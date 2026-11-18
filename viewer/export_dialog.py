"""
export_dialog.py
File → Export Image… 다이얼로그.

사용자가 저장 포맷(PNG / JPG / TIFF)과 스케일 바 옵션을 설정한다.
픽셀 크기(nm/px)가 전달되면 물리 단위(µm / nm) 스케일 바를 지원한다.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QDoubleSpinBox,
    QPushButton, QFrame, QGroupBox,
)
from PyQt6.QtCore import Qt


class ExportDialog(QDialog):
    """
    이미지 내보내기 옵션 다이얼로그.

    Parameters
    ----------
    pixel_size_nm : float | None
        imzML 메타데이터에서 읽은 픽셀 크기(nm/pixel).
        None이면 사용자가 직접 입력해야 한다.

    result_data() -> tuple:
        (format_str, scalebar_on, scalebar_length, unit, pixel_size_um, position)
        - format_str    : 'PNG' | 'JPG' | 'TIFF'
        - scalebar_on   : bool
        - scalebar_length : float  (선택한 단위 기준 길이)
        - unit          : 'µm' | 'nm' | 'px'
        - pixel_size_um : float | None  (µm/pixel, unit이 px이면 None)
        - position      : 'bottom-right' | 'bottom-left'
    """

    def __init__(self, parent=None, pixel_size_nm: float | None = None):
        super().__init__(parent)
        self.setWindowTitle("Export Image")
        self.setFixedWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # nm → µm 변환값 보관 (자동 채우기용)
        self._auto_pixel_size_um = (pixel_size_nm / 1000.0) if pixel_size_nm is not None else None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        # ── 포맷 선택 ────────────────────────────────────────────────────
        fmt_group = QGroupBox("Format")
        fmt_layout = QFormLayout(fmt_group)
        fmt_layout.setContentsMargins(8, 6, 8, 6)

        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["PNG", "JPG", "TIFF"])
        fmt_layout.addRow("File type:", self._fmt_combo)
        layout.addWidget(fmt_group)

        # ── 스케일 바 옵션 ───────────────────────────────────────────────
        sb_group = QGroupBox("Scale Bar")
        sb_layout = QFormLayout(sb_group)
        sb_layout.setContentsMargins(8, 6, 8, 6)
        sb_layout.setSpacing(6)

        self._sb_check = QCheckBox("Add scale bar")
        self._sb_check.setChecked(False)
        self._sb_check.toggled.connect(self._on_scalebar_toggled)
        sb_layout.addRow(self._sb_check)

        # 단위 선택
        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["µm", "nm", "px"])
        self._unit_combo.setEnabled(False)
        self._unit_combo.currentTextChanged.connect(self._on_unit_changed)
        sb_layout.addRow("Unit:", self._unit_combo)

        # 스케일 바 길이
        self._sb_length = QDoubleSpinBox()
        self._sb_length.setDecimals(1)
        self._sb_length.setRange(0.1, 1e6)
        self._sb_length.setValue(500.0)
        self._sb_length.setEnabled(False)
        sb_layout.addRow("Length:", self._sb_length)

        # 픽셀 크기 (µm/px)
        self._px_size_label = QLabel("Pixel size (µm/px):")
        self._px_size_spin = QDoubleSpinBox()
        self._px_size_spin.setDecimals(4)
        self._px_size_spin.setRange(0.0001, 1e6)
        self._px_size_spin.setSingleStep(1.0)
        self._px_size_spin.setEnabled(False)

        if self._auto_pixel_size_um is not None:
            self._px_size_spin.setValue(self._auto_pixel_size_um)
            self._px_size_label.setToolTip("Auto-read from imzML metadata")
        else:
            self._px_size_spin.setValue(50.0)
            self._px_size_label.setToolTip("Not found in imzML — enter manually")

        sb_layout.addRow(self._px_size_label, self._px_size_spin)

        # 위치
        self._sb_pos = QComboBox()
        self._sb_pos.addItems(["bottom-right", "bottom-left"])
        self._sb_pos.setEnabled(False)
        sb_layout.addRow("Position:", self._sb_pos)

        layout.addWidget(sb_group)

        # 자동 읽기 안내 레이블
        if self._auto_pixel_size_um is not None:
            info = QLabel(f"Pixel size auto-read: {self._auto_pixel_size_um:.4f} µm/px")
            info.setStyleSheet("color: #6c7086; font-size: 10px;")
            layout.addWidget(info)
        else:
            info = QLabel("Pixel size not found in imzML — enter manually.")
            info.setStyleSheet("color: #e06c75; font-size: 10px;")
            layout.addWidget(info)

        # ── 구분선 ────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # ── 버튼 ─────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(72)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Export")
        ok_btn.setFixedWidth(72)
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ #

    def _on_scalebar_toggled(self, checked: bool):
        self._unit_combo.setEnabled(checked)
        self._sb_length.setEnabled(checked)
        self._sb_pos.setEnabled(checked)
        unit = self._unit_combo.currentText()
        self._px_size_spin.setEnabled(checked and unit != "px")
        self._px_size_label.setEnabled(checked and unit != "px")

    def _on_unit_changed(self, unit: str):
        is_physical = unit != "px"
        self._px_size_spin.setEnabled(is_physical and self._sb_check.isChecked())
        self._px_size_label.setEnabled(is_physical and self._sb_check.isChecked())

        # 단위에 따라 기본 길이와 step 조정
        if unit == "µm":
            self._sb_length.setDecimals(1)
            self._sb_length.setSingleStep(50.0)
            if self._sb_length.value() < 1:
                self._sb_length.setValue(500.0)
            # pixel size 라벨 업데이트
            self._px_size_label.setText("Pixel size (µm/px):")
            if self._auto_pixel_size_um is not None:
                self._px_size_spin.setValue(self._auto_pixel_size_um)
        elif unit == "nm":
            self._sb_length.setDecimals(0)
            self._sb_length.setSingleStep(500.0)
            if self._sb_length.value() < 100:
                self._sb_length.setValue(500000.0)
            self._px_size_label.setText("Pixel size (nm/px):")
            if self._auto_pixel_size_um is not None:
                self._px_size_spin.setValue(self._auto_pixel_size_um * 1000.0)
        else:  # px
            self._sb_length.setDecimals(0)
            self._sb_length.setSingleStep(10.0)
            self._sb_length.setValue(50.0)
            self._px_size_label.setText("Pixel size (µm/px):")

    def result_data(self) -> tuple:
        """선택된 옵션을 반환한다."""
        unit = self._unit_combo.currentText()
        pixel_size_um = None
        if unit == "µm":
            pixel_size_um = self._px_size_spin.value()
        elif unit == "nm":
            # nm/px → µm/px 변환
            pixel_size_um = self._px_size_spin.value() / 1000.0

        return (
            self._fmt_combo.currentText(),
            self._sb_check.isChecked(),
            self._sb_length.value(),
            unit,
            pixel_size_um,
            self._sb_pos.currentText(),
        )
