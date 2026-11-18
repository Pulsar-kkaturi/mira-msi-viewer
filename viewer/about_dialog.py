"""
about_dialog.py
Help → About MIRA 다이얼로그.

표시 내용:
  - 앱 이름 / 부제(풀네임) / 버전 / 업데이트 날짜
  - 소속 (SNU GSCST / ABEL)
  - 로고 이미지 (assets/ 폴더에서 로드)
  - 간단한 설명
"""

from __future__ import annotations

import os
import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont

# ── 버전 정보 ────────────────────────────────────────────────────────────────
# 버전을 올릴 때는 아래 두 값만 수정하면 됩니다.
# (CHANGELOG.md에 새 항목을 추가한 뒤 여기도 함께 업데이트하세요)
APP_VERSION  = "0.3.5"
APP_UPDATED  = "2026.09.03"
APP_NAME     = "MIRA"
APP_SUBTITLE = "Mass spectrometry Imaging & Review App"


def _assets_dir() -> str:
    """
    실행 환경(소스 직접 실행 vs PyInstaller .app 번들)에 상관없이
    assets 폴더의 절대 경로를 반환한다.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 번들 환경: sys._MEIPASS가 임시 압축 해제 폴더
        base = sys._MEIPASS
    else:
        # 소스 직접 실행: 이 파일 기준으로 상위 폴더의 assets/
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets")


def _load_pixmap(filename: str, max_width: int) -> QPixmap | None:
    """assets/filename 을 로드하고 max_width로 스케일 다운한다. 없으면 None 반환."""
    path = os.path.join(_assets_dir(), filename)
    if not os.path.exists(path):
        return None
    pix = QPixmap(path)
    if pix.isNull():
        return None
    # 가로 max_width 초과 시 비율 유지하며 축소
    if pix.width() > max_width:
        pix = pix.scaledToWidth(max_width, Qt.TransformationMode.SmoothTransformation)
    return pix


class AboutDialog(QDialog):
    """MIRA About 다이얼로그."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        # ── 로고 행 ──────────────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setSpacing(16)
        logo_row.addStretch()

        # SNU GSCST 로고
        snu_pix = _load_pixmap("SNU_GSCST_ENG.png", 160)
        if snu_pix:
            snu_lbl = QLabel()
            snu_lbl.setPixmap(snu_pix)
            snu_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            logo_row.addWidget(snu_lbl)

        # ABEL 로고
        abel_pix = _load_pixmap("ABEL_Logo1.png", 110)
        if abel_pix:
            abel_lbl = QLabel()
            abel_lbl.setPixmap(abel_pix)
            abel_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            logo_row.addWidget(abel_lbl)

        logo_row.addStretch()
        layout.addLayout(logo_row)

        # ── 구분선 ────────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # ── MIRA 브랜드 행 ───────────────────────────────────────────────────
        # 기관 로고 행은 그대로 유지하고, 제품 로고만 앱 이름 옆에 배치한다.
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addStretch()

        mira_pix = _load_pixmap("MIRA-LOGO_v1.png", 58)
        if mira_pix:
            mira_lbl = QLabel()
            mira_lbl.setPixmap(mira_pix)
            mira_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            title_row.addWidget(mira_lbl)

        title_lbl = QLabel(APP_NAME)
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        layout.addLayout(title_row)

        # 풀네임 부제
        subtitle_lbl = QLabel(APP_SUBTITLE)
        subtitle_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_lbl.setStyleSheet("color: #aaa; font-size: 11px; font-style: italic;")
        layout.addWidget(subtitle_lbl)

        # 버전 / 날짜
        ver_lbl = QLabel(f"Version {APP_VERSION}  ·  Updated {APP_UPDATED}")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_lbl.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(ver_lbl)

        # ── 소속 문구 ─────────────────────────────────────────────────────────
        affil_lbl = QLabel(
            "Seoul National University\n"
            "Graduate School of Convergence Science and Technology\n"
            "Applied Bioscience and Engineering Lab (ABEL)"
        )
        affil_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        affil_lbl.setStyleSheet("font-size: 12px; line-height: 1.6;")
        layout.addWidget(affil_lbl)

        # ── 앱 설명 ───────────────────────────────────────────────────────────
        desc_lbl = QLabel(
            "A standalone viewer for Mass Spectrometry Imaging (MSI) data.\n"
            "Supports imzML (Continuous & Processed) and multi-channel TIFF formats."
        )
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # ── 구분선 ────────────────────────────────────────────────────────────
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line2)

        # ── 닫기 버튼 ─────────────────────────────────────────────────────────
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
