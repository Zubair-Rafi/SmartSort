"""
Application stylesheet — dark, professional theme.

Colour palette (GitHub-inspired dark):
  bg_primary   #0d1117   Main background
  bg_secondary #161b22   Sidebar / card surfaces
  bg_hover     #21262d   Hover states
  border       #30363d   Dividers
  accent       #58a6ff   Blue — active nav, buttons
  success      #3fb950   Green
  warning      #d29922   Amber
  error        #f85149   Red
  text_primary #e6edf3   Body text
  text_muted   #8b949e   Captions, placeholders
"""

APP_STYLESHEET = """
/* ── Global ────────────────────────────────────────────────────────────── */
* {
    font-family: "Segoe UI", "SF Pro Display", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
    color: #e6edf3;
}
QMainWindow, QWidget {
    background-color: #0d1117;
}
QToolTip {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
#sidebar {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}
#app_title {
    font-size: 16px;
    font-weight: 700;
    color: #e6edf3;
    letter-spacing: 0.5px;
}
#app_subtitle {
    font-size: 11px;
    color: #8b949e;
}
#nav_btn {
    background-color: transparent;
    color: #8b949e;
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
}
#nav_btn:hover {
    background-color: #21262d;
    color: #e6edf3;
}
#nav_btn[active="true"] {
    background-color: #21262d;
    color: #58a6ff;
    font-weight: 600;
}
#status_badge {
    font-size: 11px;
    color: #8b949e;
    padding: 6px 14px 10px 14px;
}
#status_dot_on  { color: #3fb950; font-size: 14px; }
#status_dot_off { color: #484f58; font-size: 14px; }

/* ── Content area ───────────────────────────────────────────────────────── */
#content_area {
    background-color: #0d1117;
}
#page_title {
    font-size: 20px;
    font-weight: 700;
    color: #e6edf3;
    padding-bottom: 4px;
}
#page_subtitle {
    font-size: 12px;
    color: #8b949e;
}
#section_header {
    font-size: 12px;
    font-weight: 600;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.8px;
}

/* ── Cards ──────────────────────────────────────────────────────────────── */
#stat_card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
}
#stat_value {
    font-size: 28px;
    font-weight: 700;
    color: #e6edf3;
}
#stat_label {
    font-size: 12px;
    color: #8b949e;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
#primary_btn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
}
#primary_btn:hover  { background-color: #2ea043; }
#primary_btn:pressed { background-color: #1a6e2a; }
#primary_btn:disabled { background-color: #21262d; color: #484f58; border-color: #30363d; }

#danger_btn {
    background-color: transparent;
    color: #f85149;
    border: 1px solid #f85149;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}
#danger_btn:hover { background-color: rgba(248,81,73,0.1); }

#secondary_btn {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
}
#secondary_btn:hover { background-color: #2d333b; border-color: #8b949e; }

/* ── Tables ─────────────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #161b22;
    alternate-background-color: #1c2128;
    gridline-color: #30363d;
    border: 1px solid #30363d;
    border-radius: 6px;
    selection-background-color: #1f6feb;
    selection-color: #e6edf3;
}
QTableWidget::item { padding: 8px 12px; }
QHeaderView::section {
    background-color: #21262d;
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 8px 12px;
}
QTableWidget::item:selected { color: #e6edf3; }

/* ── Tree ───────────────────────────────────────────────────────────────── */
QTreeWidget {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    alternate-background-color: #1c2128;
    selection-background-color: #1f6feb;
}
QTreeWidget::item { padding: 5px 8px; }
QTreeWidget::branch { background-color: transparent; }

/* ── Inputs ─────────────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #58a6ff;
    outline: none;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    selection-background-color: #21262d;
}

/* ── Scroll bars ────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #0d1117;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #30363d;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #0d1117;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #30363d;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background-color: #484f58; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Progress bar ───────────────────────────────────────────────────────── */
QProgressBar {
    background-color: #21262d;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #58a6ff;
    border-radius: 4px;
}

/* ── Labels ─────────────────────────────────────────────────────────────── */
#success_label { color: #3fb950; font-weight: 600; }
#error_label   { color: #f85149; font-weight: 600; }
#warning_label { color: #d29922; font-weight: 600; }
#muted_label   { color: #8b949e; }

/* ── Dividers ───────────────────────────────────────────────────────────── */
#h_divider {
    background-color: #30363d;
    max-height: 1px;
    min-height: 1px;
}

/* ── CheckBox ───────────────────────────────────────────────────────────── */
QCheckBox { color: #e6edf3; spacing: 8px; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border-color: #1f6feb;
}

/* ── Splitter ───────────────────────────────────────────────────────────── */
QSplitter::handle { background-color: #30363d; }
QSplitter::handle:horizontal { width: 1px; }

/* ── Message boxes ──────────────────────────────────────────────────────── */
QMessageBox { background-color: #161b22; }
QMessageBox QLabel { color: #e6edf3; }
QMessageBox QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 16px;
    min-width: 70px;
}
QMessageBox QPushButton:hover { background-color: #2d333b; }
"""
