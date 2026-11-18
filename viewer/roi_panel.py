"""Compact controls for the active multi-ROI list."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ROIPanel(QWidget):
    """활성 ROI 목록을 표시하고 사용자 조작을 MainWindow로 전달한다."""

    roi_removed = pyqtSignal(int)
    roi_visibility_changed = pyqtSignal(int, bool)
    intensity_mode_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 2, 4, 4)
        self._layout.setSpacing(2)

        mode_row = QWidget()
        mode_layout = QHBoxLayout(mode_row)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.addWidget(QLabel("ROI intensity:"))

        self._intensity_mode = QComboBox()
        self._intensity_mode.addItems(
            ["Mean per pixel", "Total (sum of all pixels)"]
        )
        self._intensity_mode.currentIndexChanged.connect(
            lambda index: self.intensity_mode_changed.emit(index == 0)
        )
        mode_layout.addWidget(self._intensity_mode, stretch=1)
        self._layout.addWidget(mode_row)

        self._rows: list[QWidget] = []
        self.setVisible(False)

    def set_rois(self, rois: list[dict | None], colors: list[str]):
        """MainWindow의 고정 슬롯 상태로 최대 5개의 간단한 행을 다시 만든다."""
        for row in self._rows:
            self._layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        for slot, roi in enumerate(rois):
            if roi is None:
                continue

            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            swatch = QLabel()
            swatch.setFixedSize(12, 12)
            swatch.setStyleSheet(
                f"background-color: {colors[slot]}; border: 1px solid #585b70;"
            )

            label = QLabel(
                f"ROI {slot + 1}  ·  {roi['pixel_count']} px  ·  "
                f"x:{roi['c0']}–{roi['c1']}, y:{roi['r0']}–{roi['r1']}"
            )

            visible = QCheckBox("Visible")
            visible.setChecked(bool(roi["visible"]))
            visible.toggled.connect(
                lambda checked, current_slot=slot:
                self.roi_visibility_changed.emit(current_slot, checked)
            )

            remove = QPushButton("✕")
            remove.setFixedWidth(28)
            remove.setToolTip(f"Remove ROI {slot + 1}")
            remove.clicked.connect(
                lambda _checked=False, current_slot=slot:
                self.roi_removed.emit(current_slot)
            )

            row_layout.addWidget(swatch)
            row_layout.addWidget(label, stretch=1)
            row_layout.addWidget(visible)
            row_layout.addWidget(remove)
            self._layout.addWidget(row)
            self._rows.append(row)

        # ROI가 없을 때는 패널이 레이아웃 공간을 차지하지 않는다.
        self.setVisible(bool(self._rows))

    def mean_per_pixel(self) -> bool:
        return self._intensity_mode.currentIndex() == 0

    def reset(self):
        """새 파일에서 기본값으로 돌아가되 중간 refresh 시그널은 보내지 않는다."""
        self._intensity_mode.blockSignals(True)
        self._intensity_mode.setCurrentIndex(0)
        self._intensity_mode.blockSignals(False)
