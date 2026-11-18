"""
overlay_panel.py
F12: 멀티 이온 컬로컬라이제이션 오버레이의 R/G/B 채널 선택 패널.

MainWindow의 중앙 레이아웃(이미지/스펙트럼 영역과 ControlsPanel 사이)에
내장되며, 오버레이 모드가 켜져 있을 때만 표시된다(F11 ROI 패널과 동일한
"내장형, 자동 표시/숨김" 패턴). ControlsPanel의 m/z 스핀박스·밝기(Min/Max/Auto)
위젯 패턴을 그대로 재사용한다.

Public methods:
    set_data(n_channels, mz_array, mode)  – 파일 로드 후 스핀박스 범위 설정 + 전체 초기화
    set_channel_minmax(slot, vmin, vmax)  – Auto 클릭 후 프로그램적으로 Min/Max 갱신
    get_channels()                        – R,G,B 순서의 현재 (enabled, idx, vmin, vmax)
Public signals:
    overlay_changed()      – 어느 행이든 값이 바뀌어 재렌더링이 필요할 때
    auto_requested(slot)   – 슬롯(0=R, 1=G, 2=B)의 Auto 버튼 클릭
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QDoubleSpinBox, QPushButton, QGroupBox,
)
from PyQt6.QtCore import pyqtSignal

# 슬롯 순서 R=0, G=1, B=2. F11의 ROI 슬롯 색상과 겹치지 않는, 명확한 R/G/B 계열.
_SLOT_COLORS = ["#f38ba8", "#a6e3a1", "#89b4fa"]
_SLOT_LABELS = ["R", "G", "B"]


class OverlayPanel(QWidget):
    """F12 Overlay Controls: R/G/B 3개 행(체크박스 + 채널 + Min/Max/Auto)."""

    overlay_changed = pyqtSignal()
    auto_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._n_channels = 1
        self._mz_array: np.ndarray | None = None
        self._mode = "continuous"

        # 프로그램적으로 값을 갱신하는 동안 overlay_changed를 억제한다
        # (ControlsPanel._updating과 동일한 역할).
        self._updating = False

        self._checks: list[QCheckBox] = []
        self._unit_labels: list[QLabel] = []
        self._mz_spins: list[QDoubleSpinBox] = []
        self._min_spins: list[QDoubleSpinBox] = []
        self._max_spins: list[QDoubleSpinBox] = []

        self._build_ui()
        # ROI 패널과 동일하게, 오버레이 모드가 켜지기 전까지는 공간을 차지하지 않는다.
        self.setVisible(False)

    # ------------------------------------------------------------------ #
    #  UI 구성
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        group = QGroupBox("Colocalization Overlay  (R / G / B)")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(group)

        rows_layout = QVBoxLayout(group)
        rows_layout.setContentsMargins(6, 4, 6, 4)
        rows_layout.setSpacing(4)

        for slot in range(3):
            row = QHBoxLayout()
            row.setSpacing(6)

            check = QCheckBox(_SLOT_LABELS[slot])
            check.setStyleSheet(
                f"QCheckBox {{ color: {_SLOT_COLORS[slot]}; font-weight: bold; }}"
            )
            check.setToolTip(
                "Include this channel in the Merge pane; "
                "the individual channel pane always remains visible"
            )
            check.toggled.connect(self._on_changed)
            row.addWidget(check)
            self._checks.append(check)

            unit_label = QLabel("m/z:")
            row.addWidget(unit_label)
            self._unit_labels.append(unit_label)

            mz_spin = QDoubleSpinBox()
            mz_spin.setDecimals(4)
            mz_spin.setRange(0.0, 1e7)
            mz_spin.setSingleStep(0.1)
            mz_spin.setFixedWidth(100)
            mz_spin.editingFinished.connect(self._on_changed)
            row.addWidget(mz_spin)
            self._mz_spins.append(mz_spin)

            row.addSpacing(8)
            row.addWidget(QLabel("Min"))
            min_spin = QDoubleSpinBox()
            min_spin.setDecimals(4)
            min_spin.setRange(-1e9, 1e9)
            min_spin.setSingleStep(0.01)
            min_spin.setFixedWidth(80)
            min_spin.valueChanged.connect(self._on_changed)
            row.addWidget(min_spin)
            self._min_spins.append(min_spin)

            row.addWidget(QLabel("Max"))
            max_spin = QDoubleSpinBox()
            max_spin.setDecimals(4)
            max_spin.setRange(-1e9, 1e9)
            max_spin.setSingleStep(0.01)
            max_spin.setFixedWidth(80)
            max_spin.valueChanged.connect(self._on_changed)
            row.addWidget(max_spin)
            self._max_spins.append(max_spin)

            auto_btn = QPushButton("Auto")
            auto_btn.setFixedWidth(46)
            auto_btn.setToolTip(
                "Auto-adjust this channel to 2%\u201398% percentile"
            )
            auto_btn.clicked.connect(
                lambda _checked=False, s=slot: self.auto_requested.emit(s)
            )
            row.addWidget(auto_btn)

            row.addStretch()
            rows_layout.addLayout(row)

    # ------------------------------------------------------------------ #
    #  외부 API
    # ------------------------------------------------------------------ #

    def set_data(self, n_channels: int, mz_array: np.ndarray, mode: str = "continuous"):
        """파일 로드 후 스핀박스 범위를 설정하고 세 행 모두 빈 기본값으로 초기화한다."""
        self._n_channels = n_channels
        self._mz_array = mz_array
        self._mode = mode
        is_tiff = (mode == "tiff")
        unit_text = "Ch:" if is_tiff else "m/z:"

        self._updating = True
        for slot in range(3):
            # v0.3.5: the 4-pane view starts with all three colors included
            # in Merge. Individual R/G/B panes remain visible regardless.
            self._checks[slot].setChecked(True)
            self._unit_labels[slot].setText(unit_text)

            spin = self._mz_spins[slot]
            if mz_array is not None and len(mz_array) > 0:
                spin.setRange(float(mz_array[0]), float(mz_array[-1]))
                spin.setValue(float(mz_array[0]))
                if is_tiff:
                    spin.setDecimals(0)
                    spin.setSingleStep(1.0)
                else:
                    spin.setDecimals(4)
                    spin.setSingleStep(0.1)

            self._min_spins[slot].setValue(0.0)
            self._max_spins[slot].setValue(1.0)
        self._updating = False

    def set_channel_minmax(self, slot: int, vmin: float, vmax: float):
        """Auto 클릭 후 특정 행의 Min/Max를 프로그램적으로 갱신한다."""
        self._updating = True
        self._min_spins[slot].setValue(vmin)
        self._max_spins[slot].setValue(vmax)
        self._updating = False

    def get_channels(self) -> list[tuple[bool, int, float, float]]:
        """R, G, B 순서로 (enabled, channel_idx, vmin, vmax)를 반환한다."""
        result = []
        for slot in range(3):
            enabled = self._checks[slot].isChecked()
            idx = self._channel_index(slot)
            vmin = self._min_spins[slot].value()
            vmax = self._max_spins[slot].value()
            result.append((enabled, idx, vmin, vmax))
        return result

    # ------------------------------------------------------------------ #
    #  내부
    # ------------------------------------------------------------------ #

    def _channel_index(self, slot: int) -> int:
        """행에 입력된 m/z(또는 Ch) 값을 가장 가까운 채널 인덱스로 변환한다."""
        if self._mz_array is None or len(self._mz_array) == 0:
            return 0
        mz_val = self._mz_spins[slot].value()
        return int(np.argmin(np.abs(self._mz_array - mz_val)))

    def _on_changed(self, *_args):
        if self._updating:
            return
        self.overlay_changed.emit()
