"""
spectral_resolution_dialog.py
대용량 imzML 파일 로드 시 채널 수가 임계값을 초과할 경우
load-time 스펙트럼 빈닝 여부를 선택하는 다이얼로그.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QDoubleSpinBox, QPushButton,
    QButtonGroup, QFrame,
)
from PyQt6.QtCore import Qt


class SpectralResolutionDialog(QDialog):
    """
    파일 열기 전 스펙트럴 해상도(채널 수) 옵션을 선택한다.

    사용법:
        dlg = SpectralResolutionDialog(
            parent, mode=mode, n_channels=n,
            mz_min=mz_min, mz_max=mz_max
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            bin_da = dlg.bin_da   # 0.0 = full resolution

    속성:
        bin_da : float   0.0이면 full resolution, 양수면 load-time 빈닝 Da 폭
    """

    def __init__(
        self,
        parent=None,
        *,
        mode: str,
        n_channels: int,
        mz_min: float = 0.0,
        mz_max: float = 0.0,
    ):
        super().__init__(parent)
        self.setWindowTitle("Large File — Spectral Resolution")
        self.setModal(True)
        self.setMinimumWidth(440)

        self._n_channels = n_channels
        self._mz_min = mz_min
        self._mz_max = mz_max
        self.bin_da = 0.0   # 결과 프로퍼티

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        # ── 헤더 ──────────────────────────────────────────────────────
        exact = "estimated " if mode == "processed" else ""
        header = QLabel(
            f"This file contains {exact}<b>{n_channels:,}</b> spectral channels, "
            f"which may cause slow rendering.<br><br>"
            f"Choose how to load the spectrum:"
        )
        header.setWordWrap(True)
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        line1 = _make_hline()
        layout.addWidget(line1)

        # ── 라디오: Full resolution ────────────────────────────────────
        self._btn_group = QButtonGroup(self)

        self._radio_full = QRadioButton(
            f"Full resolution  ({n_channels:,} channels)  — may be slow"
        )
        self._radio_full.setChecked(True)
        self._btn_group.addButton(self._radio_full, 0)
        layout.addWidget(self._radio_full)

        # ── 라디오: Bin at X Da ────────────────────────────────────────
        self._radio_bin = QRadioButton("Bin at")
        self._btn_group.addButton(self._radio_bin, 1)

        bin_row = QHBoxLayout()
        bin_row.setSpacing(6)
        bin_row.addWidget(self._radio_bin)

        self._bin_spin = QDoubleSpinBox()
        self._bin_spin.setDecimals(3)
        self._bin_spin.setRange(0.001, 10.0)
        self._bin_spin.setValue(0.1)
        self._bin_spin.setSingleStep(0.05)
        self._bin_spin.setSuffix(" Da")
        self._bin_spin.setFixedWidth(110)
        self._bin_spin.setEnabled(False)
        self._bin_spin.valueChanged.connect(self._update_preview)
        bin_row.addWidget(self._bin_spin)

        self._preview_label = QLabel()
        self._preview_label.setStyleSheet("color: #888; font-size: 11px;")
        bin_row.addWidget(self._preview_label)
        bin_row.addStretch()

        layout.addLayout(bin_row)

        # 라디오 토글 연결
        self._radio_bin.toggled.connect(self._bin_spin.setEnabled)
        self._radio_bin.toggled.connect(lambda _: self._update_preview())
        self._update_preview()

        line2 = _make_hline()
        layout.addWidget(line2)

        # ── 버튼 ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        load_btn = QPushButton("Load")
        load_btn.setDefault(True)
        load_btn.clicked.connect(self._accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ #

    def _update_preview(self):
        if not self._radio_bin.isChecked():
            self._preview_label.setText("")
            return
        bin_da = self._bin_spin.value()
        mz_range = self._mz_max - self._mz_min
        if mz_range > 0 and bin_da > 0:
            est = max(1, int(mz_range / bin_da))
            self._preview_label.setText(f"≈ {est:,} channels after binning")
        else:
            self._preview_label.setText("")

    def _accept(self):
        if self._radio_bin.isChecked():
            self.bin_da = float(self._bin_spin.value())
        else:
            self.bin_da = 0.0
        self.accept()


def _make_hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line
