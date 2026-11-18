"""
line_profile_panel.py
Ctrl+드래그로 그린 라인을 따라 측정한 공간 강도 프로파일(거리 vs 강도)을
표시하는 작은 pyqtgraph 기반 패널. QDockWidget 안에 배치되어 사용된다.

Public methods:
    set_profile(distances, intensities)  – 라인 프로파일 갱신
    clear()                              – 빈 상태로 초기화
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout


class LineProfilePanel(QWidget):
    """
    거리(px) vs 강도를 보여주는 단일 라인 플롯 위젯.
    스펙트럼 패널과 달리 stem이 아닌 일반 연결선(line)으로 표시한다 —
    공간 프로파일은 연속적인 위치 축이라 stem보다 line이 자연스럽다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._plot = pg.PlotWidget()
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setLabel("bottom", "Distance (px)")
        self._plot.setLabel("left", "Intensity")
        self._plot.setMouseEnabled(x=True, y=True)

        self._curve = self._plot.plot(
            pen=pg.mkPen(color="#00d4ff", width=1.5),
            antialias=True,
        )

        layout.addWidget(self._plot)

    def set_profile(self, distances: np.ndarray, intensities: np.ndarray):
        """라인 프로파일 데이터를 갱신한다."""
        self._curve.setData(x=distances, y=intensities)

    def clear(self):
        """빈 플롯 상태로 되돌린다."""
        self._curve.setData(x=[], y=[])
