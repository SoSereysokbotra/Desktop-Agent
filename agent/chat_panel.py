"""
Floating Chat Panel (Phase A)

A small, always-on-top, frameless floating window that displays the running
conversation (user input + agent responses). It replaces Windows toast
notifications for CONVERSATION content only - short-lived status blips
("Thinking...", errors) still go through the toast system.

Threading contract (see the Phase A architecture plan):
  - QApplication, ChatBridge, and ChatPanel are all created on the MAIN
    (GUI) thread. Widgets are only ever touched on that thread.
  - Worker threads (voice/LLM/tray) never call panel methods directly. They
    emit ChatBridge signals; because the bridge lives on the GUI thread, Qt
    delivers those signals via a queued connection so the slots run on the
    GUI thread. That is the only safe way to update the UI cross-thread.
"""

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ChatBridge(QObject):
    """
    Thread-safe bridge between worker threads and the GUI.

    Emit these signals from ANY thread; the connected slots run on the GUI
    thread (queued connection), so it is safe to update widgets from them.
    """

    user_said = Signal(str)       # user's input text -> append a user bubble
    agent_said = Signal(str)      # agent's response  -> append an agent bubble
    quit_requested = Signal()     # tray "Quit" -> app.quit() on GUI thread
    type_requested = Signal()     # tray "Type a Command" -> show QInputDialog
    confirm_requested = Signal(object)  # payload{text,event,result} -> GUI confirm


# ── Styling (kept inline so the panel is fully self-contained) ───────────────
_PANEL_QSS = """
#ChatPanel {
    background-color: #111827;
    border: 1px solid #374151;
    border-radius: 12px;
}
#Header {
    background-color: #1f2937;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
#HeaderTitle { color: #e5e7eb; font-weight: 600; font-size: 12px; }
#HideBtn {
    color: #9ca3af; background: transparent; border: none;
    font-size: 16px; font-weight: 700;
}
#HideBtn:hover { color: #f87171; }
QScrollArea { border: none; background: transparent; }
#Bubbles { background: transparent; }
QLabel[role="user"] {
    background-color: #4f46e5; color: white;
    border-radius: 10px; padding: 8px 10px;
}
QLabel[role="agent"] {
    background-color: #374151; color: #f3f4f6;
    border-radius: 10px; padding: 8px 10px;
}
"""


class ChatPanel(QWidget):
    """Frameless, always-on-top floating conversation panel."""

    WIDTH = 340
    HEIGHT = 460
    MARGIN = 24  # gap from screen edges

    def __init__(self, bridge: ChatBridge):
        super().__init__()
        self.bridge = bridge
        self._drag_offset = None
        self._stick_to_bottom = True  # auto-scroll only when user is at bottom

        # Frameless + always on top + Tool (Tool = no taskbar button).
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        # Show without stealing keyboard focus from the user's active window.
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("ChatPanel")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setStyleSheet(_PANEL_QSS)

        self._build_ui()
        self._position_bottom_right()

        # Wire bridge signals -> GUI slots (runs on GUI thread).
        self.bridge.user_said.connect(self.add_user_message)
        self.bridge.agent_said.connect(self.add_agent_message)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header (doubles as a drag handle)
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(36)
        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(12, 0, 8, 0)
        title = QLabel("Desktop Agent")
        title.setObjectName("HeaderTitle")
        hide_btn = QPushButton("–")
        hide_btn.setObjectName("HideBtn")
        hide_btn.setFixedSize(24, 24)
        hide_btn.setCursor(Qt.PointingHandCursor)
        hide_btn.clicked.connect(self.hide)  # hide only, never quits the app
        hbox.addWidget(title)
        hbox.addStretch(1)
        hbox.addWidget(hide_btn)
        root.addWidget(header)

        # Scrollable conversation area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.bubbles = QWidget()
        self.bubbles.setObjectName("Bubbles")
        self.bubbles_layout = QVBoxLayout(self.bubbles)
        self.bubbles_layout.setContentsMargins(10, 10, 10, 10)
        self.bubbles_layout.setSpacing(8)
        self.bubbles_layout.addStretch(1)  # keeps bubbles pinned to the top

        self.scroll.setWidget(self.bubbles)
        root.addWidget(self.scroll, 1)

        # Auto-scroll AFTER the layout recomputes its content height: the
        # scrollbar emits rangeChanged once the new (possibly tall, wrapped)
        # bubble has been measured. Scrolling here reaches the true bottom,
        # unlike an immediate setValue(maximum) right after inserting a widget.
        self.scroll.verticalScrollBar().rangeChanged.connect(self._auto_scroll)

    def _position_bottom_right(self):
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = area.right() - self.WIDTH - self.MARGIN
        y = area.bottom() - self.HEIGHT - self.MARGIN
        self.move(x, y)

    # ------------------------------------------------------------------
    # Slots (GUI thread) - append conversation bubbles
    # ------------------------------------------------------------------

    def add_user_message(self, text: str):
        self._add_bubble(text, role="user")

    def add_agent_message(self, text: str):
        self._add_bubble(text, role="agent")

    def _add_bubble(self, text: str, role: str):
        # Decide BEFORE adding content whether to stay pinned to the bottom:
        # only auto-scroll if the user is already at/near the bottom, so we
        # don't yank the view while they are reading scrolled-up history.
        bar = self.scroll.verticalScrollBar()
        self._stick_to_bottom = bar.value() >= (bar.maximum() - 4)

        bubble = QLabel(text)
        bubble.setWordWrap(True)  # full text, no truncation
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setProperty("role", role)
        bubble.setMaximumWidth(int(self.WIDTH * 0.82))

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)

        # Insert before the trailing stretch item so bubbles stack top-down.
        self.bubbles_layout.insertLayout(self.bubbles_layout.count() - 1, row)

        if not self.isVisible():
            self.show()
        # Actual scrolling happens in _auto_scroll(), triggered by rangeChanged
        # once the layout has measured the new bubble's height.

    def _auto_scroll(self, _minimum, _maximum):
        if self._stick_to_bottom:
            self.scroll.verticalScrollBar().setValue(_maximum)

    # ------------------------------------------------------------------
    # Frameless window dragging (via the header area)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 36:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
