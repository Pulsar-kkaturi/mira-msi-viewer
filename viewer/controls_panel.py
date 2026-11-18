"""
controls_panel.py
Bottom control bar: m/z channel slider, brightness/contrast Min/Max spinboxes,
colormap selector, normalization combo box, Auto button.

Public methods:
    set_data(n_channels, mz_array)   – called after file load to set slider range
    set_channel(idx)                 – sync channel slider position
    sync_brightness(vmin, vmax)      – reflect right-click drag result from image viewer
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QSlider, QPushButton, QComboBox, QDoubleSpinBox,
    QGroupBox, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal


class ControlsPanel(QWidget):
    """
    하단 컨트롤 패널.
    변경 시그널을 통해 MainWindow → ImageViewer로 값을 전달한다.
    """

    # m/z 채널 변경 요청
    channel_changed   = pyqtSignal(int)

    # 밝기/대비 범위 변경 (vmin, vmax)
    brightness_changed = pyqtSignal(float, float)

    # 컬러맵 변경 (이름 문자열)
    colormap_changed  = pyqtSignal(str)

    # 정규화 모드 변경 ('none' | 'tic' | 'rms' | 'median')
    norm_changed      = pyqtSignal(str)

    # Auto 버튼 클릭 (현재 채널에 맞게 percentile 재조정 요청)
    auto_brightness   = pyqtSignal()

    # Bin 크기 변경 (Da)
    bin_changed       = pyqtSignal(float)

    # 현재 채널의 즐겨찾기 추가/제거 요청
    favorite_toggle_requested = pyqtSignal()

    # Favorites 콤보박스에서 선택한 채널로 이동 요청
    favorite_channel_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(110)

        self._n_channels = 1
        self._mz_array: np.ndarray | None = None

        # 슬라이더 내부 변경 중 시그널 억제용 플래그
        self._updating = False

        self._build_ui()

    # ------------------------------------------------------------------ #
    #  UI 구성
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 4)
        root.setSpacing(10)

        # ── 1. 채널(m/z) 슬라이더 그룹 ──────────────────────────────────
        self._ch_group = QGroupBox("Channel  (m/z)")
        ch_group = self._ch_group
        ch_layout = QVBoxLayout(ch_group)
        ch_layout.setContentsMargins(4, 4, 4, 2)
        ch_layout.setSpacing(2)

        self._ch_slider = QSlider(Qt.Orientation.Horizontal)
        self._ch_slider.setMinimum(0)
        self._ch_slider.setMaximum(0)
        self._ch_slider.setValue(0)
        self._ch_slider.setTickInterval(1)
        self._ch_slider.valueChanged.connect(self._on_channel_slider)

        self._ch_label = QLabel("ch 0  |  m/z —  |  Shift+click image to select pixel")
        self._ch_label.setStyleSheet("font-size: 11px;")

        ch_layout.addWidget(self._ch_slider)
        ch_layout.addWidget(self._ch_label)

        # ── m/z 직접 입력 행 ──────────────────────────────────────────────
        mz_row = QHBoxLayout()
        mz_row.setSpacing(4)

        self._mz_label = QLabel("m/z:")
        mz_row.addWidget(self._mz_label)

        self._mz_spinbox = QDoubleSpinBox()
        self._mz_spinbox.setDecimals(4)
        self._mz_spinbox.setRange(0.0, 1e7)
        self._mz_spinbox.setSingleStep(0.1)
        self._mz_spinbox.setFixedWidth(110)
        self._mz_spinbox.setToolTip("Type m/z value and press Enter to jump to nearest channel")
        self._mz_spinbox.editingFinished.connect(self._on_mz_spinbox)
        mz_row.addWidget(self._mz_spinbox)

        self._favorite_btn = QPushButton("☆")
        self._favorite_btn.setFixedWidth(30)
        self._favorite_btn.setToolTip("Add current channel to favorites")
        self._favorite_btn.clicked.connect(
            lambda _checked=False: self.favorite_toggle_requested.emit()
        )
        mz_row.addWidget(self._favorite_btn)

        mz_row.addSpacing(8)

        mz_row.addWidget(QLabel("Favorites:"))
        self._favorites_combo = QComboBox()
        self._favorites_combo.setFixedWidth(125)
        self._favorites_combo.setPlaceholderText("—")
        self._favorites_combo.setMaxVisibleItems(10)
        # macOS native combo popups can ignore maxVisibleItems. Force Qt's
        # list-style popup so the 11th favorite reliably introduces scrolling.
        self._favorites_combo.setStyleSheet(
            "QComboBox { combobox-popup: 0; }"
        )
        self._favorites_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._favorites_combo.setToolTip(
            "Select a favorite channel to jump to it (10 visible at a time)"
        )
        self._favorites_combo.activated.connect(
            self._on_favorite_combo_activated
        )
        mz_row.addWidget(self._favorites_combo)

        mz_row.addSpacing(8)

        # ── Bin (Da) 입력 ────────────────────────────────────────────────
        mz_row.addWidget(QLabel("Bin (Da):"))
        self._bin_spinbox = QDoubleSpinBox()
        self._bin_spinbox.setDecimals(3)
        self._bin_spinbox.setRange(0.0, 100.0)
        self._bin_spinbox.setSingleStep(0.01)
        self._bin_spinbox.setValue(0.0)
        self._bin_spinbox.setFixedWidth(80)
        self._bin_spinbox.setToolTip("0 = 단일 채널 모드; 양수 = ±(Da/2) 범위 평균/합 이미지")
        self._bin_spinbox.valueChanged.connect(self._on_bin_changed)
        mz_row.addWidget(self._bin_spinbox)

        mz_row.addStretch()
        ch_layout.addLayout(mz_row)

        root.addWidget(ch_group, stretch=4)

        # ── 2. 밝기/대비 그룹 ────────────────────────────────────────────
        br_group = QGroupBox("Brightness / Contrast")
        br_layout = QVBoxLayout(br_group)
        br_layout.setContentsMargins(4, 4, 4, 2)
        br_layout.setSpacing(2)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(4)

        # Min
        slider_row.addWidget(QLabel("Min"))
        self._min_spin = QDoubleSpinBox()
        self._min_spin.setDecimals(4)
        self._min_spin.setRange(-1e9, 1e9)
        self._min_spin.setSingleStep(0.01)
        self._min_spin.setFixedWidth(90)
        self._min_spin.valueChanged.connect(self._on_brightness_spin)
        slider_row.addWidget(self._min_spin)

        # Max
        slider_row.addWidget(QLabel("Max"))
        self._max_spin = QDoubleSpinBox()
        self._max_spin.setDecimals(4)
        self._max_spin.setRange(-1e9, 1e9)
        self._max_spin.setSingleStep(0.01)
        self._max_spin.setFixedWidth(90)
        self._max_spin.valueChanged.connect(self._on_brightness_spin)
        slider_row.addWidget(self._max_spin)

        # Auto 버튼
        self._auto_btn = QPushButton("Auto")
        self._auto_btn.setFixedWidth(46)
        self._auto_btn.setToolTip("Auto-adjust brightness to 2%–98% percentile of current channel")
        self._auto_btn.clicked.connect(self.auto_brightness)
        slider_row.addWidget(self._auto_btn)

        br_layout.addLayout(slider_row)

        tip = QLabel("Right-click drag: up/down = brightness  ·  left/right = contrast")
        tip.setStyleSheet("font-size: 10px; color: #6c7086;")
        br_layout.addWidget(tip)

        root.addWidget(br_group, stretch=3)

        # ── 3. 컬러맵 + 정규화 ───────────────────────────────────────────
        opt_group = QGroupBox("Display Options")
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setContentsMargins(4, 4, 4, 2)
        opt_layout.setSpacing(4)

        cmap_row = QHBoxLayout()
        cmap_row.addWidget(QLabel("Colormap"))
        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(["gray", "viridis", "hot", "inferno"])
        self._cmap_combo.currentTextChanged.connect(self.colormap_changed)
        cmap_row.addWidget(self._cmap_combo)
        opt_layout.addLayout(cmap_row)

        norm_row = QHBoxLayout()
        norm_row.addWidget(QLabel("Normalize"))
        self._norm_combo = QComboBox()
        self._norm_combo.addItems(["none", "TIC", "RMS", "Median"])
        self._norm_combo.currentTextChanged.connect(self._on_norm_changed)
        norm_row.addWidget(self._norm_combo)
        opt_layout.addLayout(norm_row)

        root.addWidget(opt_group, stretch=2)

    # ------------------------------------------------------------------ #
    #  외부 API
    # ------------------------------------------------------------------ #

    def set_data(self, n_channels: int, mz_array: np.ndarray, mode: str = "continuous"):
        """파일 로드 후 슬라이더 범위와 m/z 배열을 설정한다."""
        self._n_channels = n_channels
        self._mz_array = mz_array
        self._mode = mode

        # TIFF 모드: 라벨을 "Ch"로, imzML 모드: "m/z"로
        is_tiff = (mode == "tiff")
        axis_label = "Ch" if is_tiff else "m/z"
        self._ch_group.setTitle(f"Channel  ({axis_label})")
        self._mz_label.setText(f"{axis_label}:")

        self._updating = True
        self._ch_slider.setMaximum(n_channels - 1)
        self._ch_slider.setValue(0)

        if mz_array is not None and len(mz_array) > 0:
            self._mz_spinbox.setRange(float(mz_array[0]), float(mz_array[-1]))
            self._mz_spinbox.setValue(float(mz_array[0]))
            if is_tiff:
                self._mz_spinbox.setDecimals(0)
                self._mz_spinbox.setSingleStep(1.0)
            else:
                self._mz_spinbox.setDecimals(4)
                self._mz_spinbox.setSingleStep(0.1)

        self._updating = False

        self._update_channel_label(0)
        self.set_favorite_state(False)

    def set_channel(self, idx: int):
        """채널 슬라이더를 외부(이미지 뷰어 휠 등)와 동기화한다."""
        idx = int(np.clip(idx, 0, self._n_channels - 1))
        self._updating = True
        self._ch_slider.setValue(idx)
        if self._mz_array is not None and idx < len(self._mz_array):
            self._mz_spinbox.setValue(float(self._mz_array[idx]))
        self._updating = False
        self._update_channel_label(idx)

    def sync_brightness(self, vmin: float, vmax: float):
        """이미지 뷰어의 우클릭 드래그 결과를 스핀박스에 반영한다."""
        self._updating = True
        self._min_spin.setValue(vmin)
        self._max_spin.setValue(vmax)
        self._updating = False

    def set_brightness(self, vmin: float, vmax: float):
        """Auto 등 외부에서 밝기/대비 값을 설정한다."""
        self.sync_brightness(vmin, vmax)

    def set_favorite_state(self, is_favorite: bool):
        """Reflect MainWindow's authoritative favorite state for the channel."""
        self._favorite_btn.setText("★" if is_favorite else "☆")
        action = "Remove current channel from" if is_favorite else "Add current channel to"
        self._favorite_btn.setToolTip(f"{action} favorites")

    def set_favorites(self, channels: set[int], current_channel: int):
        """Rebuild the sorted favorite selector and reflect the current channel."""
        self._updating = True
        self._favorites_combo.clear()
        for idx in sorted(channels):
            if self._mz_array is None or not 0 <= idx < len(self._mz_array):
                continue
            axis_value = self._mz_array[idx]
            text = (
                f"Ch {int(axis_value)}"
                if self._mode == "tiff"
                else f"{axis_value:.4f}"
            )
            self._favorites_combo.addItem(text, idx)
        self._updating = False
        self.set_favorite_selection(current_channel)

    def set_favorite_selection(self, channel_idx: int):
        """Select the current favorite, or show the blank placeholder."""
        self._updating = True
        combo_idx = self._favorites_combo.findData(channel_idx)
        self._favorites_combo.setCurrentIndex(combo_idx)
        self._updating = False

    # ------------------------------------------------------------------ #
    #  내부 슬롯
    # ------------------------------------------------------------------ #

    def bin_value(self) -> float:
        """현재 설정된 bin 크기(Da)를 반환한다."""
        return self._bin_spinbox.value()

    def _on_channel_slider(self, value: int):
        if self._updating:
            return
        self._update_channel_label(value)
        self.channel_changed.emit(value)

    def _on_mz_spinbox(self):
        """m/z SpinBox에서 Enter 입력 시 가장 가까운 채널로 이동."""
        if self._updating or self._mz_array is None:
            return
        mz_val = self._mz_spinbox.value()
        idx = int(np.argmin(np.abs(self._mz_array - mz_val)))
        self._update_channel_label(idx)
        self.channel_changed.emit(idx)

    def _on_favorite_combo_activated(self, combo_idx: int):
        if self._updating or combo_idx < 0:
            return
        channel_idx = self._favorites_combo.itemData(combo_idx)
        if channel_idx is not None:
            self.favorite_channel_selected.emit(int(channel_idx))

    def _on_bin_changed(self, value: float):
        if self._updating:
            return
        self.bin_changed.emit(value)

    def _on_brightness_spin(self):
        if self._updating:
            return
        vmin = self._min_spin.value()
        vmax = self._max_spin.value()
        if vmax > vmin:
            self.brightness_changed.emit(vmin, vmax)

    def _on_norm_changed(self, text: str):
        """콤보박스 텍스트 → 소문자 모드 문자열로 변환 후 시그널 발생."""
        self.norm_changed.emit(text.lower())

    def _update_channel_label(self, idx: int):
        if self._mz_array is not None and idx < len(self._mz_array):
            mz = self._mz_array[idx]
            mode = getattr(self, "_mode", "continuous")
            if mode == "tiff":
                self._ch_label.setText(f"ch {idx}  |  Ch {int(mz)}")
            else:
                self._ch_label.setText(f"ch {idx}  |  m/z {mz:.4f}")
            self._updating = True
            self._mz_spinbox.setValue(float(mz))
            self._updating = False
        else:
            self._ch_label.setText(f"ch {idx}  |  —")
