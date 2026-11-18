"""
line_profile_dialog.py
F15: 라인 프로파일 1개를 표시하는 비모달(non-modal) 팝업 다이얼로그.

기존 F6의 공유 하단 QDockWidget을 대체한다 — 라인마다 독립된 창을 가지므로
여러 라인을 동시에 비교할 수 있고, 창을 닫는 것 자체가 그 라인의 삭제 동작이 된다.

Public methods:
    set_profile(distances, intensities)  – 라인 프로파일 갱신
Public signals:
    closed(slot: int)                    – 창이 닫힐 때 슬롯 번호와 함께 emit
"""

from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from .line_profile_panel import LineProfilePanel


class LineProfileDialog(QDialog):
    """라인 프로파일 1개 전용 비모달 팝업. 닫히면 closed(slot)을 emit한다."""

    closed = pyqtSignal(int)

    def __init__(self, slot: int, r0: int, c0: int, r1: int, c1: int, parent=None):
        super().__init__(parent)
        self._slot = slot

        self.setWindowTitle(f"Line Profile {slot + 1}")
        # 비모달: MainWindow나 다른 팝업과의 상호작용을 막지 않는다.
        self.setModal(False)
        # 닫힌 뒤에는 MainWindow도 참조를 버리므로, Qt 쪽 객체도 함께 정리한다.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(420, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        length_px = float(np.hypot(c1 - c0, r1 - r0))
        self._coord_label = QLabel(
            f"({c0}, {r0}) → ({c1}, {r1})  ·  length: {length_px:.1f} px"
        )
        self._coord_label.setStyleSheet(
            "color: #a6adc8; font-size: 11px; padding: 2px 4px;"
        )
        layout.addWidget(self._coord_label)

        self._panel = LineProfilePanel()
        layout.addWidget(self._panel)

    def set_profile(self, distances: np.ndarray, intensities: np.ndarray):
        """라인 프로파일 데이터를 갱신한다 (채널/정규화/bin 변경 시 자동 호출됨)."""
        self._panel.set_profile(distances, intensities)

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit(self._slot)
