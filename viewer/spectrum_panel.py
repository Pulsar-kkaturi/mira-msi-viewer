"""
spectrum_panel.py
Panel displaying the global spectrum and the selected pixel spectrum using pyqtgraph.

Layout:
  - Top:    GlobalSpectrumWidget  – sum of all pixels (static after file load)
  - Bottom: PixelSpectrumWidget   – spectrum of the Shift+clicked pixel
  - Both plots show a vertical line at the current channel's m/z position
  - Clicking on either spectrum jumps to that m/z channel
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal

from .roi_panel import ROIPanel


# pyqtgraph 기본 배경을 어둡게 설정
pg.setConfigOption("background", "#1e1e2e")
pg.setConfigOption("foreground", "#cdd6f4")


class _SpectrumWidget(pg.PlotWidget):
    """
    단일 스펙트럼 플롯 위젯 (전체 / 픽셀 공통 베이스).
    클릭 시 channel_selected 시그널을 발생시킨다.
    """

    channel_selected = pyqtSignal(int)  # 클릭 위치의 채널 인덱스

    def __init__(self, title: str, line_color: str, parent=None):
        super().__init__(parent, title=title)

        self.showGrid(x=True, y=True, alpha=0.2)
        self.setLabel("bottom", "m/z")
        self.setLabel("left", "Intensity")
        self.setMouseEnabled(x=True, y=True)

        # 스펙트럼 커브 (stem 스타일: 각 피크마다 수직선만, 마커 없음)
        self._curve = self.plot(
            pen=pg.mkPen(color=line_color, width=1.0),
            antialias=False,
        )
        self._curve.setZValue(10)

        # 현재 채널 수직선
        self._vline = pg.InfiniteLine(
            angle=90,
            movable=False,
            pen=pg.mkPen(color="#f38ba8", width=1.5, style=Qt.PenStyle.DashLine),
        )
        self._vline.setZValue(20)
        self.addItem(self._vline)

        # 내부 상태
        self._mz_array: np.ndarray | None = None
        self._extra_curves: dict[str, pg.PlotDataItem] = {}
        self._favorite_lines: dict[int, pg.InfiniteLine] = {}

        # 클릭 이벤트 연결
        self.scene().sigMouseClicked.connect(self._on_click)

    # ------------------------------------------------------------------ #
    #  데이터 업데이트
    # ------------------------------------------------------------------ #

    def set_spectrum(self, mz: np.ndarray, intensity: np.ndarray):
        """스펙트럼 데이터를 stem 스타일로 업데이트한다.
        각 m/z 피크를 (mz, 0) → (mz, intensity) 수직선 쌍으로 렌더링한다."""
        self._mz_array = mz
        self._set_curve_data(self._curve, mz, intensity)

    def clear_spectrum(self):
        """클릭 가능한 m/z 축은 유지하면서 기본 curve만 비운다."""
        self._curve.setData(x=[], y=[])

    @staticmethod
    def _set_curve_data(curve, mz: np.ndarray, intensity: np.ndarray):
        """주어진 pyqtgraph curve에 공통 stem 형식 데이터를 설정한다."""
        n = len(mz)
        if n == 0:
            curve.setData(x=[], y=[])
            return
        # 각 피크를 [baseline, tip] 쌍으로 펼침
        x = np.repeat(mz, 2)                    # [mz0, mz0, mz1, mz1, ...]
        y = np.zeros(n * 2, dtype=np.float64)
        y[1::2] = intensity                      # [0, int0, 0, int1, ...]
        # connect[i]=1: i번 점과 i+1번 점을 연결
        # 쌍 내부(baseline→tip)만 연결, 피크 간 연결은 끊음
        connect = np.zeros(n * 2, dtype=np.uint8)
        connect[::2] = 1
        curve.setData(x=x, y=y, connect=connect)

    def add_extra_curve(self, key: str, color: str):
        """키로 식별되는 보조 stem curve를 필요할 때 한 번만 만든다."""
        if key in self._extra_curves:
            return
        self._extra_curves[key] = self.plot(
            pen=pg.mkPen(color=color, width=1.0),
            antialias=False,
        )

    def set_extra_curve_data(
        self,
        key: str,
        mz: np.ndarray,
        intensity: np.ndarray,
    ):
        curve = self._extra_curves.get(key)
        if curve is None:
            return
        self._set_curve_data(curve, mz, intensity)

    def remove_extra_curve(self, key: str):
        curve = self._extra_curves.pop(key, None)
        if curve is not None:
            self.removeItem(curve)

    def clear_extra_curves(self):
        for key in list(self._extra_curves):
            self.remove_extra_curve(key)

    def set_channel_line(self, mz_value: float):
        """수직선 위치를 현재 채널의 m/z 값으로 이동한다."""
        self._vline.setPos(mz_value)

    def set_favorite_markers(self, channels: set[int]):
        """Synchronize fixed favorite-channel markers with the given indices."""
        valid_channels = {
            int(idx)
            for idx in channels
            if self._mz_array is not None and 0 <= idx < len(self._mz_array)
        }

        for idx in list(self._favorite_lines):
            if idx not in valid_channels:
                self.removeItem(self._favorite_lines.pop(idx))

        for idx in sorted(valid_channels):
            if idx in self._favorite_lines:
                self._favorite_lines[idx].setPos(float(self._mz_array[idx]))
                continue
            line = pg.InfiniteLine(
                pos=float(self._mz_array[idx]),
                angle=90,
                movable=False,
                pen=pg.mkPen(
                    color="#fab387",
                    width=1.5,
                    style=Qt.PenStyle.DotLine,
                ),
            )
            # Keep spectrum stems above favorites; the current-channel line
            # remains highest at z=20.
            line.setZValue(5)
            # Let the plot's existing nearest-channel click handler receive
            # clicks that visually land on a favorite marker.
            line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.addItem(line)
            self._favorite_lines[idx] = line

    def clear_favorite_markers(self):
        for line in self._favorite_lines.values():
            self.removeItem(line)
        self._favorite_lines.clear()

    # ------------------------------------------------------------------ #
    #  클릭 → 채널 이동
    # ------------------------------------------------------------------ #

    def _on_click(self, event):
        """플롯 클릭 시 해당 m/z 위치의 채널 인덱스를 시그널로 전달한다."""
        if self._mz_array is None:
            return
        # 뷰 좌표 → 데이터 좌표 변환
        vb = self.plotItem.vb
        mouse_point = vb.mapSceneToView(event.scenePos())
        clicked_mz = mouse_point.x()
        # 가장 가까운 채널
        idx = int(np.argmin(np.abs(self._mz_array - clicked_mz)))
        self.channel_selected.emit(idx)


class SpectrumPanel(QWidget):
    """
    전체 스펙트럼(상단) + 픽셀 스펙트럼(하단)을 세로로 배치한 패널 위젯.

    외부에서 호출할 메서드:
        set_data(mz, global_intensity)             – 파일 로드 후 전체 스펙트럼 설정
        update_pixel(mz, intensity, row, col)      – hover 픽셀 스펙트럼 업데이트
        update_pixel(mz, intensity, label=...)     – ROI 등 커스텀 레이블로 스펙트럼 업데이트
        set_channel(channel_idx, mz)               – 채널 수직선 이동
    """

    # 스펙트럼 클릭 시 채널 변경 요청 시그널
    channel_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # 상단 레이블
        lbl_global = QLabel("Global Spectrum  (sum of all pixels)")
        lbl_global.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 2px 4px;")

        # 전체 스펙트럼 플롯
        self._global = _SpectrumWidget(title="", line_color="#89b4fa")
        self._global.channel_selected.connect(self.channel_selected)

        # 하단 레이블
        lbl_pixel = QLabel("Pixel Spectrum  (Shift+click image to select)")
        lbl_pixel.setStyleSheet("color: #a6adc8; font-size: 11px; padding: 2px 4px;")
        self._pixel_label = lbl_pixel

        # 픽셀 스펙트럼 플롯
        self._pixel = _SpectrumWidget(title="", line_color="#cdd6f4")
        self._pixel.channel_selected.connect(self.channel_selected)

        self.roi_panel = ROIPanel()

        # 스플리터로 높이 조절 가능하게
        splitter = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.addWidget(lbl_global)
        top_layout.addWidget(self._global)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)
        bottom_layout.addWidget(lbl_pixel)
        bottom_layout.addWidget(self.roi_panel)
        bottom_layout.addWidget(self._pixel)

        splitter.addWidget(top)
        splitter.addWidget(bottom)
        splitter.setSizes([200, 200])

        layout.addWidget(splitter)

    # ------------------------------------------------------------------ #
    #  외부 API
    # ------------------------------------------------------------------ #

    def set_data(self, mz: np.ndarray, global_intensity: np.ndarray):
        """파일 로드 후 전체 합산 스펙트럼을 설정한다."""
        self._global.clear_favorite_markers()
        self._global.set_spectrum(mz, global_intensity)
        # 픽셀 스펙트럼은 빈 배열로 초기화
        self._pixel.set_spectrum(mz, np.zeros_like(mz))
        self._pixel.clear_extra_curves()

    def set_roi_spectra(
        self,
        rois: list[dict | None],
        colors: list[str],
        mean_per_pixel: bool,
    ):
        """하단 플롯의 활성 ROI 곡선을 현재 UI 상태에 맞춘다."""
        for slot, roi in enumerate(rois):
            key = f"roi{slot}"
            if roi is None or not roi["visible"]:
                self._pixel.remove_extra_curve(key)
                continue

            intensity = roi["intensity"]
            if not mean_per_pixel:
                intensity = intensity * roi["pixel_count"]
            self._pixel.add_extra_curve(key, colors[slot])
            self._pixel.set_extra_curve_data(key, roi["mz"], intensity)

    def clear_pixel_spectrum(self):
        """ROI 비교를 시작할 때 이전 단일 픽셀 미리보기만 제거한다."""
        self._pixel.clear_spectrum()
        self._pixel_label.setText(
            "Pixel Spectrum  (Shift+click image to select)"
        )

    def update_pixel(
        self,
        mz: np.ndarray,
        intensity: np.ndarray,
        row: int | None = None,
        col: int | None = None,
        label: str | None = None,
    ):
        """
        hover 픽셀(또는 ROI 등 다른 소스)의 스펙트럼을 업데이트한다.
        label이 주어지면 그대로 레이블 텍스트로 사용하고,
        없으면 기존처럼 (row, col) 기반의 "Pixel Spectrum (x=.., y=..)" 포맷을 사용한다.
        """
        self._pixel.set_spectrum(mz, intensity)
        if label is not None:
            self._pixel_label.setText(label)
        else:
            self._pixel_label.setText(f"Pixel Spectrum  (x={col}, y={row})")

    def set_channel(self, _channel_idx: int, mz_value: float):
        """두 스펙트럼 플롯의 수직선 위치를 현재 채널로 업데이트한다."""
        self._global.set_channel_line(mz_value)
        self._pixel.set_channel_line(mz_value)

    def set_favorites(self, channels: set[int]):
        """Show favorites only in the Global Spectrum plot."""
        self._global.set_favorite_markers(channels)

    def set_xlabel(self, label: str):
        """두 스펙트럼 플롯의 x축 레이블을 변경한다 (예: 'Channel' 또는 'm/z (Da)')."""
        self._global.setLabel("bottom", label)
        self._pixel.setLabel("bottom", label)
