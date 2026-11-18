"""
image_viewer.py
QGraphicsView for displaying ion images.

Mouse controls:
  - Scroll wheel        : Zoom in/out
  - Shift + Scroll wheel : Step m/z channel (up = -1, down = +1)
  - Left-click drag     : Pan (move image)
  - Right-click drag    : Brightness/contrast (ITK-SNAP style)
                          up/down (dy) → brightness (window center shift)
                          left/right (dx) → contrast (window width scale)
  - Double-click        : Reset zoom
  - Shift + Left-click  : Select pixel → show spectrum + crosshair
  - Shift + Left-drag   : Select ROI box → show ROI mean spectrum
  - Ctrl + Left-drag    : Draw line → show spatial intensity profile
"""

from __future__ import annotations

import numpy as np
from skimage.measure import profile_line
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsSimpleTextItem,
)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QCursor, QPen, QColor, QBrush


def _make_lut(name: str) -> np.ndarray:
    """
    Returns a (256, 3) uint8 RGB look-up table for the given colormap name.
    viridis / hot / inferno are approximated without matplotlib.
    """
    t = np.linspace(0.0, 1.0, 256)

    if name == "gray":
        v = (t * 255).astype(np.uint8)
        return np.stack([v, v, v], axis=1)

    elif name == "viridis":
        # Approximate: purple → blue → teal → green → yellow
        r = np.interp(t, [0, 0.25, 0.5, 0.75, 1.0], [68,  59,  33, 94, 253])
        g = np.interp(t, [0, 0.25, 0.5, 0.75, 1.0], [1,   82, 145, 201, 231])
        b = np.interp(t, [0, 0.25, 0.5, 0.75, 1.0], [84, 139, 140,  98,  37])

    elif name == "hot":
        # black → red → orange → yellow → white
        r = np.interp(t, [0, 1/3, 2/3, 1.0], [0, 255, 255, 255])
        g = np.interp(t, [0, 1/3, 2/3, 1.0], [0,   0, 255, 255])
        b = np.interp(t, [0, 1/3, 2/3, 1.0], [0,   0,   0, 255])

    elif name == "inferno":
        # Approximate: black → purple → orange → yellow
        r = np.interp(t, [0, 0.33, 0.66, 1.0], [0, 120, 229, 252])
        g = np.interp(t, [0, 0.33, 0.66, 1.0], [0,  28,  97, 255])
        b = np.interp(t, [0, 0.33, 0.66, 1.0], [4, 109,  19,  83])

    else:
        # Unknown colormap → fallback to gray
        v = (t * 255).astype(np.uint8)
        return np.stack([v, v, v], axis=1)

    return np.stack([
        np.clip(r, 0, 255).astype(np.uint8),
        np.clip(g, 0, 255).astype(np.uint8),
        np.clip(b, 0, 255).astype(np.uint8),
    ], axis=1)


def array_to_qimage(arr: np.ndarray, vmin: float, vmax: float, lut: np.ndarray) -> QImage:
    """
    Converts a float32 2D array (H, W) to a QImage (RGB888).
    Maps vmin~vmax to 0~255 and applies the LUT (256×3).
    """
    H, W = arr.shape

    span = vmax - vmin if vmax > vmin else 1.0
    scaled = np.clip((arr - vmin) / span * 255.0, 0, 255).astype(np.uint8)

    rgb = lut[scaled]  # (H, W, 3)

    rgb_contiguous = np.ascontiguousarray(rgb)
    return QImage(
        rgb_contiguous.data,
        W, H,
        W * 3,
        QImage.Format.Format_RGB888,
    ).copy()  # .copy() prevents numpy buffer lifetime issues


def rgb_to_qimage(rgb: np.ndarray) -> QImage:
    """Convert a contiguous (H, W, 3) uint8 RGB array to an owned QImage."""
    H, W, _ = rgb.shape
    rgb_contiguous = np.ascontiguousarray(rgb)
    return QImage(
        rgb_contiguous.data,
        W, H,
        W * 3,
        QImage.Format.Format_RGB888,
    ).copy()


class ImageViewer(QGraphicsView):
    """
    QGraphicsView for displaying ion images.
    Communicates with MainWindow via signals.
    """

    # Emitted when Shift+click selects a pixel (row, col)
    pixel_clicked = pyqtSignal(int, int)

    # Emitted when brightness/contrast changes via right-click drag (vmin, vmax)
    brightness_changed = pyqtSignal(float, float)

    # Emitted when Shift+drag selects an ROI box (r0, r1, c0, c1) — 0-based, inclusive
    roi_selected = pyqtSignal(int, int, int, int)

    # Emitted once when a new Ctrl+drag line is committed and assigned a slot (0-based)
    line_added = pyqtSignal(int, int, int, int, int)  # slot, r0, c0, r1, c1

    # Emitted when a line profile is (re)computed — on creation and on every
    # subsequent channel/normalization/bin change (slot, distances, intensities)
    line_profile_ready = pyqtSignal(int, np.ndarray, np.ndarray)

    # Emitted when a 6th line is attempted while 5 are already active
    line_limit_reached = pyqtSignal()

    # Emitted on Shift+wheel to request a channel step (+1 / -1)
    channel_step = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Scene / pixmap item
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        # View options
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)

        # Crosshair overlays. Pane 0 is also used by the normal single-image
        # view; panes 1–3 are shown only by the 2×2 colocalization view.
        crosshair_pen = QPen(QColor(255, 214, 10, 220))
        crosshair_pen.setWidth(1)
        crosshair_pen.setCosmetic(True)  # stays 1px regardless of zoom level
        self._crosshair_items: list[
            tuple[QGraphicsLineItem, QGraphicsLineItem]
        ] = []
        for _pane in range(4):
            horizontal = QGraphicsLineItem()
            vertical = QGraphicsLineItem()
            horizontal.setPen(crosshair_pen)
            vertical.setPen(crosshair_pen)
            horizontal.setVisible(False)
            vertical.setVisible(False)
            horizontal.setZValue(4)
            vertical.setZValue(4)
            self._scene.addItem(horizontal)
            self._scene.addItem(vertical)
            self._crosshair_items.append((horizontal, vertical))

        # 드래그 중에만 보이는 중립색 ROI 프리뷰.
        # 확정된 ROI는 아래의 고정 슬롯 오버레이가 담당한다.
        roi_pen = QPen(QColor(205, 214, 244, 200))
        roi_pen.setWidth(1)
        roi_pen.setCosmetic(True)
        roi_pen.setStyle(Qt.PenStyle.DashLine)
        self._roi_rect_item = QGraphicsRectItem()
        self._roi_rect_item.setPen(roi_pen)
        self._roi_rect_item.setBrush(QBrush(QColor(205, 214, 244, 40)))
        self._roi_rect_item.setVisible(False)
        self._roi_rect_item.setZValue(2)
        self._scene.addItem(self._roi_rect_item)

        # MainWindow가 소유하는 최대 5개 ROI를 그리는 고정 슬롯.
        # 매번 graphics item을 생성/삭제하지 않고 좌표와 표시 상태만 바꾼다.
        self._roi_overlay_items: list[
            list[tuple[QGraphicsRectItem, QGraphicsSimpleTextItem]]
        ] = [[] for _pane in range(4)]
        roi_colors = ["#f38ba8", "#a6e3a1", "#fab387", "#f9e2af", "#cba6f7"]
        for pane in range(4):
            for slot, color_hex in enumerate(roi_colors):
                color = QColor(color_hex)
                slot_pen = QPen(color)
                slot_pen.setWidth(1)
                slot_pen.setCosmetic(True)

                rect_item = QGraphicsRectItem()
                rect_item.setPen(slot_pen)
                fill = QColor(color)
                fill.setAlpha(76)  # 약 30% 투명도
                rect_item.setBrush(QBrush(fill))
                rect_item.setVisible(False)
                rect_item.setZValue(1)
                self._scene.addItem(rect_item)

                label_item = QGraphicsSimpleTextItem(str(slot + 1))
                label_item.setBrush(QBrush(color))
                font = label_item.font()
                font.setPixelSize(15)
                label_item.setFont(font)
                # ROI 번호는 데이터가 아닌 UI 표식이므로 이미지 해상도와 줌에
                # 영향받지 않는 일정한 화면 크기로 유지한다.
                label_item.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                    True,
                )
                label_item.setVisible(False)
                label_item.setZValue(3)
                self._scene.addItem(label_item)
                self._roi_overlay_items[pane].append((rect_item, label_item))

        # 드래그 중에만 보이는 라인 프로파일 프리뷰.
        # 확정된 라인은 아래의 고정 슬롯 오버레이가 담당한다.
        line_preview_pen = QPen(QColor(0, 212, 255, 230))
        line_preview_pen.setWidth(2)
        line_preview_pen.setCosmetic(True)
        self._line_preview_item = QGraphicsLineItem()
        self._line_preview_item.setPen(line_preview_pen)
        self._line_preview_item.setVisible(False)
        # ROI 채움 위에서도 라인이 선명하게 보이도록 한다.
        self._line_preview_item.setZValue(4)
        self._scene.addItem(self._line_preview_item)

        # ImageViewer가 직접 소유하는 최대 5개 라인 프로파일을 그리는 고정 슬롯
        # (F11의 ROI 오버레이와 동일한 "미리 생성 후 재사용" 패턴). F15는 F11과
        # 달리 슬롯별 다른 색이 아니라 모두 같은 cyan을 쓰고, 번호 라벨로만 구분한다.
        self._line_overlay_items: list[
            list[tuple[QGraphicsLineItem, QGraphicsSimpleTextItem]]
        ] = [[] for _pane in range(4)]
        line_color = QColor(0, 212, 255, 230)
        for pane in range(4):
            for slot in range(5):
                slot_pen = QPen(line_color)
                slot_pen.setWidth(2)
                slot_pen.setCosmetic(True)

                line_item = QGraphicsLineItem()
                line_item.setPen(slot_pen)
                line_item.setVisible(False)
                line_item.setZValue(4)
                self._scene.addItem(line_item)

                label_item = QGraphicsSimpleTextItem(str(slot + 1))
                label_item.setBrush(QBrush(line_color))
                font = label_item.font()
                font.setPixelSize(15)
                label_item.setFont(font)
                # 라인 번호는 데이터가 아닌 UI 표식이므로 이미지 해상도와 줌에
                # 영향받지 않는 일정한 화면 크기로 유지한다.
                label_item.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                    True,
                )
                label_item.setVisible(False)
                label_item.setZValue(4)
                self._scene.addItem(label_item)
                self._line_overlay_items[pane].append((line_item, label_item))

        # State variables
        self._current_image: np.ndarray | None = None  # float32 (H, W)
        self._vmin: float = 0.0
        self._vmax: float = 1.0
        self._colormap_name: str = "gray"
        self._lut: np.ndarray = _make_lut("gray")
        self._img_shape = (0, 0)  # (H, W)

        # F12: 단일 채널 LUT 렌더링("single")과 RGB 합성 렌더링("rgb") 모드 구분.
        # RGB 모드에서는 MainWindow가 이미 정규화까지 끝낸 (H, W, 3) uint8 배열을
        # set_rgb_image()로 그대로 받아 그리며, _vmin/_vmax/_lut는 거치지 않는다.
        self._mode: str = "single"  # "single" | "rgb" | "colocalization"
        self._current_rgb: np.ndarray | None = None
        self._colocalization_rgb: np.ndarray | None = None
        self._grid_gap = 8

        # Annotation coordinates stay in the original image coordinate system.
        # Rendering helpers add the active pane's scene offset.
        self._crosshair_pos: tuple[int, int] | None = None
        self._roi_coords: list[tuple[int, int, int, int] | None] = [None] * 5
        # F12: 오버레이 모드 중에는 라인 프로파일(Ctrl+드래그)만 막는다 — RGB 합성
        # 이미지는 "하나의 채널 값"이 없어 라인을 따라갈 값을 정의할 수 없기 때문.
        # Shift+클릭/드래그(F5/F11)는 전체 스펙트럼 조회라 영향을 받지 않는다.
        self._line_profile_blocked: bool = False

        # Left-click pan state
        self._pan_start: QPointF | None = None

        # Right-click brightness/contrast drag state
        self._rc_drag_start = None
        self._rc_vmin_snap: float = 0.0
        self._rc_vmax_snap: float = 1.0

        # Shift+drag ROI selection state
        self._roi_drag_start: QPointF | None = None
        self._roi_drag_pane: int | None = None

        # 고해상도 휠/트랙패드의 작은 입력을 채널 한 단계 분량까지 누적한다.
        self._channel_wheel_accumulator: float = 0.0
        self._channel_wheel_uses_pixels = False

        # Ctrl+drag line-profile state
        self._line_drag_start: QPointF | None = None
        # slot(0~4) -> (r0, c0, r1, c1); MainWindow가 아닌 ImageViewer가 직접 소유한다.
        self._lines: dict[int, tuple[int, int, int, int]] = {}

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def set_image(self, arr: np.ndarray, vmin: float | None = None, vmax: float | None = None):
        """
        Update the displayed image from a float32 (H, W) array.
        vmin/vmax are kept unchanged if not provided.
        """
        self._current_image = arr
        self._img_shape = arr.shape

        if vmin is not None:
            self._vmin = vmin
        if vmax is not None:
            self._vmax = vmax

        self._redraw()

        # Channel/normalization/bin changes should keep every active line profile in sync.
        for slot in list(self._lines.keys()):
            self._recompute_line_profile(slot)

    def set_vmin_vmax(self, vmin: float, vmax: float):
        """Set brightness/contrast range and redraw."""
        self._vmin = vmin
        self._vmax = vmax
        if self._current_image is not None:
            self._redraw()

    def set_colormap(self, name: str):
        """Change colormap and redraw."""
        if name not in ("gray", "viridis", "hot", "inferno"):
            return
        self._colormap_name = name
        self._lut = _make_lut(name)
        if self._current_image is not None:
            self._redraw()

    def set_rgb_image(self, rgb: np.ndarray):
        """
        F12: MainWindow가 이미 정규화까지 끝낸 (H, W, 3) uint8 RGB 합성 배열을
        그대로 렌더링한다. 단일 채널 LUT/vmin/vmax 경로는 거치지 않는다.
        """
        self._current_rgb = rgb
        self._mode = "rgb"
        self._img_shape = rgb.shape[:2]

        qimg = rgb_to_qimage(rgb)
        self._pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._refresh_annotation_items()

    def set_colocalization_images(
        self,
        red: np.ndarray,
        green: np.ndarray,
        blue: np.ndarray,
        merge: np.ndarray,
    ):
        """
        Display four equally-sized RGB images as Red/Green/Blue/Merge panes.

        A single composed pixmap keeps zoom and pan synchronized automatically.
        Mouse and annotation helpers translate between the composed scene and
        each pane's original image coordinates.
        """
        entering_colocalization = self._mode != "colocalization"
        panes = (red, green, blue, merge)
        if any(pane.shape != red.shape for pane in panes):
            raise ValueError("All colocalization panes must have the same shape.")

        H, W, channels = red.shape
        if channels != 3:
            raise ValueError("Colocalization panes must be RGB arrays.")

        gap = self._grid_gap
        canvas = np.zeros((H * 2 + gap, W * 2 + gap, 3), dtype=np.uint8)
        offsets = self._grid_offsets_for_shape(H, W)
        for pane, (x, y) in zip(panes, offsets):
            canvas[y:y + H, x:x + W] = pane

        # Keep the panes free of text labels so small MSI images are not
        # obscured. Their fixed R/G/B/Merge positions identify each pane.
        qimg = rgb_to_qimage(canvas)
        self._colocalization_rgb = canvas
        self._mode = "colocalization"
        self._img_shape = (H, W)
        self._pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self._refresh_annotation_items()
        if entering_colocalization:
            self.reset_zoom()

    def set_single_mode(self):
        """F12: RGB 합성 모드에서 단일 채널 모드로 되돌린다."""
        leaving_colocalization = self._mode == "colocalization"
        self._mode = "single"
        if self._current_image is not None:
            self._redraw()
        self._refresh_annotation_items()
        if leaving_colocalization:
            self.reset_zoom()

    def set_line_profile_blocked(self, blocked: bool):
        """F12: 오버레이 모드 중 Ctrl+드래그(라인 프로파일 새로 긋기)를 막는다."""
        self._line_profile_blocked = blocked

    def set_crosshair(self, row: int, col: int):
        """Show crosshair lines at the given pixel position (row, col)."""
        H, W = self._img_shape
        if H == 0 or W == 0:
            return
        self._crosshair_pos = (row, col)
        self._layout_crosshair()

    def clear_crosshair(self):
        """Hide the crosshair overlay."""
        self._crosshair_pos = None
        for horizontal, vertical in self._crosshair_items:
            horizontal.setVisible(False)
            vertical.setVisible(False)

    def clear_roi(self):
        """Hide the drag preview and every persistent ROI slot."""
        self._roi_rect_item.setVisible(False)
        self.set_roi_overlays([None] * 5)

    def set_roi_overlays(
        self,
        rois: list[tuple[int, int, int, int] | None],
    ):
        """Render fixed ROI slots; each tuple is (r0, r1, c0, c1), inclusive."""
        self._roi_coords = [
            rois[slot] if slot < len(rois) else None
            for slot in range(5)
        ]
        self._layout_rois()

    def remove_line(self, slot: int):
        """Hide one line slot's overlay + label and forget its coordinates."""
        if slot not in self._lines:
            return
        del self._lines[slot]
        for pane_items in self._line_overlay_items:
            line_item, label_item = pane_items[slot]
            line_item.setVisible(False)
            label_item.setVisible(False)

    def clear_lines(self):
        """Remove every active line profile (called on new file load)."""
        for slot in list(self._lines.keys()):
            self.remove_line(slot)

    def reset_zoom(self):
        """Reset the view to fit the image."""
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def get_vmin_vmax(self):
        return self._vmin, self._vmax

    def get_rendered_image(self) -> np.ndarray | None:
        """
        현재 vmin/vmax/LUT 설정으로 렌더링된 RGB (H, W, 3) uint8 배열을 반환한다.
        이미지가 없으면 None을 반환한다.

        F12: RGB 합성 모드일 때는 이미 화면에 그려지고 있는 합성 배열을 그대로
        반환한다 — File → Export Image가 수정 없이 그대로 동작하는 지점.
        """
        if self._mode == "colocalization":
            return (
                None
                if self._colocalization_rgb is None
                else self._colocalization_rgb.copy()
            )
        if self._mode == "rgb":
            return None if self._current_rgb is None else self._current_rgb.copy()

        if self._current_image is None:
            return None
        qimg = array_to_qimage(self._current_image, self._vmin, self._vmax, self._lut)
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        # bytesPerLine()으로 실제 stride 반영 (Qt는 행을 4바이트 경계로 패딩)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(qimg.height(), qimg.bytesPerLine())
        arr = arr[:, : qimg.width() * 3].reshape(qimg.height(), qimg.width(), 3)
        return arr.copy()

    def is_colocalization_mode(self) -> bool:
        return self._mode == "colocalization"

    def colocalization_merge_rect(self) -> tuple[int, int, int, int] | None:
        """Return Merge pane bounds as (x, y, width, height) in export pixels."""
        if self._mode != "colocalization":
            return None
        H, W = self._img_shape
        return W + self._grid_gap, H + self._grid_gap, W, H

    # ------------------------------------------------------------------ #
    #  Internal rendering
    # ------------------------------------------------------------------ #

    def _grid_offsets_for_shape(self, H: int, W: int) -> list[tuple[int, int]]:
        gap = self._grid_gap
        return [(0, 0), (W + gap, 0), (0, H + gap), (W + gap, H + gap)]

    def _active_pane_offsets(self) -> list[tuple[int, int]]:
        """Scene offsets for visible panes; normal modes use pane zero only."""
        H, W = self._img_shape
        if self._mode == "colocalization":
            return self._grid_offsets_for_shape(H, W)
        return [(0, 0)]

    def _scene_to_image(
        self,
        scene_pos: QPointF,
        required_pane: int | None = None,
        clamp: bool = False,
    ) -> tuple[int, QPointF] | None:
        """Translate scene coordinates to one pane's original image coordinates."""
        H, W = self._img_shape
        if H == 0 or W == 0:
            return None

        offsets = self._active_pane_offsets()
        panes = (
            [required_pane]
            if required_pane is not None and 0 <= required_pane < len(offsets)
            else range(len(offsets))
        )
        for pane in panes:
            x0, y0 = offsets[pane]
            local_x = scene_pos.x() - x0
            local_y = scene_pos.y() - y0
            if 0 <= local_x < W and 0 <= local_y < H:
                return pane, QPointF(local_x, local_y)
            if clamp and required_pane == pane:
                return pane, QPointF(
                    float(np.clip(local_x, 0, max(W - 1e-6, 0))),
                    float(np.clip(local_y, 0, max(H - 1e-6, 0))),
                )
        return None

    def _refresh_annotation_items(self):
        self._layout_crosshair()
        self._layout_rois()
        self._layout_lines()

    def _layout_crosshair(self):
        offsets = self._active_pane_offsets()
        H, W = self._img_shape
        for pane, (horizontal, vertical) in enumerate(self._crosshair_items):
            visible = self._crosshair_pos is not None and pane < len(offsets)
            if not visible:
                horizontal.setVisible(False)
                vertical.setVisible(False)
                continue
            row, col = self._crosshair_pos
            x0, y0 = offsets[pane]
            horizontal.setLine(x0, y0 + row + 0.5, x0 + W, y0 + row + 0.5)
            vertical.setLine(x0 + col + 0.5, y0, x0 + col + 0.5, y0 + H)
            horizontal.setVisible(True)
            vertical.setVisible(True)

    def _layout_rois(self):
        offsets = self._active_pane_offsets()
        for pane, pane_items in enumerate(self._roi_overlay_items):
            for slot, (rect_item, label_item) in enumerate(pane_items):
                roi = self._roi_coords[slot]
                visible = roi is not None and pane < len(offsets)
                if not visible:
                    rect_item.setVisible(False)
                    label_item.setVisible(False)
                    continue
                r0, r1, c0, c1 = roi
                x0, y0 = offsets[pane]
                rect_item.setRect(
                    x0 + c0,
                    y0 + r0,
                    c1 - c0 + 1,
                    r1 - r0 + 1,
                )
                label_item.setPos(x0 + c0 + 0.15, y0 + r0 + 0.05)
                rect_item.setVisible(True)
                label_item.setVisible(True)

    def _layout_lines(self):
        offsets = self._active_pane_offsets()
        for pane, pane_items in enumerate(self._line_overlay_items):
            for slot, (line_item, label_item) in enumerate(pane_items):
                coords = self._lines.get(slot)
                visible = coords is not None and pane < len(offsets)
                if not visible:
                    line_item.setVisible(False)
                    label_item.setVisible(False)
                    continue
                r0, c0, r1, c1 = coords
                x0, y0 = offsets[pane]
                line_item.setLine(
                    x0 + c0 + 0.5,
                    y0 + r0 + 0.5,
                    x0 + c1 + 0.5,
                    y0 + r1 + 0.5,
                )
                label_item.setPos(
                    x0 + (c0 + c1) / 2.0 + 0.15,
                    y0 + (r0 + r1) / 2.0 + 0.05,
                )
                line_item.setVisible(True)
                label_item.setVisible(True)

    def _redraw(self):
        """Render the current image with vmin/vmax/LUT and update the scene."""
        # RGB 합성은 채널별 Min/Max로 이미 렌더링된 배열이다. 단일 채널용
        # 밝기/컬러맵 변경이 뒤에 저장된 _current_image를 덮어쓰지 않게 한다.
        if self._mode != "single" or self._current_image is None:
            return
        qimg = array_to_qimage(self._current_image, self._vmin, self._vmax, self._lut)
        self._pixmap_item.setPixmap(QPixmap.fromImage(qimg))
        self._scene.setSceneRect(self._pixmap_item.boundingRect())

    # ------------------------------------------------------------------ #
    #  Mouse events
    # ------------------------------------------------------------------ #

    def wheelEvent(self, event):
        """Scroll wheel → zoom in/out (centered on cursor position).
        Shift+wheel → step the m/z channel instead (no zoom)."""
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            angle = event.angleDelta()
            # macOS는 Shift+세로 휠을 가로 스크롤 입력으로 바꿀 수 있다.
            delta = angle.y() if angle.y() != 0 else angle.x()
            uses_pixels = False
            threshold = 120.0  # 일반 휠 한 notch

            if delta == 0:
                pixel = event.pixelDelta()
                delta = pixel.y() if pixel.y() != 0 else pixel.x()
                uses_pixels = True
                threshold = 30.0

            if delta == 0:
                event.accept()
                return

            # 자연스러운 스크롤 설정과 관계없이 물리적인 위/아래 방향을 맞춘다.
            step_delta = -delta if event.inverted() else delta

            if uses_pixels != self._channel_wheel_uses_pixels:
                self._channel_wheel_accumulator = 0.0
                self._channel_wheel_uses_pixels = uses_pixels

            self._channel_wheel_accumulator += step_delta
            steps = int(abs(self._channel_wheel_accumulator) // threshold)
            if steps > 0:
                direction = -1 if self._channel_wheel_accumulator > 0 else 1
                self.channel_step.emit(direction * steps)
                self._channel_wheel_accumulator -= (
                    np.sign(self._channel_wheel_accumulator) * steps * threshold
                )
            event.accept()
            return

        self._channel_wheel_accumulator = 0.0
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return

        factor = 1.15 if delta > 0 else 1 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ShiftModifier:
                # Shift+drag: start ROI box selection (finalized on release;
                # a small drag falls back to single-pixel selection there).
                scene_pos = self.mapToScene(event.position().toPoint())
                mapped = self._scene_to_image(scene_pos)
                if mapped is not None:
                    self._roi_drag_pane, self._roi_drag_start = mapped
            elif mods & Qt.KeyboardModifier.ControlModifier and not self._line_profile_blocked:
                # Ctrl+drag: start line-profile drawing (finalized on release).
                # F12: 오버레이(RGB 합성) 모드 중에는 막혀 있으며, 이 경우 그냥
                # 아래 else 분기로 떨어져 일반 팬으로 동작한다.
                self._line_drag_start = self.mapToScene(event.position().toPoint())
                self._line_preview_item.setVisible(False)
            else:
                # Normal left-click: start pan
                self._pan_start = event.position()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

        elif event.button() == Qt.MouseButton.RightButton:
            # RGB 각 채널은 서로 다른 Min/Max를 사용하므로 단일 채널용
            # 우클릭 밝기/대비 조절은 의미가 없다. Overlay Controls를 사용한다.
            if self._mode != "single":
                event.accept()
                return
            # Right-click: start brightness/contrast drag, snapshot current values
            self._rc_drag_start = event.position()
            self._rc_vmin_snap = self._vmin
            self._rc_vmax_snap = self._vmax
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Shift+drag: live-update the ROI box overlay
        if event.buttons() & Qt.MouseButton.LeftButton and self._roi_drag_start is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            mapped = self._scene_to_image(
                scene_pos,
                required_pane=self._roi_drag_pane,
                clamp=True,
            )
            if mapped is not None and self._roi_drag_pane is not None:
                _pane, local_pos = mapped
                x0, y0 = self._active_pane_offsets()[self._roi_drag_pane]
                local_rect = QRectF(self._roi_drag_start, local_pos).normalized()
                self._roi_rect_item.setRect(local_rect.translated(x0, y0))
                self._roi_rect_item.setVisible(True)
            return

        # Ctrl+drag: live-update the line overlay
        if event.buttons() & Qt.MouseButton.LeftButton and self._line_drag_start is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._line_preview_item.setLine(
                self._line_drag_start.x(), self._line_drag_start.y(),
                scene_pos.x(), scene_pos.y(),
            )
            self._line_preview_item.setVisible(True)
            return

        # Left-click pan
        if event.buttons() & Qt.MouseButton.LeftButton and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            return

        # Right-click brightness/contrast
        if event.buttons() & Qt.MouseButton.RightButton and self._rc_drag_start is not None:
            dx = event.position().x() - self._rc_drag_start.x()
            dy = event.position().y() - self._rc_drag_start.y()

            # Sensitivity: 0.5% of current span per pixel
            span = max(self._rc_vmax_snap - self._rc_vmin_snap, 1e-6)
            sensitivity = span * 0.005

            center = (self._rc_vmin_snap + self._rc_vmax_snap) / 2.0
            width = span

            # up/down → brightness (shift window center)
            center -= dy * sensitivity
            # left/right → contrast (scale window width)
            width *= max(1.0 + dx * 0.01, 0.01)

            new_vmin = center - width / 2.0
            new_vmax = center + width / 2.0

            self._vmin = new_vmin
            self._vmax = new_vmax
            self._redraw()
            self.brightness_changed.emit(new_vmin, new_vmax)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._roi_drag_start is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                mapped = self._scene_to_image(
                    scene_pos,
                    required_pane=self._roi_drag_pane,
                    clamp=True,
                )
                if mapped is not None:
                    _pane, end_pos = mapped
                    self._finish_roi_drag(self._roi_drag_start, end_pos)
                else:
                    self._roi_rect_item.setVisible(False)
                self._roi_drag_start = None
                self._roi_drag_pane = None
                return
            if self._line_drag_start is not None:
                end_pos = self.mapToScene(event.position().toPoint())
                self._finish_line_drag(self._line_drag_start, end_pos)
                self._line_drag_start = None
                return
            self._pan_start = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        elif event.button() == Qt.MouseButton.RightButton:
            self._rc_drag_start = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset zoom."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset_zoom()
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------ #
    #  Shift+drag → ROI selection (falls back to single-pixel click)
    # ------------------------------------------------------------------ #

    def _finish_roi_drag(self, start: QPointF, end: QPointF):
        H, W = self._img_shape
        if H == 0 or W == 0:
            self._roi_rect_item.setVisible(False)
            return

        c0f, c1f = sorted((start.x(), end.x()))
        r0f, r1f = sorted((start.y(), end.y()))

        if (c1f - c0f) < 2 and (r1f - r0f) < 2:
            # Effectively a click, not a drag: fall back to single-pixel selection.
            self._roi_rect_item.setVisible(False)
            col = int(end.x())
            row = int(end.y())
            if 0 <= row < H and 0 <= col < W:
                self.set_crosshair(row, col)
                self.pixel_clicked.emit(row, col)
            return

        c0 = int(np.clip(np.floor(c0f), 0, W - 1))
        c1 = int(np.clip(np.ceil(c1f) - 1, 0, W - 1))
        r0 = int(np.clip(np.floor(r0f), 0, H - 1))
        r1 = int(np.clip(np.ceil(r1f) - 1, 0, H - 1))
        c1 = max(c1, c0)
        r1 = max(r1, r0)

        # 확정 여부와 슬롯 배정은 MainWindow가 결정하므로 프리뷰는 즉시 숨긴다.
        self._roi_rect_item.setVisible(False)
        self.roi_selected.emit(r0, r1, c0, c1)

    # ------------------------------------------------------------------ #
    #  Ctrl+drag → line profile
    # ------------------------------------------------------------------ #

    def _finish_line_drag(self, start: QPointF, end: QPointF):
        H, W = self._img_shape
        if H == 0 or W == 0 or self._current_image is None:
            self._line_preview_item.setVisible(False)
            return

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if (dx * dx + dy * dy) ** 0.5 < 2:
            # Too short to be a meaningful line: treat as a mis-click.
            self._line_preview_item.setVisible(False)
            return

        c0 = int(np.clip(start.x(), 0, W - 1))
        r0 = int(np.clip(start.y(), 0, H - 1))
        c1 = int(np.clip(end.x(), 0, W - 1))
        r1 = int(np.clip(end.y(), 0, H - 1))

        # 확정 여부와 슬롯 배정은 아래 _add_line()이 결정하므로 프리뷰는 즉시 숨긴다.
        self._line_preview_item.setVisible(False)
        self._add_line(r0, c0, r1, c1)

    def _add_line(self, r0: int, c0: int, r1: int, c1: int):
        """첫 번째 빈 슬롯(0~4)에 라인을 배정하고 초기 프로파일을 계산/emit한다."""
        slot = next((i for i in range(5) if i not in self._lines), None)
        if slot is None:
            self.line_limit_reached.emit()
            return

        self._lines[slot] = (r0, c0, r1, c1)
        # 현재 모드의 모든 pane에 같은 좌표의 line/label을 배치한다.
        self._layout_lines()

        self.line_added.emit(slot, r0, c0, r1, c1)
        self._recompute_line_profile(slot)

    def _recompute_line_profile(self, slot: int):
        """Recompute the intensity profile along one slot's stored line."""
        coords = self._lines.get(slot)
        if coords is None or self._current_image is None:
            return
        r0, c0, r1, c1 = coords
        profile = profile_line(self._current_image, (r0, c0), (r1, c1), mode="nearest")
        distances = np.arange(len(profile), dtype=np.float64)
        self.line_profile_ready.emit(slot, distances, profile.astype(np.float64))
