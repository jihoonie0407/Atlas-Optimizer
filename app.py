"""
AtlasOptimizer - Houdini style
demosaic -> transform (within frame bounds) -> mosaic
"""
VERSION = "1.1.0"

import sys
import math
import numpy as np
from pathlib import Path
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QFileDialog,
    QGroupBox, QCheckBox, QSizePolicy, QStyle, QStyleOptionSlider,
    QMessageBox
)


class JumpSlider(QSlider):
    """Slider that jumps to clicked position instead of stepping"""
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
            handle = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

            if self.orientation() == Qt.Horizontal:
                pos = event.pos().x()
                slider_length = groove.width() - handle.width()
                slider_min = groove.x() + handle.width() // 2
                value = self.minimum() + (self.maximum() - self.minimum()) * (pos - slider_min) / slider_length
            else:
                pos = event.pos().y()
                slider_length = groove.height() - handle.height()
                slider_min = groove.y() + handle.height() // 2
                value = self.maximum() - (self.maximum() - self.minimum()) * (pos - slider_min) / slider_length

            value = max(self.minimum(), min(self.maximum(), int(value)))
            self.setValue(value)
            event.accept()
        super().mousePressEvent(event)
from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPointF
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor, QPainterPath, QIcon

from core.demosaic import demosaic
from core.mosaic import mosaic
from core.stagger import stagger_pack

MIN_PREVIEW = 512

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Segoe UI', 'Malgun Gothic';
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #333;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
    font-size: 13px;
    color: #e8a838;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QPushButton {
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 24px;
    font-size: 12px;
    color: #ccc;
}
QPushButton:hover {
    background: #353535;
    border-color: #e8a838;
    color: #fff;
}
QPushButton:pressed {
    background: #404040;
}
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e8a838, stop:1 #cc8800);
    color: #1a1a1a;
    font-weight: bold;
    font-size: 14px;
    border: none;
    border-radius: 5px;
    min-height: 34px;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffbb44, stop:1 #e89d20);
}
QPushButton#secondary {
    background: #2d2d2d;
    border: 1px solid #444;
    border-radius: 5px;
    font-size: 13px;
    min-height: 30px;
    color: #ddd;
}
QPushButton#secondary:hover {
    background: #3a3a3a;
    border-color: #e8a838;
    color: #fff;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #e8a838;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #ffbb44;
}
QSpinBox {
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 2px 6px;
    min-width: 44px;
    font-size: 12px;
}
QSpinBox:focus {
    border-color: #e8a838;
}
QCheckBox {
    spacing: 4px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #3a3a3a;
    background: #2a2a2a;
}
QCheckBox::indicator:checked {
    background: #e8a838;
    border-color: #b07000;
}
QLabel#info {
    color: #7799cc;
    font-size: 11px;
    padding: 1px 0;
}
"""


class ImagePreview(QWidget):
    """Resizable image preview - fills available space"""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(MIN_PREVIEW, MIN_PREVIEW)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pil_img = None
        self._qpixmap = None
        self._grid = None  # (rows, cols) or None

    def set_image(self, pil_img):
        self.pil_img = pil_img
        if pil_img:
            img = pil_img if pil_img.mode == 'RGBA' else pil_img.convert('RGBA')
            data = img.tobytes('raw', 'RGBA')
            qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            self._qpixmap = QPixmap.fromImage(qimg)
        else:
            self._qpixmap = None
        self.update()

    def set_grid(self, rows, cols):
        """Set grid overlay (rows, cols) or None to disable"""
        self._grid = (rows, cols) if rows and cols else None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Solid dark background
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self._qpixmap is None:
            return  # Empty - just dark background

        # Fit image to widget
        img_w, img_h = self._qpixmap.width(), self._qpixmap.height()
        widget_w, widget_h = self.width(), self.height()

        scale = min(widget_w / img_w, widget_h / img_h)
        disp_w = int(img_w * scale)
        disp_h = int(img_h * scale)
        x = (widget_w - disp_w) // 2
        y = (widget_h - disp_h) // 2

        painter.drawPixmap(x, y, disp_w, disp_h, self._qpixmap)

        # Grid overlay
        if self._grid:
            rows, cols = self._grid
            painter.setPen(QPen(QColor(0, 255, 255, 180), 1))

            cell_w = disp_w / cols
            cell_h = disp_h / rows

            # Vertical lines
            for c in range(1, cols):
                lx = x + int(c * cell_w)
                painter.drawLine(lx, y, lx, y + disp_h)

            # Horizontal lines
            for r in range(1, rows):
                ly = y + int(r * cell_h)
                painter.drawLine(x, ly, x + disp_w, ly)

            # Border
            painter.drawRect(x, y, disp_w, disp_h)

    def _draw_checker(self, painter, rect):
        cs = 12
        c1, c2 = QColor(35, 35, 35), QColor(45, 45, 45)
        for y in range(rect.top(), rect.bottom(), cs):
            for x in range(rect.left(), rect.right(), cs):
                c = c1 if ((x - rect.left()) // cs + (y - rect.top()) // cs) % 2 == 0 else c2
                painter.fillRect(x, y, min(cs, rect.right() - x), min(cs, rect.bottom() - y), c)


class TransformCanvas(QWidget):
    """
    Photoshop-style Free Transform canvas
    - Drag center: move
    - Drag corners: uniform scale
    - Drag edges: axis scale
    - Wheel: uniform scale
    - Shift+drag corner: rotate (future)
    """
    HANDLE_SIZE = 10

    def __init__(self):
        super().__init__()
        self.setMinimumSize(MIN_PREVIEW, MIN_PREVIEW)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self.frame_img = None
        self.frame_size = (256, 256)

        # Transform params
        self.tx = 0.0
        self.ty = 0.0
        self.sx = 1.0  # scale X
        self.sy = 1.0  # scale Y
        self.rotation = 0.0

        # Interaction
        self.dragging = None  # 'move', 'corner_tl', 'corner_tr', 'corner_bl', 'corner_br', 'edge_t', 'edge_b', 'edge_l', 'edge_r'
        self.last_pos = None
        self.on_changed = None

    def set_frame(self, pil_img, frame_size):
        self.frame_img = pil_img
        self.frame_size = frame_size
        self.update()

    def reset_transform(self):
        self.tx = self.ty = 0.0
        self.sx = self.sy = 1.0
        self.rotation = 0.0
        self.update()
        if self.on_changed:
            self.on_changed()

    def get_transform(self):
        return {'tx': self.tx, 'ty': self.ty, 'sx': self.sx, 'sy': self.sy, 'rotation': self.rotation}

    def _get_canvas_rect(self):
        """Get the square canvas area centered in widget"""
        size = min(self.width(), self.height()) - 40
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2
        return QRect(x, y, size, size)

    def _get_crop_rect(self):
        """Get fixed crop bounds rect (final output area)"""
        canvas = self._get_canvas_rect()
        fw, fh = self.frame_size
        fit = min(canvas.width() / fw, canvas.height() / fh) * 0.8

        w = fw * fit
        h = fh * fit
        cx = canvas.center().x()
        cy = canvas.center().y()

        return QRect(int(cx - w/2), int(cy - h/2), int(w), int(h))

    def _get_frame_rect(self):
        """Get transformed frame display rect"""
        canvas = self._get_canvas_rect()
        fw, fh = self.frame_size
        fit = min(canvas.width() / fw, canvas.height() / fh) * 0.8

        w = fw * fit * self.sx
        h = fh * fit * self.sy
        cx = canvas.center().x() + self.tx * fit
        cy = canvas.center().y() + self.ty * fit

        return QRectF(cx - w/2, cy - h/2, w, h), fit

    def _get_handles(self):
        """Return handle rects: corners and edges"""
        frame_rect, _ = self._get_frame_rect()
        hs = self.HANDLE_SIZE
        r = frame_rect

        handles = {
            'corner_tl': QRectF(r.left() - hs/2, r.top() - hs/2, hs, hs),
            'corner_tr': QRectF(r.right() - hs/2, r.top() - hs/2, hs, hs),
            'corner_bl': QRectF(r.left() - hs/2, r.bottom() - hs/2, hs, hs),
            'corner_br': QRectF(r.right() - hs/2, r.bottom() - hs/2, hs, hs),
            'edge_t': QRectF(r.center().x() - hs/2, r.top() - hs/2, hs, hs),
            'edge_b': QRectF(r.center().x() - hs/2, r.bottom() - hs/2, hs, hs),
            'edge_l': QRectF(r.left() - hs/2, r.center().y() - hs/2, hs, hs),
            'edge_r': QRectF(r.right() - hs/2, r.center().y() - hs/2, hs, hs),
        }
        return handles

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Solid dark background
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self.frame_img is None:
            return  # Empty - just dark background

        frame_rect, fit = self._get_frame_rect()
        fw, fh = self.frame_size

        # Crop bounds area - solid black for transparency
        crop_rect = self._get_crop_rect()
        painter.fillRect(crop_rect, QColor(0, 0, 0))

        # Clip to crop bounds (final output area)
        painter.setClipRect(crop_rect)

        # Draw image
        qimg = self._pil_to_qimage(self.frame_img)
        pixmap = QPixmap.fromImage(qimg)

        # Transform and draw
        painter.save()
        painter.translate(frame_rect.center())
        painter.rotate(self.rotation)
        painter.drawPixmap(
            int(-frame_rect.width()/2), int(-frame_rect.height()/2),
            int(frame_rect.width()), int(frame_rect.height()),
            pixmap
        )
        painter.restore()

        painter.setClipping(False)

        # Fixed crop bounds (dashed red) - shows final output area
        crop_rect = self._get_crop_rect()
        pen = QPen(QColor(255, 80, 80, 200), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(crop_rect)

        # Transform frame border (yellow solid)
        painter.setPen(QPen(QColor(255, 200, 0, 200), 2))
        painter.drawRect(frame_rect)

        # Handles
        handles = self._get_handles()
        painter.setBrush(QBrush(QColor(255, 200, 0)))
        painter.setPen(QPen(QColor(50, 50, 50), 1))
        for name, rect in handles.items():
            painter.drawRect(rect)

        # Legend
        painter.setPen(QColor(255, 80, 80))
        painter.drawText(crop_rect.left(), crop_rect.top() - 5, "Crop Bounds")
        painter.setPen(QColor(255, 200, 0))
        painter.drawText(int(frame_rect.left()), int(frame_rect.bottom() + 15), "Transform")

    def _draw_checker(self, painter, rect):
        cs = 12
        c1, c2 = QColor(35, 35, 35), QColor(45, 45, 45)
        for y in range(rect.top(), rect.bottom(), cs):
            for x in range(rect.left(), rect.right(), cs):
                c = c1 if ((x - rect.left()) // cs + (y - rect.top()) // cs) % 2 == 0 else c2
                painter.fillRect(x, y, min(cs, rect.right() - x), min(cs, rect.bottom() - y), c)

    def _pil_to_qimage(self, pil_img):
        if pil_img.mode != 'RGBA':
            pil_img = pil_img.convert('RGBA')
        data = pil_img.tobytes('raw', 'RGBA')
        return QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)

    def _hit_test(self, pos):
        """Check what's under cursor"""
        handles = self._get_handles()
        for name, rect in handles.items():
            if rect.contains(pos):
                return name

        frame_rect, _ = self._get_frame_rect()
        if frame_rect.contains(pos):
            return 'move'

        # Check rotation zone (outside frame but within margin)
        expanded = frame_rect.adjusted(-30, -30, 30, 30)
        if expanded.contains(pos) and not frame_rect.contains(pos):
            return 'rotate'

        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hit = self._hit_test(QPointF(event.pos()))
            if hit:
                self.dragging = hit
                self.last_pos = event.pos()
                self._update_cursor(hit)

    def mouseMoveEvent(self, event):
        if self.dragging and self.last_pos:
            delta = event.pos() - self.last_pos
            frame_rect, fit = self._get_frame_rect()

            if self.dragging == 'move':
                self.tx += delta.x() / fit
                self.ty += delta.y() / fit

            elif self.dragging.startswith('corner'):
                # Uniform scale
                factor = 1.0 + (delta.x() + delta.y()) * 0.005
                self.sx *= factor
                self.sy *= factor
                self.sx = max(0.1, min(5.0, self.sx))
                self.sy = max(0.1, min(5.0, self.sy))

            elif self.dragging == 'edge_l' or self.dragging == 'edge_r':
                # X scale
                factor = 1.0 + delta.x() * 0.005 * (1 if 'r' in self.dragging else -1)
                self.sx *= factor
                self.sx = max(0.1, min(5.0, self.sx))

            elif self.dragging == 'edge_t' or self.dragging == 'edge_b':
                # Y scale
                factor = 1.0 + delta.y() * 0.005 * (1 if 'b' in self.dragging else -1)
                self.sy *= factor
                self.sy = max(0.1, min(5.0, self.sy))

            elif self.dragging == 'rotate':
                # Calculate rotation based on angle from center
                center = frame_rect.center()
                prev_angle = math.atan2(self.last_pos.y() - center.y(), self.last_pos.x() - center.x())
                curr_angle = math.atan2(event.pos().y() - center.y(), event.pos().x() - center.x())
                delta_angle = math.degrees(curr_angle - prev_angle)
                self.rotation += delta_angle
                # Normalize to -180 ~ 180
                while self.rotation > 180:
                    self.rotation -= 360
                while self.rotation < -180:
                    self.rotation += 360

            self.last_pos = event.pos()
            self.update()
            if self.on_changed:
                self.on_changed()
        else:
            # Update cursor on hover
            hit = self._hit_test(QPointF(event.pos()))
            self._update_cursor(hit)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = None
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self.sx = max(0.1, min(5.0, self.sx * factor))
        self.sy = max(0.1, min(5.0, self.sy * factor))
        self.update()
        if self.on_changed:
            self.on_changed()

    def _update_cursor(self, hit):
        if hit == 'move':
            self.setCursor(Qt.SizeAllCursor)
        elif hit in ('corner_tl', 'corner_br'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif hit in ('corner_tr', 'corner_bl'):
            self.setCursor(Qt.SizeBDiagCursor)
        elif hit in ('edge_l', 'edge_r'):
            self.setCursor(Qt.SizeHorCursor)
        elif hit in ('edge_t', 'edge_b'):
            self.setCursor(Qt.SizeVerCursor)
        elif hit == 'rotate':
            self.setCursor(self._get_rotate_cursor())
        else:
            self.setCursor(Qt.ArrowCursor)

    def _get_rotate_cursor(self):
        """Create rotation cursor icon"""
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw rotation arc
        pen = QPen(QColor(255, 200, 0), 2)
        painter.setPen(pen)

        # Arc
        rect = QRectF(4, 4, size - 8, size - 8)
        painter.drawArc(rect, 45 * 16, 270 * 16)

        # Arrow head
        painter.drawLine(size - 6, 8, size - 6, 4)
        painter.drawLine(size - 6, 4, size - 10, 4)

        painter.end()
        return QCursor(pixmap, size // 2, size // 2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AtlasOptimizer")
        self.setMinimumSize(1400, 820)
        self.setStyleSheet(DARK_STYLE)

        self.atlas = None
        self.frames = []
        self._frames_np = []       # Pre-converted numpy float32 arrays (normalized 0-1)
        self._ghost_cache = None   # (cache_key, result_image)
        self.frame_size = (256, 256)
        self.current_frame = 0
        self.is_playing = False
        self.result_atlas = None
        self._stagger_grid = None
        self.original_filename = "result"  # For save dialog
        self.channel_view = {'R': True, 'G': True, 'B': True, 'A': True}  # RGBA channel toggles

        # Resolution presets (power of 2)
        self.res_presets = [128, 256, 512, 1024, 2048, 4096]
        self.res_index = 3  # Default 1024

        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self._next_frame)

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # Fixed heights so all 3 previews are the same size
        TOP_H = 82
        BOT_H = 158

        # === Input Panel ===
        input_panel = QGroupBox("Input (Atlas)")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setSpacing(0)
        input_layout.setContentsMargins(8, 24, 8, 8)

        # Top controls (fixed)
        input_top = QWidget()
        input_top.setFixedHeight(TOP_H)
        input_top_lay = QVBoxLayout(input_top)
        input_top_lay.setSpacing(4)
        input_top_lay.setContentsMargins(0, 0, 0, 0)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Row:"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 16)
        self.rows_spin.setValue(4)
        self.rows_spin.valueChanged.connect(self._on_grid)
        row1.addWidget(self.rows_spin)
        row1.addWidget(QLabel("Col:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 16)
        self.cols_spin.setValue(4)
        self.cols_spin.valueChanged.connect(self._on_grid)
        row1.addWidget(self.cols_spin)
        row1.addStretch()
        input_top_lay.addLayout(row1)
        input_top_lay.addStretch()

        input_layout.addWidget(input_top)

        # Preview
        self.input_preview = ImagePreview()
        input_layout.addWidget(self.input_preview, 1)

        # Bottom (fixed) - Load button + file info
        input_bot = QWidget()
        input_bot.setFixedHeight(BOT_H)
        input_bot_lay = QVBoxLayout(input_bot)
        input_bot_lay.setSpacing(4)
        input_bot_lay.setContentsMargins(0, 4, 0, 0)

        self.load_btn = QPushButton("Load")
        self.load_btn.setObjectName("primary")
        self.load_btn.clicked.connect(self._load)
        input_bot_lay.addWidget(self.load_btn)

        self.file_label = QLabel("No file")
        self.file_label.setObjectName("info")
        input_bot_lay.addWidget(self.file_label)

        self.grid_info = QLabel("")
        self.grid_info.setObjectName("info")
        input_bot_lay.addWidget(self.grid_info)
        input_bot_lay.addStretch()

        input_layout.addWidget(input_bot)

        # === Xform Panel ===
        xform_panel = QGroupBox("Xform (Free Transform)")
        xform_layout = QVBoxLayout(xform_panel)
        xform_layout.setSpacing(0)
        xform_layout.setContentsMargins(8, 24, 8, 8)

        # Top controls (fixed)
        xform_top = QWidget()
        xform_top.setFixedHeight(TOP_H)
        xform_top_lay = QVBoxLayout(xform_top)
        xform_top_lay.setSpacing(4)
        xform_top_lay.setContentsMargins(0, 0, 0, 0)

        ghost_row = QHBoxLayout()
        self.ghost_check = QCheckBox("Ghost")
        self.ghost_check.stateChanged.connect(self._update_canvas)
        ghost_row.addWidget(self.ghost_check)
        ghost_row.addWidget(QLabel("Steps:"))
        self.ghost_steps = QSpinBox()
        self.ghost_steps.setRange(1, 32)
        self.ghost_steps.setValue(5)
        self.ghost_steps.valueChanged.connect(self._update_canvas)
        ghost_row.addWidget(self.ghost_steps)
        ghost_row.addStretch()
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset)
        ghost_row.addWidget(self.reset_btn)
        xform_top_lay.addLayout(ghost_row)

        fit_row = QHBoxLayout()
        self.autofit_btn = QPushButton("Auto Fit")
        self.autofit_btn.clicked.connect(self._auto_fit)
        fit_row.addWidget(self.autofit_btn)
        fit_row.addWidget(QLabel("Pad:"))
        self.padding_slider = JumpSlider(Qt.Horizontal)
        self.padding_slider.setRange(0, 50)
        self.padding_slider.setValue(0)
        self.padding_slider.setFixedWidth(80)
        fit_row.addWidget(self.padding_slider)
        self.padding_label = QLabel("0")
        self.padding_label.setFixedWidth(20)
        self.padding_slider.valueChanged.connect(lambda v: self.padding_label.setText(str(v)))
        fit_row.addWidget(self.padding_label)
        fit_row.addSpacing(8)

        # RGBA channel toggles
        self.channel_btns = {}
        for ch, color in [('R', '#e05050'), ('G', '#50c050'), ('B', '#5080e0'), ('A', '#999999')]:
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #2a2a2a; color: #444; font-size: 10px;
                    font-weight: bold; border: 1px solid #3a3a3a; border-radius: 2px;
                    padding: 0; margin: 0;
                }}
                QPushButton:checked {{
                    background: #383838; color: {color}; border-color: #484848;
                }}
                QPushButton:hover {{ border-color: #555; }}
            """)
            btn.clicked.connect(self._on_channel_toggle)
            fit_row.addWidget(btn)
            self.channel_btns[ch] = btn
        fit_row.addStretch()
        xform_top_lay.addLayout(fit_row)
        xform_top_lay.addStretch()

        xform_layout.addWidget(xform_top)

        # Canvas
        self.canvas = TransformCanvas()
        self.canvas.on_changed = self._on_canvas_changed
        xform_layout.addWidget(self.canvas, 1)

        # Bottom controls (fixed)
        xform_bot = QWidget()
        xform_bot.setFixedHeight(BOT_H)
        xform_bot_lay = QVBoxLayout(xform_bot)
        xform_bot_lay.setSpacing(4)
        xform_bot_lay.setContentsMargins(0, 6, 6, 2)

        LABEL_W = 72
        VAL_W = 40

        # Location X/Y
        loc_row = QHBoxLayout()
        loc_row.addWidget(QLabel("Loc X:"))
        self.lx_slider = JumpSlider(Qt.Horizontal)
        self.lx_slider.setRange(-500, 500)
        self.lx_slider.setValue(0)
        self.lx_slider.valueChanged.connect(self._on_loc_slider)
        loc_row.addWidget(self.lx_slider)
        self.lx_label = QLabel("0")
        self.lx_label.setFixedWidth(VAL_W)
        loc_row.addWidget(self.lx_label)
        loc_row.addSpacing(4)
        loc_row.addWidget(QLabel("Y:"))
        self.ly_slider = JumpSlider(Qt.Horizontal)
        self.ly_slider.setRange(-500, 500)
        self.ly_slider.setValue(0)
        self.ly_slider.valueChanged.connect(self._on_loc_slider)
        loc_row.addWidget(self.ly_slider)
        self.ly_label = QLabel("0")
        self.ly_label.setFixedWidth(VAL_W)
        loc_row.addWidget(self.ly_label)
        xform_bot_lay.addLayout(loc_row)

        # Scale X/Y
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Scale X:"))
        self.sx_slider = JumpSlider(Qt.Horizontal)
        self.sx_slider.setRange(10, 300)
        self.sx_slider.setValue(100)
        self.sx_slider.valueChanged.connect(self._on_scale_slider)
        scale_row.addWidget(self.sx_slider)
        self.sx_label = QLabel("1.00")
        self.sx_label.setFixedWidth(VAL_W)
        scale_row.addWidget(self.sx_label)
        scale_row.addSpacing(4)
        scale_row.addWidget(QLabel("Y:"))
        self.sy_slider = JumpSlider(Qt.Horizontal)
        self.sy_slider.setRange(10, 300)
        self.sy_slider.setValue(100)
        self.sy_slider.valueChanged.connect(self._on_scale_slider)
        scale_row.addWidget(self.sy_slider)
        self.sy_label = QLabel("1.00")
        self.sy_label.setFixedWidth(VAL_W)
        scale_row.addWidget(self.sy_label)
        xform_bot_lay.addLayout(scale_row)

        # Rotation
        rot_row = QHBoxLayout()
        rot_lbl = QLabel("Rotation:")
        rot_lbl.setFixedWidth(LABEL_W)
        rot_row.addWidget(rot_lbl)
        self.rot_slider = JumpSlider(Qt.Horizontal)
        self.rot_slider.setRange(-180, 180)
        self.rot_slider.setValue(0)
        self.rot_slider.valueChanged.connect(self._on_rot_slider)
        rot_row.addWidget(self.rot_slider)
        self.rot_label = QLabel("0\u00b0")
        self.rot_label.setFixedWidth(VAL_W)
        rot_row.addWidget(self.rot_label)
        xform_bot_lay.addLayout(rot_row)

        # Gamma
        gamma_row = QHBoxLayout()
        gamma_lbl = QLabel("Gamma:")
        gamma_lbl.setFixedWidth(LABEL_W)
        gamma_row.addWidget(gamma_lbl)
        self.gamma_slider = JumpSlider(Qt.Horizontal)
        self.gamma_slider.setRange(20, 300)
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self._on_adjust_changed)
        gamma_row.addWidget(self.gamma_slider)
        self.gamma_label = QLabel("1.00")
        self.gamma_label.setFixedWidth(VAL_W)
        gamma_row.addWidget(self.gamma_label)
        xform_bot_lay.addLayout(gamma_row)

        # Timeline
        transport_style = """
            QPushButton { background: #2a2a2a; border: 1px solid #3a3a3a; border-radius: 3px;
                font-size: 11px; font-weight: bold; padding: 0; }
            QPushButton:hover { background: #353535; border-color: #e8a838; }
        """
        tl_row = QHBoxLayout()
        self.prev_btn = QPushButton("|<")
        self.prev_btn.setFixedSize(28, 22)
        self.prev_btn.setStyleSheet(transport_style)
        self.prev_btn.clicked.connect(self._prev_frame)
        tl_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("")
        self.play_btn.setFixedSize(28, 22)
        self._update_play_icon(False)
        self.play_btn.clicked.connect(self._toggle_play)
        tl_row.addWidget(self.play_btn)

        self.next_btn = QPushButton(">|")
        self.next_btn.setFixedSize(28, 22)
        self.next_btn.setStyleSheet(transport_style)
        self.next_btn.clicked.connect(self._next_frame)
        tl_row.addWidget(self.next_btn)

        self.timeline = JumpSlider(Qt.Horizontal)
        self.timeline.valueChanged.connect(self._on_timeline)
        tl_row.addWidget(self.timeline)

        self.frame_label = QLabel("0/0")
        self.frame_label.setFixedWidth(50)
        tl_row.addWidget(self.frame_label)
        xform_bot_lay.addLayout(tl_row)

        xform_layout.addWidget(xform_bot)

        # === Result Panel ===
        result_panel = QGroupBox("Result (Atlas)")
        result_layout = QVBoxLayout(result_panel)
        result_layout.setSpacing(0)
        result_layout.setContentsMargins(8, 24, 8, 8)

        # Top controls (fixed)
        result_top = QWidget()
        result_top.setFixedHeight(TOP_H)
        result_top_lay = QVBoxLayout(result_top)
        result_top_lay.setSpacing(4)
        result_top_lay.setContentsMargins(0, 0, 0, 0)

        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Size:"))
        self.res_down_btn = QPushButton("\u2212")
        self.res_down_btn.setFixedSize(20, 20)
        self.res_down_btn.setStyleSheet("QPushButton { font-size: 13px; font-weight: bold; padding: 0; }")
        self.res_down_btn.clicked.connect(self._res_down)
        res_row.addWidget(self.res_down_btn)
        self.res_label = QLabel("1024")
        self.res_label.setFixedWidth(46)
        self.res_label.setAlignment(Qt.AlignCenter)
        self.res_label.setStyleSheet("font-weight: bold; color: #e8a838; font-size: 14px;")
        res_row.addWidget(self.res_label)
        self.res_up_btn = QPushButton("+")
        self.res_up_btn.setFixedSize(20, 20)
        self.res_up_btn.setStyleSheet("QPushButton { font-size: 13px; font-weight: bold; padding: 0; }")
        self.res_up_btn.clicked.connect(self._res_up)
        res_row.addWidget(self.res_up_btn)
        res_row.addStretch()
        self.grid_check = QCheckBox("Grid")
        self.grid_check.stateChanged.connect(self._toggle_grid)
        res_row.addWidget(self.grid_check)
        result_top_lay.addLayout(res_row)

        # RGBA channel toggles for result preview
        res_ch_row = QHBoxLayout()
        res_ch_row.addStretch()
        self.result_channel_btns = {}
        for ch, color in [('R', '#e05050'), ('G', '#50c050'), ('B', '#5080e0'), ('A', '#999999')]:
            btn = QPushButton(ch)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setFixedSize(20, 20)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #2a2a2a; color: #444; font-size: 10px;
                    font-weight: bold; border: 1px solid #3a3a3a; border-radius: 2px;
                    padding: 0; margin: 0;
                }}
                QPushButton:checked {{
                    background: #383838; color: {color}; border-color: #484848;
                }}
                QPushButton:hover {{ border-color: #555; }}
            """)
            btn.clicked.connect(self._on_result_channel_toggle)
            res_ch_row.addWidget(btn)
            self.result_channel_btns[ch] = btn
        result_top_lay.addLayout(res_ch_row)
        result_top_lay.addStretch()

        result_layout.addWidget(result_top)

        # Preview
        self.result_preview = ImagePreview()
        result_layout.addWidget(self.result_preview, 1)

        # Bottom (fixed)
        result_bot = QWidget()
        result_bot.setFixedHeight(BOT_H)
        result_bot_lay = QVBoxLayout(result_bot)
        result_bot_lay.setSpacing(4)
        result_bot_lay.setContentsMargins(0, 4, 0, 0)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.mosaic_btn = QPushButton("Optimize")
        self.mosaic_btn.setObjectName("primary")
        self.mosaic_btn.clicked.connect(self._mosaic)
        self.stagger_btn = QPushButton("Stagger")
        self.stagger_btn.setObjectName("primary")
        self.stagger_btn.clicked.connect(self._stagger)
        btn_row.addWidget(self.mosaic_btn)
        btn_row.addWidget(self.stagger_btn)
        result_bot_lay.addLayout(btn_row)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("secondary")
        self.save_btn.clicked.connect(self._save)
        result_bot_lay.addWidget(self.save_btn)

        self.result_info = QLabel("")
        self.result_info.setObjectName("info")
        result_bot_lay.addWidget(self.result_info)
        result_bot_lay.addStretch()

        ver_label = QLabel(f"v{VERSION}  jihoonie0407")
        ver_label.setAlignment(Qt.AlignRight)
        ver_label.setStyleSheet("color: #555; font-size: 10px;")
        result_bot_lay.addWidget(ver_label)

        result_layout.addWidget(result_bot)

        # Equal width panels
        main_layout.addWidget(input_panel, 1)
        main_layout.addWidget(xform_panel, 1)
        main_layout.addWidget(result_panel, 1)

    def _load(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Load", "", "Images (*.png *.jpg *.tga);;All (*)")
        if not paths:
            return

        # Reset all settings
        self._reset()
        self.result_atlas = None
        self._stagger_grid = None
        self.result_preview.set_image(None)
        self.result_info.setText("")

        try:
            if len(paths) == 1:
                # Single file → Atlas mode
                self.atlas = Image.open(paths[0]).convert('RGBA')
                self.input_preview.set_image(self.atlas)
                self.file_label.setText(f"{Path(paths[0]).name}\n{self.atlas.width}x{self.atlas.height}")
                self.original_filename = Path(paths[0]).stem

                self._auto_detect_grid()
                self._do_demosaic()
            else:
                # Multiple files → Sequence mode
                paths = sorted(paths)
                imgs = []
                for p in paths:
                    try:
                        imgs.append(Image.open(p).convert('RGBA'))
                    except Exception:
                        QMessageBox.warning(self, "Load Error",
                            f"Failed to load: {Path(p).name}\n\n"
                            "Supported formats: PNG, JPG, TGA\n"
                            "Make sure all files are valid images.")
                        return

                if len(imgs) < 2:
                    return

                # Validate: all frames must be same size
                first_size = imgs[0].size
                bad = [Path(paths[i]).name for i, im in enumerate(imgs) if im.size != first_size]
                if bad:
                    QMessageBox.warning(self, "Size Mismatch",
                        f"All frames must be the same size ({first_size[0]}x{first_size[1]}).\n\n"
                        f"Mismatched files:\n" + "\n".join(bad[:5]) +
                        (f"\n... and {len(bad)-5} more" if len(bad) > 5 else ""))
                    return

                self.frames = imgs
                self.frame_size = first_size
                self._frames_np = [np.array(f, dtype=np.float32) / 255.0 for f in self.frames]
                self._ghost_cache = None
                self.current_frame = 0

                # Auto grid: √N square
                n = len(self.frames)
                cols = math.ceil(math.sqrt(n))
                rows = math.ceil(n / cols)

                self.rows_spin.blockSignals(True)
                self.cols_spin.blockSignals(True)
                self.rows_spin.setValue(rows)
                self.cols_spin.setValue(cols)
                self.rows_spin.blockSignals(False)
                self.cols_spin.blockSignals(False)

                # Pad with empty frames if needed (rows*cols > n)
                total = rows * cols
                while len(self.frames) < total:
                    empty = Image.new('RGBA', self.frame_size, (0, 0, 0, 0))
                    self.frames.append(empty)
                    self._frames_np.append(np.zeros((*self.frame_size[::-1], 4), dtype=np.float32))

                # Build atlas from sequence for input preview
                self.atlas = mosaic(self.frames, rows, cols)
                self.input_preview.set_image(self.atlas)
                fw, fh = self.frame_size
                self.file_label.setText(f"Sequence {n} files\n{fw}x{fh} per frame")
                self.original_filename = Path(paths[0]).stem.rstrip('0123456789_.- ')
                if not self.original_filename:
                    self.original_filename = "sequence"

                self.timeline.setRange(0, max(0, len(self.frames) - 1))
                self.grid_info.setText(f"{len(self.frames)} frames | {fw}x{fh}")
        except Exception as e:
            QMessageBox.warning(self, "Load Error",
                f"Failed to load image:\n{e}")
            return

        # Auto fit immediately
        self._auto_fit()

    def _auto_detect_grid(self):
        """Auto-detect grid by analyzing content clustering in each potential cell"""
        if not self.atlas:
            return

        w, h = self.atlas.size
        arr = np.array(self.atlas, dtype=np.float32)

        # Check if image has meaningful alpha channel
        has_alpha = np.any(arr[:, :, 3] < 250)

        if has_alpha:
            content = arr[:, :, 3]
        else:
            content = np.max(arr[:, :, :3], axis=2)

        # Normalize
        if np.max(content) > 0:
            content = content / np.max(content)

        best_rows, best_cols = 4, 4
        best_score = -1

        # Try common grid configurations
        candidates = []
        for rows in [2, 3, 4, 5, 6, 7, 8, 10, 12, 16]:
            for cols in [2, 3, 4, 5, 6, 7, 8, 10, 12, 16]:
                if h % rows == 0 and w % cols == 0:
                    candidates.append((rows, cols))

        for rows, cols in candidates:
            frame_h = h // rows
            frame_w = w // cols

            cells_with_content = 0
            total_center_vs_edge = 0

            for r in range(rows):
                for c in range(cols):
                    y1, y2 = r * frame_h, (r + 1) * frame_h
                    x1, x2 = c * frame_w, (c + 1) * frame_w
                    cell = content[y1:y2, x1:x2]

                    # Check if cell has content
                    if np.mean(cell) > 0.01:
                        cells_with_content += 1

                    # Analyze center vs edge - correct grid has high center, low edges
                    margin = max(2, min(frame_w, frame_h) // 8)  # 12.5% margin

                    # Edge region (outer ring)
                    edge_mask = np.ones_like(cell, dtype=bool)
                    edge_mask[margin:-margin, margin:-margin] = False
                    edge_content = np.mean(cell[edge_mask]) if np.any(edge_mask) else 0

                    # Center region (inner area)
                    center = cell[margin:-margin, margin:-margin]
                    center_content = np.mean(center) if center.size > 0 else 0

                    # Ratio: high center / low edge = correct boundary
                    if edge_content > 0.001:
                        ratio = center_content / (edge_content + 0.001)
                    else:
                        ratio = center_content * 100 if center_content > 0.01 else 0
                    total_center_vs_edge += min(ratio, 50)  # cap at 50

            total_cells = rows * cols
            content_ratio = cells_with_content / total_cells
            avg_center_vs_edge = total_center_vs_edge / total_cells

            # Skip if too few cells have content
            if content_ratio < 0.3:
                continue

            # Score components
            score = 0

            # Content ratio - prefer more cells with content
            score += content_ratio * 30

            # Center vs edge ratio - KEY metric
            # Correct grid: content centered in each cell
            score += avg_center_vs_edge * 2

            # Square frames preferred
            if frame_w == frame_h:
                score += 20

            # Power of 2 frame sizes (common in game assets)
            if frame_w in [64, 128, 256, 512, 1024]:
                score += 10
            if frame_h in [64, 128, 256, 512, 1024]:
                score += 10

            # Higher grid counts get small bonus when close scores
            # (finer grid is usually more accurate)
            score += (rows * cols) * 0.1

            if score > best_score:
                best_score = score
                best_rows, best_cols = rows, cols

        self.rows_spin.blockSignals(True)
        self.cols_spin.blockSignals(True)
        self.rows_spin.setValue(best_rows)
        self.cols_spin.setValue(best_cols)
        self.rows_spin.blockSignals(False)
        self.cols_spin.blockSignals(False)

    def _on_grid(self):
        if self.atlas:
            self._do_demosaic()

    def _do_demosaic(self):
        if not self.atlas:
            return
        r, c = self.rows_spin.value(), self.cols_spin.value()
        self.frames = demosaic(self.atlas, r, c)
        if self.frames:
            self.frame_size = self.frames[0].size
        # Pre-convert all frames to numpy float32 normalized (0-1) for fast ghost/processing
        self._frames_np = [np.array(f, dtype=np.float32) / 255.0 for f in self.frames]
        self._ghost_cache = None
        self.current_frame = 0
        self.timeline.setRange(0, max(0, len(self.frames) - 1))
        self.timeline.setValue(0)
        self.grid_info.setText(f"{len(self.frames)} frames | {self.frame_size[0]}x{self.frame_size[1]}")
        self._update_canvas()
        self._update_frame_label()

    def _auto_fit(self):
        """Calculate global bbox from all frames and auto-fit transform"""
        if not self.frames:
            return

        padding = self.padding_slider.value()
        fw, fh = self.frame_size

        # Check if frames have meaningful alpha (not all opaque)
        first_frame = np.array(self.frames[0])
        has_alpha = np.any(first_frame[:, :, 3] < 250)

        # Find global bounding box across all frames
        global_left, global_top = fw, fh
        global_right, global_bottom = 0, 0

        for frame in self.frames:
            arr = np.array(frame)

            if has_alpha:
                # Use alpha channel
                mask = arr[:, :, 3] > 0
            else:
                # Use brightness (grayscale)
                brightness = np.mean(arr[:, :, :3], axis=2)
                mask = brightness > 10  # Threshold for dark pixels

            rows = np.any(mask, axis=1)
            cols = np.any(mask, axis=0)

            if rows.any() and cols.any():
                y_min, y_max = np.where(rows)[0][[0, -1]]
                x_min, x_max = np.where(cols)[0][[0, -1]]

                global_left = min(global_left, x_min)
                global_top = min(global_top, y_min)
                global_right = max(global_right, x_max)
                global_bottom = max(global_bottom, y_max)

        if global_right <= global_left or global_bottom <= global_top:
            return  # No content found

        # Apply padding
        global_left = max(0, global_left - padding)
        global_top = max(0, global_top - padding)
        global_right = min(fw - 1, global_right + padding)
        global_bottom = min(fh - 1, global_bottom + padding)

        # Calculate bbox size
        bbox_w = global_right - global_left + 1
        bbox_h = global_bottom - global_top + 1

        # Calculate center offset (from frame center to bbox center)
        frame_cx, frame_cy = fw / 2, fh / 2
        bbox_cx = global_left + bbox_w / 2
        bbox_cy = global_top + bbox_h / 2

        # Calculate scale to fit bbox into frame (separate X/Y)
        scale_x = fw / bbox_w
        scale_y = fh / bbox_h

        # Set transform
        self.canvas.tx = -(bbox_cx - frame_cx)
        self.canvas.ty = -(bbox_cy - frame_cy)
        self.canvas.sx = scale_x
        self.canvas.sy = scale_y
        self.canvas.rotation = 0
        self.canvas.update()

        # Sync all sliders with canvas values
        self.lx_slider.blockSignals(True)
        self.ly_slider.blockSignals(True)
        self.sx_slider.blockSignals(True)
        self.sy_slider.blockSignals(True)
        self.rot_slider.blockSignals(True)

        self.lx_slider.setValue(int(self.canvas.tx))
        self.ly_slider.setValue(int(self.canvas.ty))
        self.sx_slider.setValue(int(scale_x * 100))
        self.sy_slider.setValue(int(scale_y * 100))
        self.rot_slider.setValue(0)

        self.lx_slider.blockSignals(False)
        self.ly_slider.blockSignals(False)
        self.sx_slider.blockSignals(False)
        self.sy_slider.blockSignals(False)
        self.rot_slider.blockSignals(False)

        self.lx_label.setText(str(int(self.canvas.tx)))
        self.ly_label.setText(str(int(self.canvas.ty)))
        self.sx_label.setText(f"{scale_x:.2f}")
        self.sy_label.setText(f"{scale_y:.2f}")
        self.rot_label.setText("0°")

        # Show info
        self.grid_info.setText(f"BBox: {bbox_w}x{bbox_h} | Scale: {scale_x:.2f}x{scale_y:.2f}")

    def _on_channel_toggle(self):
        """Update channel view state from buttons"""
        for ch in ['R', 'G', 'B', 'A']:
            self.channel_view[ch] = self.channel_btns[ch].isChecked()
        self._update_canvas()

    def _on_result_channel_toggle(self):
        """Update result preview with channel filter"""
        self._update_result_preview()

    def _update_result_preview(self):
        """Refresh result preview with current channel filter"""
        if not self.result_atlas:
            return
        view = {}
        for ch in ['R', 'G', 'B', 'A']:
            view[ch] = self.result_channel_btns[ch].isChecked()

        if view['R'] and view['G'] and view['B'] and view['A']:
            self.result_preview.set_image(self.result_atlas)
            return

        arr = np.array(self.result_atlas, dtype=np.uint8)
        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

        # Single channel → grayscale display
        on_count = sum([view['R'], view['G'], view['B']])
        if view['A'] and on_count == 0:
            result = np.stack([a, a, a, np.full_like(a, 255)], axis=2)
        elif on_count == 1 and not view['A']:
            ch_data = r if view['R'] else (g if view['G'] else b)
            result = np.stack([ch_data, ch_data, ch_data, np.full_like(ch_data, 255)], axis=2)
        else:
            new_r = r if view['R'] else np.zeros_like(r)
            new_g = g if view['G'] else np.zeros_like(g)
            new_b = b if view['B'] else np.zeros_like(b)
            new_a = a if view['A'] else np.full_like(a, 255)
            result = np.stack([new_r, new_g, new_b, new_a], axis=2)

        self.result_preview.set_image(Image.fromarray(result))

    def _apply_channel_filter(self, img):
        """Apply RGBA channel filter for viewing"""
        r_on = self.channel_view['R']
        g_on = self.channel_view['G']
        b_on = self.channel_view['B']
        a_on = self.channel_view['A']

        # All channels on - no filter needed
        if r_on and g_on and b_on and a_on:
            return img

        arr = np.array(img, dtype=np.uint8)
        r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

        # Alpha only - show as grayscale
        if a_on and not r_on and not g_on and not b_on:
            result = np.stack([a, a, a, np.full_like(a, 255)], axis=2)
            return Image.fromarray(result)

        # Single channel (R, G, or B only) - show as grayscale
        if sum([r_on, g_on, b_on]) == 1 and not a_on:
            if r_on:
                result = np.stack([r, r, r, np.full_like(r, 255)], axis=2)
            elif g_on:
                result = np.stack([g, g, g, np.full_like(g, 255)], axis=2)
            else:
                result = np.stack([b, b, b, np.full_like(b, 255)], axis=2)
            return Image.fromarray(result)

        # Mix channels
        new_r = r if r_on else np.zeros_like(r)
        new_g = g if g_on else np.zeros_like(g)
        new_b = b if b_on else np.zeros_like(b)
        new_a = a if a_on else np.full_like(a, 255)

        result = np.stack([new_r, new_g, new_b, new_a], axis=2)
        return Image.fromarray(result)

    def _update_canvas(self):
        if not self.frames:
            return

        # Ghost is cached - only recompute when frame/steps change
        ghost_on = self.ghost_check.isChecked()
        cache_key = (self.current_frame, self.ghost_steps.value(), ghost_on)

        if self._ghost_cache and self._ghost_cache[0] == cache_key:
            frame = self._ghost_cache[1]
        else:
            frame = self.frames[self.current_frame]
            if ghost_on:
                frame = self._add_ghost(frame)
            self._ghost_cache = (cache_key, frame)

        # Apply brightness/contrast for preview
        frame = self._apply_gamma(frame)

        # Apply channel filter
        frame = self._apply_channel_filter(frame)

        self.canvas.set_frame(frame, self.frame_size)

    def _apply_gamma(self, img):
        """Apply gamma adjustment (preserves black and white)"""
        gamma = self.gamma_slider.value() / 100.0  # 0.2 to 3.0

        if gamma == 1.0:
            return img

        arr = np.array(img, dtype=np.float32)
        rgb = arr[:, :, :3].copy()

        # Normalize to 0-1
        rgb = rgb / 255.0

        # Gamma: pow(pixel, gamma) - preserves 0 and 1
        rgb = np.power(np.clip(rgb, 0.0001, 1.0), gamma)

        # Back to 0-255
        rgb = np.clip(rgb * 255, 0, 255)
        arr[:, :, :3] = rgb

        return Image.fromarray(arr.astype(np.uint8))

    def _add_ghost(self, base):
        steps = self.ghost_steps.value()
        n_frames = len(self._frames_np)

        # Collect ghost indices and fade values
        ghost_indices = []
        ghost_fades = []
        for i in range(1, steps + 1):
            fade = 0.6 / i
            for idx in [self.current_frame - i, self.current_frame + i]:
                if 0 <= idx < n_frames:
                    ghost_indices.append(idx)
                    ghost_fades.append(fade)

        if not ghost_indices:
            return base

        # Work in pre-normalized 0-1 space (no repeated /255)
        result = self._frames_np[self.current_frame].copy()

        for idx, fade in zip(ghost_indices, ghost_fades):
            g = self._frames_np[idx]
            ga = g[:, :, 3:4] * fade

            # Screen blend RGB: 1 - (1-base) * (1 - ghost*alpha)
            result[:, :, :3] = 1.0 - (1.0 - result[:, :, :3]) * (1.0 - g[:, :, :3] * ga)

            # Screen blend Alpha
            result[:, :, 3:4] = 1.0 - (1.0 - result[:, :, 3:4]) * (1.0 - ga)

        return Image.fromarray(np.clip(result * 255, 0, 255).astype(np.uint8))

    def _on_canvas_changed(self):
        # Sync location sliders with canvas
        self.lx_slider.blockSignals(True)
        self.ly_slider.blockSignals(True)
        self.lx_slider.setValue(int(self.canvas.tx))
        self.ly_slider.setValue(int(self.canvas.ty))
        self.lx_slider.blockSignals(False)
        self.ly_slider.blockSignals(False)
        self.lx_label.setText(str(int(self.canvas.tx)))
        self.ly_label.setText(str(int(self.canvas.ty)))

        # Sync scale sliders with canvas
        self.sx_slider.blockSignals(True)
        self.sy_slider.blockSignals(True)
        self.sx_slider.setValue(int(self.canvas.sx * 100))
        self.sy_slider.setValue(int(self.canvas.sy * 100))
        self.sx_slider.blockSignals(False)
        self.sy_slider.blockSignals(False)
        self.sx_label.setText(f"{self.canvas.sx:.2f}")
        self.sy_label.setText(f"{self.canvas.sy:.2f}")

        # Sync rotation slider with canvas
        rot = int(self.canvas.rotation)
        self.rot_slider.blockSignals(True)
        self.rot_slider.setValue(rot)
        self.rot_slider.blockSignals(False)
        self.rot_label.setText(f"{rot}°")

    def _on_loc_slider(self):
        tx = self.lx_slider.value()
        ty = self.ly_slider.value()
        self.lx_label.setText(str(tx))
        self.ly_label.setText(str(ty))
        self.canvas.tx = float(tx)
        self.canvas.ty = float(ty)
        self.canvas.update()

    def _on_scale_slider(self):
        sx = self.sx_slider.value() / 100.0
        sy = self.sy_slider.value() / 100.0
        self.sx_label.setText(f"{sx:.2f}")
        self.sy_label.setText(f"{sy:.2f}")
        self.canvas.sx = sx
        self.canvas.sy = sy
        self.canvas.update()

    def _on_rot_slider(self, value):
        self.canvas.rotation = float(value)
        self.rot_label.setText(f"{value}°")
        self.canvas.update()

    def _on_adjust_changed(self):
        gamma = self.gamma_slider.value() / 100.0
        self.gamma_label.setText(f"{gamma:.2f}")
        self._update_canvas()  # Update preview with new values

    def _reset(self):
        self.canvas.reset_transform()
        self.lx_slider.setValue(0)
        self.ly_slider.setValue(0)
        self.lx_label.setText("0")
        self.ly_label.setText("0")
        self.sx_slider.setValue(100)
        self.sy_slider.setValue(100)
        self.sx_label.setText("1.00")
        self.sy_label.setText("1.00")
        self.rot_slider.setValue(0)
        self.rot_label.setText("0°")
        self.gamma_slider.setValue(100)
        self.gamma_label.setText("1.00")

    def _on_timeline(self, v):
        self.current_frame = v
        self._update_canvas()
        self._update_frame_label()

    def _prev_frame(self):
        if self.frames:
            self.current_frame = (self.current_frame - 1) % len(self.frames)
            self.timeline.setValue(self.current_frame)

    def _next_frame(self):
        if self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.timeline.setValue(self.current_frame)

    def _update_play_icon(self, playing):
        """Update play button: red circle when stopped, pause bars when playing"""
        if playing:
            self.play_btn.setText("||")
            self.play_btn.setStyleSheet("""
                QPushButton { background: #2a2a2a; color: #aaa; border: 1px solid #3a3a3a; border-radius: 3px;
                    font-size: 11px; font-weight: bold; text-align: center; padding: 0; }
                QPushButton:hover { background: #353535; border-color: #e8a838; }
            """)
        else:
            self.play_btn.setText("\u25cf")
            self.play_btn.setStyleSheet("""
                QPushButton { background: #2a2a2a; color: #cc4444; border: 1px solid #3a3a3a; border-radius: 3px;
                    font-size: 12px; text-align: center; padding: 0; }
                QPushButton:hover { background: #353535; border-color: #e8a838; }
            """)

    def _toggle_play(self):
        if self.is_playing:
            self.is_playing = False
            self.play_timer.stop()
            self._update_play_icon(False)
        else:
            if not self.frames:
                return
            self.is_playing = True
            self._update_play_icon(True)
            self.play_timer.start(42)  # ~24fps

    def _update_frame_label(self):
        self.frame_label.setText(f"{self.current_frame + 1}/{len(self.frames)}" if self.frames else "0/0")

    def _render_frame(self, frame):
        """Final render: transform within frame bounds"""
        fw, fh = self.frame_size
        t = self.canvas.get_transform()

        result = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))

        # Edge extend
        pad = max(fw, fh) * 2
        arr = np.array(frame)
        ext = np.pad(arr, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
        img = Image.fromarray(ext)

        # Scale (separate X/Y)
        nw = int(img.width * t['sx'])
        nh = int(img.height * t['sy'])
        if nw > 0 and nh > 0:
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            pad_x = int(pad * t['sx'])
            pad_y = int(pad * t['sy'])
        else:
            pad_x = pad_y = pad

        # Rotate
        if t['rotation'] != 0:
            img = img.rotate(-t['rotation'], expand=True, resample=Image.Resampling.BICUBIC)

        # Crop to frame bounds
        cx = img.width // 2 - int(t['tx'] * t['sx'])
        cy = img.height // 2 - int(t['ty'] * t['sy'])
        left = cx - fw // 2
        top = cy - fh // 2

        cropped = img.crop((left, top, left + fw, top + fh))
        result.paste(cropped, (0, 0))

        # Apply brightness/contrast (use same function as preview)
        result = self._apply_gamma(result)

        return result

    def _mosaic(self):
        if not self.frames:
            return
        # Parallel frame rendering for speed
        with ThreadPoolExecutor() as executor:
            rendered = list(executor.map(self._render_frame, self.frames))
        r, c = self.rows_spin.value(), self.cols_spin.value()
        self.result_atlas = mosaic(rendered, r, c)

        # Apply target resolution
        target_size = self.res_presets[self.res_index]
        current_size = max(self.result_atlas.width, self.result_atlas.height)

        if current_size != target_size:
            # Calculate new dimensions maintaining aspect ratio
            ratio = target_size / current_size
            new_w = int(self.result_atlas.width * ratio)
            new_h = int(self.result_atlas.height * ratio)

            # Use appropriate resampling algorithm
            if ratio < 1:
                # Downscale: Lanczos for sharp results
                resample = Image.Resampling.LANCZOS
            else:
                # Upscale: Lanczos for smooth results
                resample = Image.Resampling.LANCZOS

            self.result_atlas = self.result_atlas.resize((new_w, new_h), resample)

        self._update_result_preview()
        self.result_info.setText(f"{self.result_atlas.width}x{self.result_atlas.height}")
        # Update grid if enabled
        self._stagger_grid = None
        self._toggle_grid()

    def _stagger(self):
        if not self.frames:
            return
        # Render frames with current transform
        with ThreadPoolExecutor() as executor:
            rendered = list(executor.map(self._render_frame, self.frames))

        r, c = self.rows_spin.value(), self.cols_spin.value()

        # Resize each frame BEFORE packing (not after)
        # Packing 후 리사이즈하면 LANCZOS 보간이 채널 데이터를 깨뜨림
        total = r * c
        num_cells = math.ceil(total / 4)
        grid_size = math.ceil(math.sqrt(num_cells))
        target_size = self.res_presets[self.res_index]
        cell_size = target_size // grid_size

        if cell_size > 0:
            fw, fh = rendered[0].size
            if fw != cell_size or fh != cell_size:
                rendered = [f.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
                           for f in rendered]

        packed, new_r, new_c = stagger_pack(rendered, r, c)

        self.result_atlas = packed
        self._stagger_grid = (new_r, new_c)
        self._update_result_preview()
        total_frames = self.rows_spin.value() * self.cols_spin.value()
        self.result_info.setText(
            f"Stagger {new_r}x{new_c} | {packed.width}x{packed.height} | {total_frames}f→{math.ceil(total_frames/4)}cells"
        )
        self._toggle_grid()

    def _res_down(self):
        if self.res_index > 0:
            self.res_index -= 1
            self._update_res_label()

    def _res_up(self):
        if self.res_index < len(self.res_presets) - 1:
            self.res_index += 1
            self._update_res_label()

    def _update_res_label(self):
        self.res_label.setText(str(self.res_presets[self.res_index]))

    def _toggle_grid(self):
        if self.grid_check.isChecked():
            if hasattr(self, '_stagger_grid') and self._stagger_grid:
                r, c = self._stagger_grid
            else:
                r, c = self.rows_spin.value(), self.cols_spin.value()
            self.result_preview.set_grid(r, c)
        else:
            self.result_preview.set_grid(None, None)

    def _save(self):
        if not self.result_atlas:
            return
        filters = "PNG (*.png);;TGA (*.tga);;JPEG (*.jpg *.jpeg);;GIF (*.gif);;All (*)"
        default_name = f"{self.original_filename}.png"
        path, selected_filter = QFileDialog.getSaveFileName(self, "Save", default_name, filters)
        if path:
            # Handle format based on extension
            ext = Path(path).suffix.lower()
            img = self.result_atlas

            if ext in ('.jpg', '.jpeg'):
                # JPEG doesn't support alpha, convert to RGB
                if img.mode == 'RGBA':
                    bg = Image.new('RGB', img.size, (0, 0, 0))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                img.save(path, quality=95)
            elif ext == '.gif':
                img.save(path)
            else:
                img.save(path)

            self.result_info.setText(f"Saved: {Path(path).name}")


def _resource_path(relative):
    """Get path to resource - works for dev and PyInstaller exe"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent / relative


def main():
    import os
    # Fix Korean/CJK IME input on Windows
    os.environ["QT_IM_MODULE"] = "windows"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

    # Windows taskbar icon - must be set before QApplication on Windows
    import ctypes
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('AtlasOptimizer')
    except:
        pass

    # Must be set before QApplication for IME
    from PyQt5.QtCore import Qt as QtCore_Qt
    QApplication.setAttribute(QtCore_Qt.AA_EnableHighDpiScaling, False)

    app = QApplication(sys.argv)
    app.setAttribute(QtCore_Qt.AA_UseHighDpiPixmaps, False)

    # Set app icon globally (for taskbar + window)
    icon_path = _resource_path("icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
