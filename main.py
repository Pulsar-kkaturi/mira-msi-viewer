"""
main.py
MIRA 진입점.
실행: python main.py
"""

from __future__ import annotations

import sys
import warnings
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from viewer.main_window import MainWindow
from viewer.about_dialog import APP_NAME


MAX_OPEN_WINDOWS = 3
_open_windows: list[MainWindow] = []


def _unregister_window(window: MainWindow):
    """승인되어 닫힌 창의 강한 참조를 레지스트리에서 제거한다."""
    if window in _open_windows:
        _open_windows.remove(window)


def create_window(requester: MainWindow | None = None) -> MainWindow | None:
    """독립 MIRA 창을 만들되 최초 창을 포함해 최대 3개로 제한한다."""
    if len(_open_windows) >= MAX_OPEN_WINDOWS:
        QMessageBox.warning(
            requester,
            "Window Limit",
            "A maximum of 3 MIRA windows can be open at once.",
        )
        return None

    window = MainWindow()
    window.new_window_requested.connect(create_window)
    window.window_closed.connect(_unregister_window)

    # 새 창이 기존 창과 완전히 겹치지 않도록 마지막 창에서 조금 이동한다.
    if _open_windows:
        previous_pos = _open_windows[-1].pos()
        window.move(previous_pos.x() + 30, previous_pos.y() + 30)

    _open_windows.append(window)
    window.show()
    return window


def main():
    # pyimzml 온톨로지 이름 불일치 경고 억제 (라이브러리 내부 이슈)
    warnings.filterwarnings("ignore", category=UserWarning, module="pyimzml")

    # 고해상도(Retina) 디스플레이 지원
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("ABEL")

    # macOS 다크/라이트 모드 자동 적용을 위한 Fusion 스타일 사용
    app.setStyle("Fusion")

    create_window()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
