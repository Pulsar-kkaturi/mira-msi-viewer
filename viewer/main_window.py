"""
main_window.py
Main QMainWindow for MIRA.

Layout:
  ┌──────────────────────────────────────────────┐
  │  Menubar: platform-native menus                │
  │  Toolbar: [Open] [TIC Image] [Colocalization] │
  │           [Zoom Reset] [Clear]                │
  ├─────────────────────┬────────────────────────┤
  │                     │  Global Spectrum        │
  │   ImageViewer       ├────────────────────────┤
  │   (QGraphicsView)   │  Pixel/ROI Spectrum     │
  │                     │  (Shift+click/drag)     │
  ├─────────────────────┴────────────────────────┤
  │  OverlayPanel (F12: R/G/B channel pickers,    │
  │                only visible while active)     │
  ├────────────────────────────────────────────────┤
  │  ControlsPanel (channel slider, brightness,    │
  │                 normalization)                 │
  └──────────────────────────────────────────────┘

  Ctrl+drag on the image opens an independent, non-modal Line Profile
  popup per line (up to 5); closing a popup deletes that line. Disabled
  while the Colocalization Overlay (F12) is active — Shift+click/drag
  (pixel/ROI spectrum) keep working since they don't depend on a single
  "current channel".

All inter-panel communication is mediated here via signals/slots.
"""

from __future__ import annotations

import csv
import os
import sys
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QFileDialog, QStatusBar, QMessageBox,
    QProgressDialog, QLabel, QDialog,
)
from PyQt6.QtCore import Qt, QThread, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence

from .data_model import MSIDataModel
from .image_viewer import ImageViewer
from .spectrum_panel import SpectrumPanel
from .controls_panel import ControlsPanel
from .overlay_panel import OverlayPanel
from .export_dialog import ExportDialog
from .line_profile_dialog import LineProfileDialog
from .about_dialog import AboutDialog, APP_NAME, APP_VERSION, APP_UPDATED
from .user_manual_dialog import UserManualDialog, user_manual_path


# ------------------------------------------------------------------ #
#  Background file loader (prevents UI freeze on large files)
# ------------------------------------------------------------------ #

class _LoadWorker(QObject):
    """Worker that loads an MSI file in a background thread."""
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(
        self,
        model: MSIDataModel,
        path: str,
        bin_da: float = 0.0,
        is_tiff: bool = False,
    ):
        super().__init__()
        self._model   = model
        self._path    = path
        self._bin_da  = bin_da
        self._is_tiff = is_tiff

    def run(self):
        try:
            if self._is_tiff:
                self._model.load_tiff(self._path)
            else:
                self._model.load(self._path, self._bin_da)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


# ------------------------------------------------------------------ #
#  Main window
# ------------------------------------------------------------------ #

class MainWindow(QMainWindow):

    # 창 생성/레지스트리는 main.py가 소유하고, MainWindow는 요청과 종료만 알린다.
    new_window_requested = pyqtSignal(object)
    window_closed = pyqtSignal(object)

    _ROI_COLORS = ["#f38ba8", "#a6e3a1", "#fab387", "#f9e2af", "#cba6f7"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)

        self._model = MSIDataModel()
        self._current_channel = 0
        self._bin_mode = "mean"   # F4: bin 집계 방식 ('mean' | 'sum')
        # index가 ROI 번호/색상 슬롯이며 None은 재사용 가능한 빈 슬롯이다.
        self._rois: list[dict | None] = [None] * 5
        # F15: slot(0~4) -> 열려있는 LineProfileDialog. 라인 좌표/데이터 자체는
        # ImageViewer가 소유하므로, 여기서는 팝업 창 자체만 추적한다.
        self._line_popups: dict[int, LineProfileDialog] = {}
        # F12: 컬로컬라이제이션 오버레이(RGB 합성) 모드 on/off 여부.
        self._overlay_mode: bool = False
        # 비동기 로드가 성공했을 때 이 창의 제목에 반영할 파일 경로.
        self._loading_path: str | None = None
        # F17: 즐겨찾기는 창마다, 정규화된 파일 경로마다 세션 동안만 유지한다.
        self._favorites_by_file: dict[str, set[int]] = {}
        self._current_file_key: str | None = None
        self._load_thread: QThread | None = None
        self._load_worker: _LoadWorker | None = None

        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        self._set_ui_enabled(False)

    # ------------------------------------------------------------------ #
    #  UI build
    # ------------------------------------------------------------------ #

    def _build_menubar(self):
        menubar = self.menuBar()

        # ── File menu ─────────────────────────────────────────────────
        file_menu = menubar.addMenu("File")

        new_window_act = QAction("New Window", self)
        new_window_act.setShortcut(QKeySequence.StandardKey.New)
        new_window_act.triggered.connect(
            lambda: self.new_window_requested.emit(self)
        )
        file_menu.addAction(new_window_act)

        open_act = QAction("Open File…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_file)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        export_act = QAction("Export Image…", self)
        export_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        export_act.triggered.connect(self._export_image)
        file_menu.addAction(export_act)

        self._export_global_spectrum_action = QAction(
            "Export Global Spectrum…", self
        )
        self._export_global_spectrum_action.triggered.connect(
            self._export_global_spectrum
        )
        file_menu.addAction(self._export_global_spectrum_action)

        self._export_roi_spectra_action = QAction("Export ROI Spectra…", self)
        self._export_roi_spectra_action.triggered.connect(
            self._export_roi_spectra
        )
        file_menu.addAction(self._export_roi_spectra_action)

        file_menu.addSeparator()

        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # Qt moves PreferencesRole into the application menu on macOS. The
        # temporary File attachment gives Qt an owning menu without exposing an
        # otherwise-empty Edit menu; other platforms use an explicit Settings menu.
        prefs_act = QAction("Preferences…", self)
        prefs_act.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_act.triggered.connect(self._show_preferences)
        if sys.platform == "darwin":
            file_menu.addAction(prefs_act)
        else:
            settings_menu = menubar.addMenu("Settings")
            settings_menu.addAction(prefs_act)

        # ── View menu ─────────────────────────────────────────────────
        view_menu = menubar.addMenu("View")

        tic_act = QAction("Show TIC Image", self)
        tic_act.triggered.connect(self._show_tic)
        view_menu.addAction(tic_act)

        # F12: R/G/B 채널을 additive RGB 합성으로 보는 컬로컬라이제이션 오버레이.
        # 툴바의 체크 가능한 버튼과 서로 동기화된다 (_sync_colocalization_toggle).
        self._colocalization_menu_action = QAction("Colocalization Overlay", self)
        self._colocalization_menu_action.setCheckable(True)
        self._colocalization_menu_action.setToolTip(
            "Toggle multi-ion RGB colocalization overlay"
        )
        self._colocalization_menu_action.toggled.connect(
            self._on_colocalization_toggled
        )
        view_menu.addAction(self._colocalization_menu_action)

        reset_act = QAction("Reset Zoom", self)
        reset_act.setShortcut("Ctrl+0")
        reset_act.triggered.connect(
            self._image_viewer.reset_zoom if hasattr(self, "_image_viewer") else lambda: None
        )
        view_menu.addAction(reset_act)

        view_menu.addSeparator()

        # F15/Clear: 이미지 위의 ROI(F11)/픽셀 크로스헤어(F5)/라인 프로파일(F15)을
        # 한 번에 모두 지운다. 줌·채널·밝기 등 뷰 상태는 건드리지 않는다.
        self._clear_annotations_action = QAction("Clear Annotations", self)
        self._clear_annotations_action.setToolTip(
            "Clear all ROI boxes, the pixel crosshair, and line profiles from the image"
        )
        self._clear_annotations_action.triggered.connect(self._clear_all_annotations)
        view_menu.addAction(self._clear_annotations_action)

        view_menu.addSeparator()

        # F4: Bin Mode 서브메뉴 (Mean / Sum)
        bin_mode_menu = view_menu.addMenu("Bin Mode")
        self._bin_mode_group = QActionGroup(self)
        self._bin_mode_group.setExclusive(True)

        mean_act = QAction("Mean", self)
        mean_act.setCheckable(True)
        mean_act.setChecked(True)
        mean_act.triggered.connect(lambda: self._set_bin_mode("mean"))
        self._bin_mode_group.addAction(mean_act)
        bin_mode_menu.addAction(mean_act)

        sum_act = QAction("Sum", self)
        sum_act.setCheckable(True)
        sum_act.setChecked(False)
        sum_act.triggered.connect(lambda: self._set_bin_mode("sum"))
        self._bin_mode_group.addAction(sum_act)
        bin_mode_menu.addAction(sum_act)

        # ── Help menu ─────────────────────────────────────────────────
        help_menu = menubar.addMenu("Help")

        manual_act = QAction("User Manual…", self)
        manual_act.triggered.connect(self._show_user_manual)
        help_menu.addAction(manual_act)
        help_menu.addSeparator()

        about_act = QAction(f"About {APP_NAME}…", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)

        open_act = QAction("Open", self)
        open_act.setToolTip("Open MSI file  (Ctrl+O)")
        open_act.triggered.connect(self._open_file)
        tb.addAction(open_act)

        tb.addSeparator()

        tic_act = QAction("TIC Image", self)
        tic_act.setToolTip("Show TIC image")
        tic_act.triggered.connect(self._show_tic)
        tb.addAction(tic_act)

        # F12: View 메뉴의 Colocalization Overlay 액션과 상호 동기화된다.
        self._colocalization_action = QAction("Colocalization", self)
        self._colocalization_action.setCheckable(True)
        self._colocalization_action.setToolTip(
            "Toggle multi-ion RGB colocalization overlay"
        )
        self._colocalization_action.toggled.connect(
            self._on_colocalization_toggled
        )
        tb.addAction(self._colocalization_action)

        tb.addSeparator()

        zoom_reset = QAction("Zoom Reset", self)
        zoom_reset.setToolTip("Reset zoom  (or double-click on image)")
        zoom_reset.triggered.connect(lambda: self._image_viewer.reset_zoom())
        tb.addAction(zoom_reset)

        clear_act = QAction("Clear", self)
        clear_act.setToolTip(
            "Clear all ROI boxes, the pixel crosshair, and line profiles from the image"
        )
        clear_act.triggered.connect(self._clear_all_annotations)
        tb.addAction(clear_act)

    def _build_central(self):
        """Central widget: image viewer + spectrum panel + controls panel."""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        # Top: image viewer (left) + spectrum panel (right)
        hsplitter = QSplitter(Qt.Orientation.Horizontal)

        self._image_viewer = ImageViewer()
        hsplitter.addWidget(self._image_viewer)

        self._spectrum_panel = SpectrumPanel()
        hsplitter.addWidget(self._spectrum_panel)

        hsplitter.setSizes([760, 500])

        root_layout.addWidget(hsplitter, stretch=1)

        # F12: Overlay Controls 패널 — 오버레이 모드가 켜져 있을 때만 표시된다
        # (ROI 패널과 동일한 "내장형, 자동 표시/숨김" 패턴).
        self._overlay_panel = OverlayPanel()
        root_layout.addWidget(self._overlay_panel)

        # Bottom: controls panel
        self._controls = ControlsPanel()
        root_layout.addWidget(self._controls)

        # ── Signal connections ────────────────────────────────────────

        self._image_viewer.pixel_clicked.connect(self._on_pixel_clicked)
        self._image_viewer.brightness_changed.connect(self._controls.sync_brightness)
        self._image_viewer.roi_selected.connect(self._on_roi_selected)
        # F15: 라인마다 독립 팝업으로 뜨므로, dock 대신 팝업 생성/전달 슬롯에 연결한다.
        self._image_viewer.line_added.connect(self._on_line_added)
        self._image_viewer.line_profile_ready.connect(self._on_line_profile_ready)
        self._image_viewer.line_limit_reached.connect(self._on_line_limit_reached)
        self._image_viewer.channel_step.connect(self._on_channel_step)

        self._controls.channel_changed.connect(self._on_channel_changed)
        self._controls.brightness_changed.connect(self._image_viewer.set_vmin_vmax)
        self._controls.colormap_changed.connect(self._image_viewer.set_colormap)
        self._controls.norm_changed.connect(self._on_norm_changed)
        self._controls.auto_brightness.connect(self._auto_brightness)
        self._controls.bin_changed.connect(self._on_bin_changed)
        self._controls.favorite_toggle_requested.connect(
            self._toggle_current_favorite
        )
        self._controls.favorite_channel_selected.connect(
            self._on_channel_changed
        )

        # F12: Overlay Controls 패널의 값 변경 → 재렌더링 / Auto 버튼 → percentile 계산.
        self._overlay_panel.overlay_changed.connect(self._render_overlay)
        self._overlay_panel.auto_requested.connect(self._on_overlay_auto)

        self._spectrum_panel.channel_selected.connect(self._on_channel_changed)
        roi_panel = self._spectrum_panel.roi_panel
        roi_panel.roi_removed.connect(self._remove_roi)
        roi_panel.roi_visibility_changed.connect(self._set_roi_visibility)
        roi_panel.intensity_mode_changed.connect(
            self._on_roi_intensity_mode_changed
        )

    def _build_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_label = QLabel("Open a file  (File → Open File)")
        self._statusbar.addWidget(self._status_label)

        ver_label = QLabel(f"{APP_NAME} v{APP_VERSION}  ·  {APP_UPDATED}  |  ABEL, SNU GSCST")
        ver_label.setStyleSheet("color: #888; font-size: 11px; padding-right: 6px;")
        self._statusbar.addPermanentWidget(ver_label)

    # ------------------------------------------------------------------ #
    #  File open
    # ------------------------------------------------------------------ #

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MSI File",
            "",
            "MSI Files (*.imzML *.imzml *.tif *.tiff)"
            ";;imzML Files (*.imzML *.imzml)"
            ";;TIFF Files (*.tif *.tiff)"
            ";;All Files (*)",
        )
        if not path:
            return

        is_tiff = path.lower().endswith((".tif", ".tiff"))
        bin_da = 0.0

        if not is_tiff:
            # ── imzML: 채널 수 사전 스캔 → 대용량 시 빈닝 다이얼로그 ──
            try:
                mode, n_ch, mz_min, mz_max = MSIDataModel.pre_scan(path)
                print(f"[pre_scan] mode={mode}, n_channels={n_ch}, mz={mz_min:.2f}–{mz_max:.2f}")
            except Exception as e:
                import traceback
                print(f"[pre_scan] failed: {e}")
                traceback.print_exc()
                mode, n_ch, mz_min, mz_max = "continuous", 0, 0.0, 0.0

            from .settings_dialog import get_channel_threshold
            threshold = get_channel_threshold()

            if n_ch > threshold:
                from .spectral_resolution_dialog import SpectralResolutionDialog
                dlg = SpectralResolutionDialog(
                    self,
                    mode=mode,
                    n_channels=n_ch,
                    mz_min=mz_min,
                    mz_max=mz_max,
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return
                bin_da = dlg.bin_da

        self._loading_path = path

        # ── 로딩 진행 다이얼로그 ──────────────────────────────────────
        progress = QProgressDialog("Loading file…", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(300)
        progress.show()

        self._load_thread = QThread()
        self._load_worker = _LoadWorker(
            self._model, path, bin_da=bin_da, is_tiff=is_tiff
        )
        self._load_worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(lambda: self._on_load_finished(progress))
        self._load_worker.error.connect(self._load_thread.quit)
        self._load_worker.error.connect(lambda e: self._on_load_error(e, progress))
        self._load_thread.start()

    def _on_load_finished(self, progress: QProgressDialog):
        progress.close()
        m = self._model

        # 새 파일 로드 시 이전 파일의 ROI/라인 프로파일 잔상·좌표를 초기화
        # (이미지 크기가 달라지면 이전 좌표가 무효화될 수 있음)
        self._rois = [None] * 5
        self._spectrum_panel.roi_panel.reset()
        self._image_viewer.clear_roi()
        self._image_viewer.clear_crosshair()
        self._close_all_line_popups()

        # F12: 새 파일은 항상 일반 단일 채널 뷰로 열리게 오버레이 모드를 강제로 끈다
        # (F11 ROI/F15 라인/F5 크로스헤어와 동일한 "새 파일 로드 시 초기화" 규칙).
        self._sync_colocalization_toggle(False)
        self._overlay_mode = False
        self._overlay_panel.setVisible(False)
        self._image_viewer.set_single_mode()
        self._image_viewer.set_line_profile_blocked(False)

        # 모드에 따라 컨트롤 패널 라벨 업데이트
        self._controls.set_data(m.n_channels, m.mz_array, mode=m.mode)
        self._overlay_panel.set_data(m.n_channels, m.mz_array, mode=m.mode)

        # 스펙트럼 패널 x축 라벨 업데이트
        x_label = "Channel" if m.mode == "tiff" else "m/z (Da)"
        self._spectrum_panel.set_xlabel(x_label)

        global_spec = m.get_global_spectrum()
        self._spectrum_panel.set_data(m.mz_array, global_spec)
        self._spectrum_panel.clear_pixel_spectrum()
        self._refresh_roi_ui()

        self._current_channel = 0
        if hasattr(self, "_first_shown"):
            del self._first_shown
        self._load_and_show_channel(0)
        self._spectrum_panel.set_channel(0, m.mz_at(0))

        if self._loading_path is not None:
            self._current_file_key = self._file_key(self._loading_path)
        else:
            self._current_file_key = None
        self._refresh_favorites()

        self._set_ui_enabled(True)

        H, W = m.shape
        if m.mode == "tiff":
            self._status_label.setText(
                f"Loaded TIFF: {H}×{W} pixels | {m.n_channels} channels"
            )
        else:
            binned = f"  (binned: {m._bin_da} Da)" if m._bin_da > 0 else ""
            self._status_label.setText(
                f"Loaded: {H}×{W} pixels | {m.n_channels} channels"
                f" | mode: {m.mode}{binned}"
            )

        if self._loading_path is not None:
            self.setWindowTitle(
                f"{APP_NAME} — {os.path.basename(self._loading_path)}"
            )
        self._loading_path = None

    def _on_load_error(self, error_msg: str, progress: QProgressDialog):
        progress.close()
        self._loading_path = None
        QMessageBox.critical(self, "Load Failed", f"Cannot open file:\n{error_msg}")

    # ------------------------------------------------------------------ #
    #  Channel change (central coordinator)
    # ------------------------------------------------------------------ #

    def _on_channel_changed(self, idx: int):
        # RGB 합성 중에는 단일 "현재 채널"이 화면을 대표하지 않는다.
        # 비활성화된 하단 컨트롤을 우회하는 Shift+휠/스펙트럼 클릭도 무시한다.
        if self._overlay_mode or not self._model.is_loaded():
            return

        idx = int(np.clip(idx, 0, self._model.n_channels - 1))
        self._current_channel = idx

        self._load_and_show_channel(idx)
        self._controls.set_channel(idx)

        mz_val = self._model.mz_at(idx)
        self._spectrum_panel.set_channel(idx, mz_val)
        self._update_favorite_button()

        self._update_status_channel(idx)

    # ------------------------------------------------------------------ #
    #  F17: Favorite channels
    # ------------------------------------------------------------------ #

    @staticmethod
    def _file_key(path: str) -> str:
        """Normalize a path for per-file, in-memory favorite storage."""
        return os.path.normcase(os.path.abspath(path))

    def _current_favorites(self) -> set[int]:
        if self._current_file_key is None:
            return set()
        return self._favorites_by_file.setdefault(self._current_file_key, set())

    def _toggle_current_favorite(self):
        """Add or remove the current channel, then refresh both UI surfaces."""
        if not self._model.is_loaded() or self._current_file_key is None:
            return
        favorites = self._current_favorites()
        if self._current_channel in favorites:
            favorites.remove(self._current_channel)
        else:
            favorites.add(self._current_channel)
        self._refresh_favorites()

    def _refresh_favorites(self):
        """Synchronize Global Spectrum markers and the current star button."""
        favorites = {
            idx
            for idx in self._current_favorites()
            if 0 <= idx < self._model.n_channels
        }
        if self._current_file_key is not None:
            self._favorites_by_file[self._current_file_key] = favorites
        self._spectrum_panel.set_favorites(favorites)
        self._controls.set_favorites(favorites, self._current_channel)
        self._update_favorite_button()

    def _update_favorite_button(self):
        is_favorite = (
            self._model.is_loaded()
            and self._current_channel in self._current_favorites()
        )
        self._controls.set_favorite_state(is_favorite)
        self._controls.set_favorite_selection(
            self._current_channel if is_favorite else -1
        )

    def _get_display_channel_image(self, idx: int) -> np.ndarray:
        """현재 view-time Bin 설정까지 반영한 한 채널의 표시 배열을 반환한다."""
        bin_da = self._controls.bin_value()
        if bin_da > 0:
            return self._model.get_bin_image(idx, bin_da, self._bin_mode)
        return self._model.get_channel_image(idx)

    def _load_and_show_channel(self, idx: int):
        """Load channel image (with bin if set) and display."""
        arr = self._get_display_channel_image(idx)
        is_first = (idx == 0 and not hasattr(self, "_first_shown"))

        if is_first:
            vmin = float(np.percentile(arr[arr > 0], 2)) if arr.max() > 0 else 0.0
            vmax = float(np.percentile(arr, 98))
            self._image_viewer.set_image(arr, vmin=vmin, vmax=vmax)
            self._controls.set_brightness(vmin, vmax)
            self._first_shown = True
        else:
            self._image_viewer.set_image(arr)

    # ------------------------------------------------------------------ #
    #  Other slots
    # ------------------------------------------------------------------ #

    def _on_pixel_clicked(self, row: int, col: int):
        if not self._model.is_loaded():
            return
        mz, intensity = self._model.get_pixel_spectrum(row, col)
        self._spectrum_panel.update_pixel(mz, intensity, row, col)

    def _on_roi_selected(self, r0: int, r1: int, c0: int, c1: int):
        """F11: 첫 빈 색상 슬롯에 ROI와 계산된 평균 스펙트럼을 저장한다."""
        if not self._model.is_loaded():
            return

        slot = next(
            (idx for idx, roi in enumerate(self._rois) if roi is None),
            None,
        )
        if slot is None:
            self._statusbar.showMessage(
                "Maximum 5 ROIs — remove one before adding another.",
                4000,
            )
            return

        mz, intensity = self._model.get_roi_spectrum(r0, r1, c0, c1)
        self._rois[slot] = {
            "r0": r0,
            "r1": r1,
            "c0": c0,
            "c1": c1,
            "mz": mz,
            "intensity": intensity,
            "pixel_count": (r1 - r0 + 1) * (c1 - c0 + 1),
            "visible": True,
        }
        # 실제로 ROI가 추가된 경우에만 픽셀 위치와 곡선을 함께 지운다.
        # 슬롯 한도 초과처럼 거부된 요청은 위에서 반환하므로 기존 선택이 유지된다.
        self._image_viewer.clear_crosshair()
        self._spectrum_panel.clear_pixel_spectrum()
        self._refresh_roi_ui()

    def _remove_roi(self, slot: int):
        if 0 <= slot < len(self._rois):
            self._rois[slot] = None
            self._refresh_roi_ui()

    def _set_roi_visibility(self, slot: int, visible: bool):
        if 0 <= slot < len(self._rois) and self._rois[slot] is not None:
            self._rois[slot]["visible"] = visible
            self._refresh_roi_ui()

    def _on_roi_intensity_mode_changed(self, _mean_per_pixel: bool):
        # 평균/합계 전환은 캐시된 스펙트럼의 표시 배율만 바꾼다.
        self._refresh_roi_ui()

    def _refresh_roi_ui(self):
        """Authoritative ROI state를 세 UI 구성요소에 한 번에 반영한다."""
        overlays = []
        for roi in self._rois:
            if roi is None:
                overlays.append(None)
            else:
                overlays.append(
                    (roi["r0"], roi["r1"], roi["c0"], roi["c1"])
                )
        self._image_viewer.set_roi_overlays(overlays)
        roi_panel = self._spectrum_panel.roi_panel
        roi_panel.set_rois(self._rois, self._ROI_COLORS)
        self._spectrum_panel.set_roi_spectra(
            self._rois,
            self._ROI_COLORS,
            roi_panel.mean_per_pixel(),
        )
        self._export_roi_spectra_action.setEnabled(
            any(roi is not None for roi in self._rois)
        )

    def _on_line_added(self, slot: int, r0: int, c0: int, r1: int, c1: int):
        """F15: 새 라인이 슬롯에 배정되면 그 슬롯 전용 비모달 팝업을 새로 띄운다."""
        popup = LineProfileDialog(slot, r0, c0, r1, c1, parent=self)
        popup.closed.connect(self._on_line_popup_closed)
        # 슬롯 번호 기반 캐스케이드 배치: 같은 슬롯은 항상 같은 위치에서 다시 열린다.
        anchor = self.frameGeometry().topLeft() + QPoint(60, 80)
        popup.move(anchor + QPoint(30, 30) * slot)
        popup.show()
        self._line_popups[slot] = popup

    def _on_line_profile_ready(self, slot: int, distances: np.ndarray, intensities: np.ndarray):
        """F15: 채널/정규화/bin 변경 등으로 재계산된 프로파일을 해당 슬롯의 팝업에 전달한다."""
        popup = self._line_popups.get(slot)
        if popup is not None:
            popup.set_profile(distances, intensities)

    def _on_line_limit_reached(self):
        self._statusbar.showMessage(
            "Maximum 5 line profiles — close a popup before adding another.",
            4000,
        )

    def _on_line_popup_closed(self, slot: int):
        """팝업 창을 닫는 것 자체가 그 라인의 삭제 동작이다."""
        self._line_popups.pop(slot, None)
        self._image_viewer.remove_line(slot)

    def _close_all_line_popups(self):
        """모든 라인 팝업을 닫고 오버레이/데이터를 정리한다 (새 파일 로드/Clear 버튼 공용)."""
        for popup in list(self._line_popups.values()):
            # 일괄 정리 중에는 개별 close()가 _on_line_popup_closed를 다시 트리거해
            # 같은 딕셔너리를 건드리지 않도록 신호를 잠시 막는다.
            popup.blockSignals(True)
            popup.close()
        self._line_popups.clear()
        self._image_viewer.clear_lines()

    def _clear_all_annotations(self):
        """Zoom Reset 옆 Clear 버튼: 줌·채널·밝기 등 뷰 상태는 그대로 두고,
        이미지 위에 그려진 ROI(F11) / 픽셀 크로스헤어(F5) / 라인 프로파일(F15)만
        모두 지운다. 기존 F11/F5/F15의 reset 메서드만 재사용한다."""
        if not self._model.is_loaded():
            return
        self._rois = [None] * 5
        self._spectrum_panel.roi_panel.reset()
        self._spectrum_panel.clear_pixel_spectrum()
        self._image_viewer.clear_roi()
        self._image_viewer.clear_crosshair()
        self._refresh_roi_ui()
        self._close_all_line_popups()

    def _on_channel_step(self, delta: int):
        """Shift+휠: 채널을 +1/-1 이동한다."""
        if not self._model.is_loaded():
            return
        self._on_channel_changed(self._current_channel + delta)

    def _on_norm_changed(self, mode: str):
        if not self._model.is_loaded():
            return
        self._model.set_normalization(mode)
        # 채널 변경과 같은 경로를 사용해야 활성 Bin과 라인 프로파일이 유지된다.
        self._load_and_show_channel(self._current_channel)

    def _auto_brightness(self):
        if not self._model.is_loaded():
            return
        arr = self._get_display_channel_image(self._current_channel)
        nonzero = arr[arr > 0]
        if len(nonzero) == 0:
            return
        vmin = float(np.percentile(nonzero, 2))
        vmax = float(np.percentile(arr, 98))
        self._image_viewer.set_vmin_vmax(vmin, vmax)
        self._controls.set_brightness(vmin, vmax)

    def _show_tic(self):
        if not self._model.is_loaded():
            return
        if self._overlay_mode:
            # 화면과 ImageViewer 내부 모드를 함께 단일 채널 상태로 되돌린다.
            self._on_colocalization_toggled(False)
        tic = self._model.get_tic_image()
        vmin = float(np.percentile(tic[tic > 0], 2)) if tic.max() > 0 else 0.0
        vmax = float(np.percentile(tic, 98))
        self._image_viewer.set_image(tic, vmin=vmin, vmax=vmax)
        self._controls.set_brightness(vmin, vmax)
        self._status_label.setText("Showing TIC Image")

    # ------------------------------------------------------------------ #
    #  F12: Colocalization overlay
    # ------------------------------------------------------------------ #

    def _sync_colocalization_toggle(self, checked: bool):
        """툴바 버튼과 View 메뉴 액션이 항상 같은 체크 상태를 보이게 한다."""
        for action in (self._colocalization_action, self._colocalization_menu_action):
            if action.isChecked() != checked:
                action.blockSignals(True)
                action.setChecked(checked)
                action.blockSignals(False)

    def _on_colocalization_toggled(self, checked: bool):
        """F12: Colocalization 오버레이 토글 (툴바 버튼/View 메뉴 공용 핸들러)."""
        if checked and not self._model.is_loaded():
            self._sync_colocalization_toggle(False)
            return

        self._sync_colocalization_toggle(checked)
        self._overlay_mode = checked
        self._overlay_panel.setVisible(checked)
        self._controls.setEnabled(not checked)
        # F5(픽셀 클릭)/F11(ROI 드래그)는 오버레이 모드에서도 그대로 동작;
        # F15(라인 프로파일)만 단일 2D 이미지가 필요해서 막는다.
        self._image_viewer.set_line_profile_blocked(checked)

        if checked:
            self._render_overlay()
        else:
            self._image_viewer.set_single_mode()
            self._load_and_show_channel(self._current_channel)

    def _render_overlay(self):
        """Build the tinted R/G/B panes and their additive Merge pane."""
        if not self._overlay_mode or not self._model.is_loaded():
            return

        H, W = self._model.shape
        merge = np.zeros((H, W, 3), dtype=np.uint8)
        panes: list[np.ndarray] = []

        for slot, (enabled, idx, vmin, vmax) in enumerate(self._overlay_panel.get_channels()):
            arr = self._get_display_channel_image(idx)
            span = max(vmax - vmin, 1e-9)
            scaled = np.clip(
                (arr - vmin) / span * 255.0, 0, 255
            ).astype(np.uint8)

            # Each individual pane is always visible in its assigned color.
            tinted = np.zeros((H, W, 3), dtype=np.uint8)
            tinted[:, :, slot] = scaled
            panes.append(tinted)

            # The checkbox controls only this channel's contribution to Merge.
            if enabled:
                merge[:, :, slot] = scaled

        self._image_viewer.set_colocalization_images(
            panes[0], panes[1], panes[2], merge
        )

    def _on_overlay_auto(self, slot: int):
        """F12: 특정 R/G/B 행의 Auto 버튼 — 그 채널의 2%/98% percentile로 Min/Max를 설정한다."""
        if not self._model.is_loaded():
            return
        idx = self._overlay_panel.get_channels()[slot][1]
        arr = self._get_display_channel_image(idx)
        nonzero = arr[arr > 0]
        if len(nonzero) == 0:
            return
        vmin = float(np.percentile(nonzero, 2))
        vmax = float(np.percentile(arr, 98))
        self._overlay_panel.set_channel_minmax(slot, vmin, vmax)
        self._render_overlay()

    def _update_status_channel(self, idx: int):
        H, W = self._model.shape
        mz = self._model.mz_at(idx)
        if self._model.mode == "tiff":
            self._status_label.setText(
                f"{H}×{W} px | ch {idx} / {self._model.n_channels - 1}"
            )
        else:
            self._status_label.setText(
                f"{H}×{W} px | ch {idx} / {self._model.n_channels - 1}  |  m/z {mz:.4f}"
            )

    def _set_bin_mode(self, mode: str):
        self._bin_mode = mode
        if self._model.is_loaded():
            if self._overlay_mode:
                self._render_overlay()
            else:
                self._load_and_show_channel(self._current_channel)

    def _on_bin_changed(self, value: float):
        if self._model.is_loaded():
            self._load_and_show_channel(self._current_channel)

    def _export_image(self):
        """F7: File → Export Image… — 현재 렌더링된 이미지를 파일로 저장한다."""
        rgb = self._image_viewer.get_rendered_image()
        if rgb is None:
            QMessageBox.information(self, "Export", "No image loaded.")
            return

        pixel_size_nm = self._model.pixel_size_nm() if self._model.is_loaded() else None
        dlg = ExportDialog(self, pixel_size_nm=pixel_size_nm)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        fmt, scalebar_on, scalebar_length, unit, pixel_size_um, position = dlg.result_data()

        ext_map = {
            "PNG": "PNG Files (*.png)",
            "JPG": "JPEG Files (*.jpg *.jpeg)",
            "TIFF": "TIFF Files (*.tif *.tiff)",
        }
        default_ext = {"PNG": ".png", "JPG": ".jpg", "TIFF": ".tif"}
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", f"image{default_ext[fmt]}", ext_map[fmt]
        )
        if not path:
            return

        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.fromarray(rgb, mode="RGB")

            if scalebar_on:
                if unit == "px":
                    bar_px = int(round(scalebar_length))
                    label = f"{int(scalebar_length)} px"
                elif unit == "µm" and pixel_size_um and pixel_size_um > 0:
                    bar_px = int(round(scalebar_length / pixel_size_um))
                    label = f"{scalebar_length:.0f} µm"
                elif unit == "nm" and pixel_size_um and pixel_size_um > 0:
                    pixel_size_nm_val = pixel_size_um * 1000.0
                    bar_px = int(round(scalebar_length / pixel_size_nm_val))
                    label = f"{scalebar_length:.0f} nm"
                else:
                    bar_px = int(round(scalebar_length))
                    label = f"{int(scalebar_length)} px"

                bar_px = max(bar_px, 2)

                draw = ImageDraw.Draw(img)
                W_img, H_img = img.size
                merge_rect = self._image_viewer.colocalization_merge_rect()
                if merge_rect is None:
                    target_x, target_y = 0, 0
                    target_w, target_h = W_img, H_img
                else:
                    # In a 2×2 export the scale bar belongs to the Merge pane,
                    # not to the Blue pane at the full canvas's bottom-left.
                    target_x, target_y, target_w, target_h = merge_rect

                margin = max(8, target_h // 40)
                bar_h = max(4, target_h // 60)

                if position == "bottom-right":
                    x1 = target_x + target_w - margin - bar_px
                else:
                    x1 = target_x + margin
                y1 = target_y + target_h - margin - bar_h
                x2, y2 = x1 + bar_px, y1 + bar_h

                draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255))

                font_size = max(10, bar_h * 2)
                try:
                    font = ImageFont.truetype(
                        "/System/Library/Fonts/Helvetica.ttc", font_size
                    )
                except Exception:
                    font = ImageFont.load_default()

                bbox = draw.textbbox((0, 0), label, font=font)
                tw = bbox[2] - bbox[0]
                tx = x1 + (bar_px - tw) // 2
                ty = y1 - (bbox[3] - bbox[1]) - 2
                draw.text((tx, ty), label, fill=(255, 255, 255), font=font)

            save_kwargs = {}
            if fmt == "JPG":
                save_kwargs["quality"] = 95
            img.save(path, **save_kwargs)

        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not save image:\n{e}")
            return

        self._status_label.setText(f"Exported: {os.path.basename(path)}")

    @staticmethod
    def _ensure_csv_extension(path: str) -> str:
        return path if path.lower().endswith(".csv") else f"{path}.csv"

    def _export_global_spectrum(self):
        """현재 상단 Global Spectrum의 raw 합산값을 CSV로 저장한다."""
        if not self._model.is_loaded():
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Global Spectrum",
            "global_spectrum.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        path = self._ensure_csv_extension(path)

        axis_label = "Channel" if self._model.mode == "tiff" else "m/z"
        intensity = self._model.get_global_spectrum()
        try:
            with open(path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([axis_label, "Global Intensity"])
                writer.writerows(zip(self._model.mz_array, intensity))
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not save global spectrum:\n{e}",
            )
            return

        self._status_label.setText(f"Exported: {os.path.basename(path)}")

    def _export_roi_spectra(self):
        """활성 ROI들을 슬롯 순서대로 현재 평균/합계 상태에 맞춰 저장한다."""
        active = [
            (slot, roi)
            for slot, roi in enumerate(self._rois)
            if roi is not None
        ]
        if not active:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ROI Spectra",
            "roi_spectra.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        path = self._ensure_csv_extension(path)

        axis_label = "Channel" if self._model.mode == "tiff" else "m/z"
        header = [axis_label]
        for slot, roi in active:
            header.append(
                f"ROI{slot + 1} "
                f"(x:{roi['c0']}-{roi['c1']}, y:{roi['r0']}-{roi['r1']})"
            )

        mean_per_pixel = self._spectrum_panel.roi_panel.mean_per_pixel()
        columns = [active[0][1]["mz"]]
        for _slot, roi in active:
            values = roi["intensity"]
            if not mean_per_pixel:
                values = values * roi["pixel_count"]
            columns.append(values)

        try:
            with open(path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(header)
                writer.writerows(zip(*columns))
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not save ROI spectra:\n{e}",
            )
            return

        self._status_label.setText(f"Exported: {os.path.basename(path)}")

    def _show_preferences(self):
        """Open the platform-native Preferences dialog."""
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

    def _show_user_manual(self):
        """Open the bundled English manual or report a packaging error."""
        path = user_manual_path()
        try:
            dlg = UserManualDialog(path, self)
        except (OSError, UnicodeError) as error:
            QMessageBox.warning(
                self,
                "User Manual Unavailable",
                f"The MIRA user manual could not be opened.\n\n"
                f"Path: {path}\n"
                f"Error: {error}",
            )
            return
        dlg.exec()

    def _show_about(self):
        dlg = AboutDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------ #
    #  UI enable/disable
    # ------------------------------------------------------------------ #

    def _set_ui_enabled(self, enabled: bool):
        self._controls.setEnabled(enabled)
        self._export_global_spectrum_action.setEnabled(enabled)
        self._export_roi_spectra_action.setEnabled(
            enabled and any(roi is not None for roi in self._rois)
        )

    def closeEvent(self, event):
        """로딩 중 파괴를 막고, 승인된 창만 앱 레지스트리에서 제거하게 알린다."""
        thread = getattr(self, "_load_thread", None)
        if thread is not None and thread.isRunning():
            event.ignore()
            self.statusBar().showMessage(
                "File is still loading. Close this window after loading finishes.",
                4000,
            )
            return

        self._close_all_line_popups()
        super().closeEvent(event)
        if event.isAccepted():
            self.window_closed.emit(self)
