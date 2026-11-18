"""
settings_dialog.py
MIRA 환경설정 다이얼로그.

현재 포함 설정:
    Performance → Large-file channel threshold
        채널 수가 이 값을 초과하면 파일 열기 시 SpectralResolutionDialog를 표시한다.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QSpinBox, QPushButton, QGroupBox, QFormLayout,
)
from PyQt6.QtCore import QSettings


SETTINGS_ORG = "ABEL"
SETTINGS_APP = "MSIViewer"
DEFAULT_CHANNEL_THRESHOLD = 5_000


def get_channel_threshold() -> int:
    """QSettings에서 Large-file channel threshold를 읽는다 (기본값 5,000)."""
    s = QSettings(SETTINGS_ORG, SETTINGS_APP)
    return int(s.value("performance/channelThreshold", DEFAULT_CHANNEL_THRESHOLD))


class SettingsDialog(QDialog):
    """MIRA 환경설정 다이얼로그."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.setMinimumWidth(380)

        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        # ── Performance 그룹 ───────────────────────────────────────────
        perf_group = QGroupBox("Performance")
        form = QFormLayout(perf_group)
        form.setSpacing(8)

        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(1_000, 100_000)
        self._threshold_spin.setSingleStep(1_000)
        self._threshold_spin.setValue(
            int(settings.value("performance/channelThreshold", DEFAULT_CHANNEL_THRESHOLD))
        )
        self._threshold_spin.setSuffix(" channels")
        self._threshold_spin.setToolTip(
            "파일을 열 때 채널 수가 이 값을 초과하면\n"
            "스펙트럴 빈닝 여부를 묻는 다이얼로그가 표시됩니다."
        )
        form.addRow("Large-file channel threshold:", self._threshold_spin)
        layout.addWidget(perf_group)

        layout.addStretch()

        # ── 버튼 ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._save_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _save_and_accept(self):
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        s.setValue("performance/channelThreshold", self._threshold_spin.value())
        self.accept()
