#!/usr/bin/env python3

import json
import sys
import re
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QSplitter, QScrollArea, QFrame, QLineEdit,
    QFileDialog, QStatusBar, QMessageBox, QGroupBox,
    QSizePolicy, QDialog, QComboBox, QSpinBox, QDialogButtonBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QDragEnterEvent, QDropEvent,
    QPainter, QPen, QBrush, QFontMetrics, QKeySequence, QShortcut,
)

sys.path.insert(0, str(Path(__file__).parent.parent))
import a2a_reconstruct as a2a

THEMES = {
    "dark_neutral": {
        "name":         "Dark Neutral",
        "dark_bg":      "#1e1e1e",
        "panel_bg":     "#252526",
        "card_bg":      "#2d2d2d",
        "border":       "#3e3e3e",
        "text_primary": "#d4d4d4",
        "text_muted":   "#858585",
        "accent_blue":  "#4fc1ff",
        "accent_green": "#4ec9b0",
        "accent_red":   "#f44747",
        "accent_teal":  "#4ec9b0",
        "accent_purp":  "#c586c0",
        "accent_org":   "#ce9178",
        "accent_yel":   "#dcdcaa",
    },
    "dark_blue": {
        "name":         "Dark Blue",
        "dark_bg":      "#0d1117",
        "panel_bg":     "#161b22",
        "card_bg":      "#1c2128",
        "border":       "#30363d",
        "text_primary": "#e6edf3",
        "text_muted":   "#7d8590",
        "accent_blue":  "#58a6ff",
        "accent_green": "#3fb950",
        "accent_red":   "#ff7b72",
        "accent_teal":  "#39d353",
        "accent_purp":  "#bc8cff",
        "accent_org":   "#ffa657",
        "accent_yel":   "#e3b341",
    },
    "dark_purple": {
        "name":         "Dark Purple",
        "dark_bg":      "#1e1e2e",
        "panel_bg":     "#252537",
        "card_bg":      "#2d2d44",
        "border":       "#3a3a55",
        "text_primary": "#cdd6f4",
        "text_muted":   "#6c6f93",
        "accent_blue":  "#89b4fa",
        "accent_green": "#a6e3a1",
        "accent_red":   "#f38ba8",
        "accent_teal":  "#94e2d5",
        "accent_purp":  "#cba6f7",
        "accent_org":   "#fab387",
        "accent_yel":   "#f9e2af",
    },
    "light": {
        "name":         "Light Professional",
        "dark_bg":      "#f0f2f5",
        "panel_bg":     "#ffffff",
        "card_bg":      "#f7f8fa",
        "border":       "#dde1e7",
        "text_primary": "#1a1a2e",
        "text_muted":   "#6b7280",
        "accent_blue":  "#2563eb",
        "accent_green": "#16a34a",
        "accent_red":   "#dc2626",
        "accent_teal":  "#0891b2",
        "accent_purp":  "#7c3aed",
        "accent_org":   "#ea580c",
        "accent_yel":   "#d97706",
    },
    "high_contrast": {
        "name":         "High Contrast",
        "dark_bg":      "#000000",
        "panel_bg":     "#0a0a0a",
        "card_bg":      "#111111",
        "border":       "#555555",
        "text_primary": "#ffffff",
        "text_muted":   "#aaaaaa",
        "accent_blue":  "#00aaff",
        "accent_green": "#00ff88",
        "accent_red":   "#ff3333",
        "accent_teal":  "#00ffcc",
        "accent_purp":  "#cc88ff",
        "accent_org":   "#ff8800",
        "accent_yel":   "#ffee00",
    },
}

FONT_FAMILIES = {
    "System Default": "Segoe UI, SF Pro Display, Inter, Arial, sans-serif",
    "Monospace":       "Fira Code, Consolas, Courier New, monospace",
    "Roboto":          "Roboto, Helvetica Neue, Arial, sans-serif",
    "Ubuntu":          "Ubuntu, Cantarell, Arial, sans-serif",
    "Georgia (Serif)": "Georgia, Times New Roman, serif",
}

SETTINGS_FILE = Path.home() / ".a2a_forensics_settings.json"

DEFAULT_SETTINGS: dict = {
    "theme":       "dark_neutral",
    "font_family": "System Default",
    "font_size":   15,
}

_CS: dict = {}

def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.exists():
            saved = json.loads(SETTINGS_FILE.read_text())
            s.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    except Exception:
        pass
    return s

def save_settings(s: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    except Exception:
        pass

def _t(key: str) -> str:
    theme_key = _CS.get("theme", "dark_neutral")
    theme = THEMES.get(theme_key, THEMES["dark_neutral"])
    return theme.get(key, "#ff00ff")

def _fs(delta: int = 0) -> int:
    return max(9, _CS.get("font_size", 15) + delta)

def _ff() -> str:
    fam_key = _CS.get("font_family", "System Default")
    return FONT_FAMILIES.get(fam_key, FONT_FAMILIES["System Default"])

def build_app_style() -> str:
    fs   = _fs()
    fs_s = _fs(-2)
    fs_t = _fs(-3)
    ff   = _ff()
    return f"""
QMainWindow, QWidget {{
    background-color: {_t('dark_bg')};
    color: {_t('text_primary')};
    font-family: {ff};
    font-size: {fs}px;
}}
QDialog {{
    background-color: {_t('panel_bg')};
}}
QTabWidget::pane {{
    border: 1px solid {_t('border')};
    background: {_t('panel_bg')};
}}
QTabBar {{
    border-bottom: 2px solid {_t('border')};
}}
QTabBar::tab {{
    background: {_t('card_bg')};
    color: {_t('text_primary')};
    padding: 11px 28px;
    border: 1px solid {_t('border')};
    border-bottom: none;
    margin-right: 3px;
    font-size: {fs}px;
    font-weight: 500;
    min-width: 80px;
    opacity: 0.75;
}}
QTabBar::tab:selected {{
    background: {_t('panel_bg')};
    color: {_t('accent_blue')};
    border-top: 3px solid {_t('accent_blue')};
    border-bottom: 2px solid {_t('panel_bg')};
    font-weight: bold;
    padding-top: 9px;
    opacity: 1;
}}
QTabBar::tab:!selected:hover {{
    background: {_t('dark_bg')};
    color: {_t('text_primary')};
    border-top: 3px solid {_t('border')};
    padding-top: 9px;
}}
QTreeWidget {{
    background-color: {_t('panel_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    alternate-background-color: {_t('card_bg')};
    outline: none;
    font-size: {fs}px;
}}
QTreeWidget::item {{ padding: 3px 2px; }}
QTreeWidget::item:selected {{
    background-color: {_t('accent_blue')}33;
    color: {_t('text_primary')};
}}
QTreeWidget::item:hover {{
    background-color: {_t('accent_blue')}18;
}}
QHeaderView::section {{
    background-color: {_t('card_bg')};
    color: {_t('text_muted')};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {_t('border')};
    font-size: {fs_t}px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QScrollBar:vertical {{
    background: {_t('dark_bg')};
    width: 9px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {_t('border')};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {_t('text_muted')}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {_t('dark_bg')};
    height: 9px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {_t('border')};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QPushButton {{
    background-color: {_t('card_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    padding: 7px 18px;
    border-radius: 6px;
    font-size: {fs}px;
}}
QPushButton:hover {{
    background-color: {_t('accent_blue')}22;
    border-color: {_t('accent_blue')};
}}
QPushButton:pressed {{ background-color: {_t('dark_bg')}; }}
QPushButton:disabled {{
    color: {_t('text_muted')};
    border-color: {_t('border')};
    background: {_t('card_bg')};
}}
QPushButton:checked {{
    background-color: {_t('accent_blue')}22;
    border-color: {_t('accent_blue')};
    color: {_t('accent_blue')};
}}
QLineEdit {{
    background-color: {_t('card_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    padding: 6px 10px;
    border-radius: 4px;
    font-size: {fs}px;
}}
QLineEdit:focus {{ border-color: {_t('accent_blue')}; }}
QComboBox {{
    background-color: {_t('card_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    padding: 6px 10px;
    border-radius: 4px;
    font-size: {fs}px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {_t('card_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    selection-background-color: {_t('accent_blue')}33;
}}
QSpinBox {{
    background-color: {_t('card_bg')};
    color: {_t('text_primary')};
    border: 1px solid {_t('border')};
    padding: 6px 10px;
    border-radius: 4px;
    font-size: {fs}px;
}}
QProgressBar {{
    background-color: {_t('card_bg')};
    border: 1px solid {_t('border')};
    border-radius: 4px;
    text-align: center;
    color: {_t('text_primary')};
    height: 20px;
    font-size: {fs_s}px;
}}
QProgressBar::chunk {{
    background-color: {_t('accent_blue')};
    border-radius: 3px;
}}
QSplitter::handle {{ background: {_t('border')}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QStatusBar {{
    background: {_t('card_bg')};
    color: {_t('text_muted')};
    border-top: 1px solid {_t('border')};
    font-size: {fs_s}px;
}}
QGroupBox {{
    border: 1px solid {_t('border')};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    color: {_t('text_muted')};
    font-size: {fs_t}px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}}
QLabel {{ font-size: {fs}px; }}
QWidget#topBar {{
    background: {_t('card_bg')};
    border-bottom: 1px solid {_t('border')};
}}
QWidget#dropContainer {{
    background: {_t('dark_bg')};
    border-bottom: 1px solid {_t('border')};
}}
QLabel#titleLabel {{
    color: {_t('accent_blue')};
    font-size: {_fs(2)}px;
    font-weight: bold;
}}
QLabel#progressLabel {{
    color: {_t('text_muted')};
    font-size: {_fs(-1)}px;
}}
QPushButton#analyzeBtn {{
    background: {_t('accent_blue')}22;
    color: {_t('accent_blue')};
    border: 1px solid {_t('accent_blue')}66;
    border-radius: 6px;
    font-weight: bold;
    padding: 7px 18px;
    font-size: {fs}px;
}}
QPushButton#analyzeBtn:hover {{ background: {_t('accent_blue')}44; }}
QPushButton#analyzeBtn:disabled {{
    color: {_t('text_muted')};
    border-color: {_t('border')};
    background: {_t('card_bg')};
}}
QWidget#filterBar {{
    background: {_t('dark_bg')};
    border-bottom: 1px solid {_t('border')};
}}
"""

def _badge_label(text: str, color: str, parent=None) -> QLabel:
    fs = _fs(-2)
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(
        f"background:{color}22; color:{color}; border:1px solid {color}55;"
        f" border-radius:4px; padding:2px 8px; font-size:{fs}px; font-weight:bold;"
    )
    lbl.setFixedHeight(max(20, fs + 10))
    return lbl

def _mono_label(text: str, parent=None) -> QLabel:
    fs = _fs(-2)
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(
        f"font-family: 'Fira Code','Consolas','Courier New',monospace;"
        f" font-size:{fs}px; color:{_t('accent_yel')};"
        f" background:{_t('card_bg')}; border:1px solid {_t('border')};"
        f" border-radius:3px; padding:1px 6px;"
    )
    return lbl

def _section_label(text: str, parent=None) -> QLabel:
    fs = _fs(-3)
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(
        f"color:{_t('text_muted')}; font-size:{fs}px; font-weight:bold;"
        f" letter-spacing:1px; text-transform:uppercase; padding-bottom:2px;"
    )
    return lbl

def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

class ThemeSwatch(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, theme_key: str, theme: dict, parent=None):
        super().__init__(parent)
        self.theme_key = theme_key
        self.theme = theme
        self.setFixedSize(148, 96)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        dots = QHBoxLayout()
        dots.setSpacing(4)
        for color_key in ("accent_blue", "accent_green", "accent_teal", "accent_purp", "accent_org"):
            dot = QLabel()
            dot.setFixedSize(14, 14)
            dot.setStyleSheet(
                f"background:{self.theme[color_key]}; border-radius:7px;"
                f" border:1px solid {self.theme['border']};"
            )
            dots.addWidget(dot)
        dots.addStretch()
        layout.addLayout(dots)

        bar = QWidget()
        bar.setFixedHeight(26)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)
        for color_key in ("dark_bg", "panel_bg", "card_bg"):
            seg = QLabel()
            seg.setStyleSheet(f"background:{self.theme[color_key]};")
            bar_layout.addWidget(seg)
        layout.addWidget(bar)

        name_lbl = QLabel(self.theme["name"])
        name_lbl.setStyleSheet(
            f"color:{self.theme['text_primary']}; font-size:12px;"
            f" font-weight:bold; background:transparent;"
        )
        layout.addWidget(name_lbl)

    def set_selected(self, selected: bool):
        self._selected = selected
        border_color = self.theme["accent_blue"] if selected else self.theme["border"]
        bg = self.theme["card_bg"]
        self.setStyleSheet(
            f"QFrame {{ background:{bg}; border:2px solid {border_color}; border-radius:8px; }}"
        )

    def mousePressEvent(self, event):
        self.clicked.emit(self.theme_key)

class SettingsDialog(QDialog):
    settings_applied = pyqtSignal(dict)

    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(700)
        self._working = dict(current)
        self._swatches: dict[str, ThemeSwatch] = {}
        self._build_ui()
        self._load_working()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        theme_grp = QGroupBox("Theme")
        theme_grp.setStyleSheet(
            f"QGroupBox {{ border:1px solid {_t('border')}; border-radius:6px;"
            f" margin-top:10px; padding-top:10px; color:{_t('text_muted')};"
            f" font-size:{_fs(-3)}px; font-weight:bold; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; }}"
        )
        theme_layout = QHBoxLayout(theme_grp)
        theme_layout.setSpacing(10)

        for key, theme in THEMES.items():
            swatch = ThemeSwatch(key, theme)
            swatch.clicked.connect(self._on_theme_clicked)
            self._swatches[key] = swatch
            theme_layout.addWidget(swatch)
        theme_layout.addStretch()
        root.addWidget(theme_grp)

        font_grp = QGroupBox("Font")
        font_grp.setStyleSheet(
            f"QGroupBox {{ border:1px solid {_t('border')}; border-radius:6px;"
            f" margin-top:10px; padding-top:10px; color:{_t('text_muted')};"
            f" font-size:{_fs(-3)}px; font-weight:bold; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; }}"
        )
        font_layout = QHBoxLayout(font_grp)
        font_layout.setSpacing(16)

        font_layout.addWidget(QLabel("Family:"))
        self._family_combo = QComboBox()
        self._family_combo.setMinimumWidth(200)
        for name in FONT_FAMILIES:
            self._family_combo.addItem(name)
        self._family_combo.currentTextChanged.connect(
            lambda t: self._working.update({"font_family": t}))
        font_layout.addWidget(self._family_combo)

        font_layout.addWidget(QLabel("Size:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(11, 22)
        self._size_spin.setSuffix(" px")
        self._size_spin.setFixedWidth(80)
        self._size_spin.valueChanged.connect(
            lambda v: self._working.update({"font_size": v}))
        font_layout.addWidget(self._size_spin)
        font_layout.addStretch()
        root.addWidget(font_grp)

        prev_grp = QGroupBox("Preview")
        prev_grp.setStyleSheet(
            f"QGroupBox {{ border:1px solid {_t('border')}; border-radius:6px;"
            f" margin-top:10px; padding-top:10px; color:{_t('text_muted')};"
            f" font-size:{_fs(-3)}px; font-weight:bold; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; subcontrol-position:top left; padding:0 6px; }}"
        )
        prev_layout = QVBoxLayout(prev_grp)
        self._preview = QLabel(
            "Agent Card  ·  RPC Request  ·  Task: COMPLETED  ·  0x03A1F200"
        )
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setFixedHeight(42)
        prev_layout.addWidget(self._preview)
        root.addWidget(prev_grp)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply
        )
        btn_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._do_apply)
        btn_box.accepted.connect(self._do_ok)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    def _load_working(self):
        theme_key = self._working.get("theme", "dark_neutral")
        for key, sw in self._swatches.items():
            sw.set_selected(key == theme_key)
        fam = self._working.get("font_family", "System Default")
        idx = self._family_combo.findText(fam)
        if idx >= 0:
            self._family_combo.setCurrentIndex(idx)
        self._size_spin.setValue(self._working.get("font_size", 15))
        self._update_preview()

    def _on_theme_clicked(self, key: str):
        self._working["theme"] = key
        for k, sw in self._swatches.items():
            sw.set_selected(k == key)
        self._update_preview()

    def _update_preview(self):
        t = THEMES.get(self._working.get("theme", "dark_neutral"), THEMES["dark_neutral"])
        fs = self._working.get("font_size", 15)
        fam_key = self._working.get("font_family", "System Default")
        ff = FONT_FAMILIES.get(fam_key, FONT_FAMILIES["System Default"])
        self._preview.setStyleSheet(
            f"background:{t['card_bg']}; color:{t['text_primary']};"
            f" border:1px solid {t['border']}; border-radius:4px;"
            f" font-family:{ff}; font-size:{fs}px; padding:8px;"
        )

    def _do_apply(self):
        self.settings_applied.emit(dict(self._working))

    def _do_ok(self):
        self.settings_applied.emit(dict(self._working))
        self.accept()

class AnalysisWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, image_path: str):
        super().__init__()
        self.image_path = image_path

    def run(self):
        try:
            path = Path(self.image_path)
            self.progress.emit("Extracting strings from memory image…", 5)
            pairs = a2a.extract_strings(str(path), min_len=6)
            self.progress.emit(f"Extracted {len(pairs):,} raw strings.", 25)

            self.progress.emit("Stitching degree-symbol fragments…", 30)
            triples = a2a.stitch_degree_splits(pairs)
            lines       = [l for _, _, l in triples]
            offsets     = [o for o, _, _ in triples]
            end_offsets = [e for _, e, _ in triples]

            self.progress.emit("Scanning for agent_output candidates…", 35)
            agent_outputs = a2a.extract_agent_outputs(lines)
            multiline_content: Optional[str] = None
            if agent_outputs:
                multiline_content = agent_outputs[0]
                best = multiline_content.strip().rstrip('"')
                if len(best) < 200:
                    prefix = re.escape(best[:30]) if best else None
                    if prefix:
                        derived_pat = re.compile(prefix, re.IGNORECASE)
                        longer = a2a.reconstruct_multiline_content(lines, derived_pat)
                        _json_spill = re.compile(
                            r'"(?:taskId|contextId|messageId|jsonrpc|method|role|kind)"\s*:')
                        if (longer and len(longer) > len(multiline_content)
                                and not _json_spill.search(longer)):
                            multiline_content = longer

            self.progress.emit("Carving JSON objects…", 45)
            objects = a2a.carve_json_objects(lines, offsets, end_offsets)
            self.progress.emit(f"Carved {len(objects)} unique JSON objects.", 60)

            self.progress.emit("Classifying A2A objects…", 65)
            classified = a2a.classify_objects(objects)

            agent_cards = [a2a.parse_agent_card(o)  for o in classified["agent_cards"]]
            requests    = [a2a.parse_rpc_request(o)  for o in classified["rpc_requests"]]
            responses   = [a2a.parse_rpc_response(o) for o in classified["rpc_responses"]]

            artifact_by_task: dict = {}
            for au in classified.get("artifact_updates", []):
                tid = au.get("taskId", "")
                if tid:
                    artifact_by_task.setdefault(tid, []).append(au.get("artifact", {}))

            self.progress.emit("Recovering partial responses…", 72)
            if not responses:
                responses = a2a.extract_partial_responses(lines)
            else:
                known_ids = {r.task_id for r in responses}
                extras = [r for r in a2a.extract_partial_responses(lines)
                          if r.task_id not in known_ids]
                responses.extend(extras)

            self.progress.emit("Reconstructing interactions…", 80)
            interactions = a2a.reconstruct_interactions(agent_cards, requests, responses)

            for ix in interactions:
                if not ix.response:
                    continue
                resp = ix.response
                if resp.embedded_plan is None and resp.task_id in artifact_by_task:
                    extracted = a2a._extract_plan_from_artifacts(artifact_by_task[resp.task_id])
                    if extracted is not None:
                        resp.embedded_plan = extracted

            def _best_content_for(truncated: str) -> Optional[str]:
                trunc = truncated.strip()
                if not trunc or len(trunc) < 50:
                    return multiline_content or (agent_outputs[0] if agent_outputs else None)
                if multiline_content:
                    mc = multiline_content.strip()
                    if mc.startswith(trunc[:20]) or trunc[:20] in mc[:80]:
                        return multiline_content
                for ao in agent_outputs:
                    if ao.startswith(trunc[:20]) or trunc[:20] in ao[:80]:
                        return ao
                if agent_outputs and len(trunc) < 200:
                    return agent_outputs[0]
                return None

            for ix in interactions:
                if not ix.response:
                    continue
                resp = ix.response
                if resp.response_text and len(resp.response_text.strip()) < 200:
                    better = _best_content_for(resp.response_text)
                    if better:
                        resp.response_text = better
                if resp.embedded_plan and isinstance(resp.embedded_plan.get("agent_output"), str):
                    ao = resp.embedded_plan["agent_output"]
                    if len(ao.strip()) < 200:
                        better = _best_content_for(ao)
                        if better:
                            resp.embedded_plan["agent_output"] = better

            self.progress.emit("Building result set…", 95)
            result = {
                "image_name":    path.name,
                "image_size":    path.stat().st_size,
                "classified":    classified,
                "agent_cards":   agent_cards,
                "requests":      requests,
                "responses":     responses,
                "interactions":  interactions,
            }
            self.progress.emit("Done.", 100)
            self.finished.emit(result)

        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())

class JsonTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Key", "Value"])
        self.setColumnWidth(0, 240)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)

    def load(self, data, label: str = "root"):
        self.clear()
        root = self._make_item(label, data)
        self.addTopLevelItem(root)
        root.setExpanded(True)
        for i in range(root.childCount()):
            root.child(i).setExpanded(True)

    def _make_item(self, key: str, value) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setText(0, str(key))
        item.setForeground(0, QColor(_t("accent_blue")))

        if isinstance(value, dict):
            summary = f"{{ {len(value)} keys }}"
            item.setText(1, summary)
            item.setForeground(1, QColor(_t("text_muted")))
            item.setData(1, Qt.ItemDataRole.UserRole, value)
            for k, v in value.items():
                item.addChild(self._make_item(k, v))
        elif isinstance(value, list):
            summary = f"[ {len(value)} items ]"
            item.setText(1, summary)
            item.setForeground(1, QColor(_t("text_muted")))
            item.setData(1, Qt.ItemDataRole.UserRole, value)
            for i, v in enumerate(value):
                item.addChild(self._make_item(f"[{i}]", v))
        elif isinstance(value, bool):
            item.setText(1, str(value).lower())
            item.setForeground(1, QColor(_t("accent_red") if not value else _t("accent_green")))
            item.setData(1, Qt.ItemDataRole.UserRole, value)
        elif isinstance(value, (int, float)):
            item.setText(1, str(value))
            item.setForeground(1, QColor(_t("accent_org")))
            item.setData(1, Qt.ItemDataRole.UserRole, value)
        elif value is None:
            item.setText(1, "null")
            item.setForeground(1, QColor(_t("text_muted")))
            item.setData(1, Qt.ItemDataRole.UserRole, None)
        else:
            s = str(value)
            preview = s.replace("\n", " ")
            item.setText(1, preview[:120] + ("…" if len(preview) > 120 else ""))
            item.setForeground(1, QColor(_t("accent_green")))
            item.setData(1, Qt.ItemDataRole.UserRole, s)

        return item

class DropZone(QWidget):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(90)
        self._hovered = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(4)

        self._icon  = QLabel("⬇")
        self._label = QLabel("Drop .vmem file here")
        self._sub   = QLabel("or click Browse to select")

        for w in (self._icon, self._label, self._sub):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            w.setStyleSheet("background:transparent;")
        self._icon.setStyleSheet(f"font-size:28px; color:{_t('text_muted')}; background:transparent;")
        self._label.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(1)}px; background:transparent;")
        self._sub.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; background:transparent;")

        layout.addWidget(self._icon)
        layout.addWidget(self._label)
        layout.addWidget(self._sub)

    def refresh_styles(self):
        if self._icon.text() == "✓":
            self._icon.setStyleSheet(f"font-size:28px; color:{_t('accent_green')}; background:transparent;")
            self._label.setStyleSheet(f"color:{_t('text_primary')}; font-size:{_fs(1)}px; background:transparent;")
            self._sub.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; background:transparent;")
        else:
            self._icon.setStyleSheet(f"font-size:28px; color:{_t('text_muted')}; background:transparent;")
            self._label.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(1)}px; background:transparent;")
            self._sub.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; background:transparent;")
        self.update()

    def set_file(self, path: str):
        name = Path(path).name
        size = _fmt_size(Path(path).stat().st_size)
        self._icon.setText("✓")
        self._icon.setStyleSheet(f"font-size:28px; color:{_t('accent_green')}; background:transparent;")
        self._label.setText(name)
        self._label.setStyleSheet(f"color:{_t('text_primary')}; font-size:{_fs(1)}px; background:transparent;")
        self._sub.setText(size)
        self._sub.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; background:transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(_t("accent_blue") if self._hovered else _t("border"))
        bg    = QColor(_t("accent_blue") + "11" if self._hovered else _t("card_bg"))
        painter.fillRect(self.rect(), bg)
        pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 8, 8)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hovered = True
            self.update()

    def dragLeaveEvent(self, e):
        self._hovered = False
        self.update()

    def dropEvent(self, e: QDropEvent):
        self._hovered = False
        self.update()
        urls = e.mimeData().urls()
        if urls:
            self.file_dropped.emit(urls[0].toLocalFile())

class StatTile(QFrame):
    def __init__(self, count: int, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 84)
        self.setStyleSheet(
            f"QFrame {{ background:{_t('card_bg')}; border:1px solid {color}44;"
            f" border-left:3px solid {color}; border-radius:6px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        n = QLabel(str(count))
        n.setStyleSheet(f"color:{color}; font-size:{_fs(14)}px; font-weight:bold; border:none;")
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; border:none;")
        lbl.setWordWrap(True)
        layout.addWidget(n)
        layout.addWidget(lbl)

class SummaryTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._inner = QWidget()
        self._outer = QVBoxLayout(self._inner)
        self._outer.setContentsMargins(20, 20, 20, 20)
        self._outer.setSpacing(16)

        self._placeholder = QLabel("Load a memory image to see the summary.")
        self._placeholder.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(1)}px;")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._outer.addWidget(self._placeholder)
        self._outer.addStretch()

        scroll.setWidget(self._inner)
        root.addWidget(scroll)

    def populate(self, result: dict):
        while self._outer.count():
            item = self._outer.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        classified   = result["classified"]
        agent_cards  = result["agent_cards"]
        requests     = result["requests"]
        responses    = result["responses"]
        interactions = result["interactions"]
        partial_only = [r for r in responses if r.raw.get("_source") == "partial_regex"]

        info = QLabel(
            f"Image: <b>{result['image_name']}</b>  ({_fmt_size(result['image_size'])})"
        )
        info.setStyleSheet(f"color:{_t('text_primary')}; font-size:{_fs(1)}px;")
        self._outer.addWidget(info)

        tiles_row = QHBoxLayout()
        tiles_row.setSpacing(12)
        for count, label, color_key in [
            (len(agent_cards),                   "Agent Cards",      "accent_teal"),
            (len(classified["rpc_requests"]),    "RPC Requests",     "accent_blue"),
            (len(responses) - len(partial_only), "RPC Responses",    "accent_green"),
            (len(classified["artifact_updates"]),"Artifact Updates", "accent_purp"),
            (len(partial_only),                  "Partial (regex)",  "accent_org"),
            (len(interactions),                  "Interactions",     "accent_yel"),
        ]:
            tiles_row.addWidget(StatTile(count, label, _t(color_key)))
        tiles_row.addStretch()
        self._outer.addLayout(tiles_row)

        if agent_cards:
            grp = QGroupBox("Agent Cards Discovered")
            gl = QVBoxLayout(grp)
            gl.setSpacing(10)
            for card in agent_cards:
                gl.addWidget(self._card_widget(card))
            self._outer.addWidget(grp)

        if interactions:
            grp2 = QGroupBox("Interaction Index")
            g2l  = QVBoxLayout(grp2)
            for ix in interactions:
                state = ix.response.state.upper() if ix.response else "NO RESPONSE"
                sc = (_t("accent_green") if state == "COMPLETED"
                      else (_t("accent_red") if state == "FAILED" else _t("text_muted")))
                row = QHBoxLayout()
                row.setSpacing(8)
                num = QLabel(f"#{ix.index}")
                num.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; min-width:28px;")
                goal = ix.user_goal[:90] + ("…" if len(ix.user_goal) > 90 else "")
                goal_lbl = QLabel(goal)
                goal_lbl.setStyleSheet(f"color:{_t('text_primary')}; font-size:{_fs()}px;")
                row.addWidget(num)
                row.addWidget(_badge_label(state, sc))
                row.addWidget(_badge_label(ix.interaction_type.upper(), _t("accent_blue")))
                row.addWidget(goal_lbl)
                row.addStretch()
                g2l.addLayout(row)
            self._outer.addWidget(grp2)

        self._outer.addStretch()

    def _card_widget(self, card) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{_t('card_bg')}; border:1px solid {_t('accent_teal')}33;"
            f" border-left:3px solid {_t('accent_teal')}; border-radius:6px; padding:4px; }}"
        )
        layout = QVBoxLayout(frame)
        layout.setSpacing(5)

        h = QHBoxLayout()
        name = QLabel(card.name)
        name.setStyleSheet(
            f"color:{_t('accent_teal')}; font-size:{_fs(1)}px; font-weight:bold; border:none;"
        )
        url = QLabel(card.url)
        url.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; border:none;")
        h.addWidget(name)
        h.addWidget(url)
        h.addStretch()
        h.addWidget(_badge_label(f"A2A {card.protocol_version}", _t("accent_teal")))
        layout.addLayout(h)

        if card.description:
            desc = QLabel(card.description[:140])
            desc.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; border:none;")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        cap_row = QHBoxLayout()
        for k, v in card.capabilities.items():
            c = _t("accent_green") if v else _t("text_muted")
            cap = QLabel(f"{k}: {'✓' if v else '✗'}")
            cap.setStyleSheet(f"color:{c}; font-size:{_fs(-2)}px; border:none;")
            cap_row.addWidget(cap)
        cap_row.addStretch()
        layout.addLayout(cap_row)

        if card.skills:
            sk_row = QHBoxLayout()
            sk_row.setSpacing(4)
            for sk in card.skills:
                sk_row.addWidget(_badge_label(sk.get("name", sk.get("id","?")), _t("accent_teal")))
            sk_row.addStretch()
            layout.addLayout(sk_row)

        return frame

class _ClickableHeader(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        if self._hover:
            p = QPainter(self)
            p.fillRect(self.rect(), QColor(_t("accent_blue") + "12"))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

class _ResizeHandle(QWidget):

    def __init__(self, target: QWidget, parent=None):
        super().__init__(parent)
        self._target = target
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_h = 0
        self.setFixedHeight(10)
        self.setCursor(Qt.CursorShape.SizeVerCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(_t("card_bg")))
        p.fillRect(0, 0, self.width(), 1, QColor(_t("border")))
        cx, cy = self.width() // 2, self.height() // 2
        dot = QColor(_t("text_muted"))
        for dx in range(-20, 21, 5):
            p.fillRect(cx + dx - 1, cy - 1, 2, 2, dot)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = e.globalPosition().toPoint().y()
            h = self._target.height()
            self._drag_start_h = h if h > 20 else self._target.sizeHint().height()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._dragging:
            return
        dy = e.globalPosition().toPoint().y() - self._drag_start_y
        new_h = max(40, self._drag_start_h + dy)
        self._target.setFixedHeight(new_h)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(e)

class StepWidget(QFrame):

    def __init__(self, step_num: int, title: str, color: str, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.setStyleSheet(
            f"QFrame {{ background:{_t('card_bg')}; border:1px solid {color}33;"
            f" border-left:3px solid {color}; border-radius:6px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr_widget = _ClickableHeader()
        hdr_lay = QHBoxLayout(hdr_widget)
        hdr_lay.setContentsMargins(14, 9, 14, 9)
        hdr_lay.setSpacing(8)

        self._arrow = QLabel("▼")
        self._arrow.setStyleSheet(
            f"color:{color}; font-size:{_fs(-1)}px; min-width:14px; background:transparent;"
        )

        num_lbl = QLabel(f"STEP {step_num}")
        num_lbl.setStyleSheet(
            f"background:{color}22; color:{color}; border:1px solid {color}55;"
            f" border-radius:3px; padding:2px 8px; font-size:{_fs(-2)}px; font-weight:bold;"
        )
        num_lbl.setFixedHeight(22)

        ttl = QLabel(title)
        ttl.setStyleSheet(
            f"color:{_t('text_primary')}; font-size:{_fs(1)}px; font-weight:bold; background:transparent;"
        )

        hdr_lay.addWidget(self._arrow)
        hdr_lay.addWidget(num_lbl)
        hdr_lay.addWidget(ttl)
        hdr_lay.addStretch()
        hdr_widget.clicked.connect(self._toggle)
        outer.addWidget(hdr_widget)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{color}22; background:{color}22; max-height:1px;")
        outer.addWidget(sep)
        self._sep = sep

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(16, 8, 16, 12)
        self._body_layout.setSpacing(7)
        outer.addWidget(self._body)

        self._resize_handle = _ResizeHandle(self._body)
        outer.addWidget(self._resize_handle)

    def _toggle(self):
        self._collapsed = not self._collapsed
        expanded = not self._collapsed
        self._body.setVisible(expanded)
        self._sep.setVisible(expanded)
        self._resize_handle.setVisible(expanded)
        self._arrow.setText("▶" if self._collapsed else "▼")

    def add_row(self, key: str, value: str, value_color: str = ""):
        vc = value_color or _t("text_primary")
        row = QHBoxLayout()
        row.setSpacing(10)
        k = QLabel(key)
        k.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px;")
        k.setFixedWidth(150)
        v = QLabel(str(value))
        v.setStyleSheet(f"color:{vc}; font-size:{_fs()}px;")
        v.setWordWrap(True)
        row.addWidget(k)
        row.addWidget(v, 1)
        self._body_layout.addLayout(row)

    def add_badge_row(self, key: str, badges: list):
        row = QHBoxLayout()
        row.setSpacing(6)
        k = QLabel(key)
        k.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px;")
        k.setFixedWidth(150)
        row.addWidget(k)
        for text, color in badges:
            row.addWidget(_badge_label(text, color))
        row.addStretch()
        self._body_layout.addLayout(row)

    def add_text_block(self, text: str):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{_t('text_primary')}; font-size:{_fs(-1)}px;"
            f" background:{_t('dark_bg')}; border:1px solid {_t('border')};"
            f" border-radius:4px; padding:10px;"
            f" font-family:'Fira Code','Consolas','Courier New',monospace;"
        )
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body_layout.addWidget(lbl)

    def add_offset(self, offset: Optional[int], end_offset: Optional[int] = None):
        if offset is None:
            return
        s = f"0x{offset:08X}  ({offset:,} bytes)"
        if end_offset is not None:
            s += f"  →  0x{end_offset:08X}"
        row = QHBoxLayout()
        k = QLabel("Memory Offset")
        k.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px;")
        k.setFixedWidth(150)
        row.addWidget(k)
        row.addWidget(_mono_label(s))
        row.addStretch()
        self._body_layout.addLayout(row)

    def add_widget(self, widget: QWidget):
        self._body_layout.addWidget(widget)

class CollapsibleAgentCard(QFrame):

    def __init__(self, card, parent=None):
        super().__init__(parent)
        color = _t("accent_teal")
        self._collapsed = False
        self.setStyleSheet(
            f"QFrame {{ background:{_t('dark_bg')}; border:1px solid {color}33;"
            f" border-left:3px solid {color}; border-radius:5px; margin-bottom:4px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = _ClickableHeader()
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(10, 7, 10, 7)
        hdr_lay.setSpacing(8)

        self._arrow = QLabel("▼")
        self._arrow.setStyleSheet(
            f"color:{color}; font-size:{_fs(-1)}px; min-width:14px; background:transparent;"
        )
        name_lbl = QLabel(card.name)
        name_lbl.setStyleSheet(
            f"color:{color}; font-size:{_fs()}px; font-weight:bold; background:transparent;"
        )
        url_lbl = QLabel(card.url)
        url_lbl.setStyleSheet(
            f"color:{_t('text_muted')}; font-size:{_fs(-1)}px; background:transparent;"
        )
        proto = _badge_label(f"A2A {card.protocol_version}", color)

        hide_btn = QPushButton("✕")
        hide_btn.setFixedSize(22, 22)
        hide_btn.setToolTip("Hide this card  (use 'Agent' button in Step 1 to restore)")
        hide_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{_t('text_muted')};"
            f" border:1px solid {_t('border')}; border-radius:3px;"
            f" font-size:{_fs(-2)}px; padding:0; }}"
            f"QPushButton:hover {{ color:{_t('accent_red')}; border-color:{_t('accent_red')}; }}"
        )
        hide_btn.clicked.connect(self.hide)

        hdr_lay.addWidget(self._arrow)
        hdr_lay.addWidget(name_lbl)
        hdr_lay.addWidget(url_lbl)
        hdr_lay.addStretch()
        hdr_lay.addWidget(proto)
        hdr_lay.addWidget(hide_btn)
        hdr.clicked.connect(self._toggle)
        outer.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{color}22; background:{color}22; max-height:1px;")
        outer.addWidget(sep)
        self._sep = sep

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(12, 6, 12, 10)
        bl.setSpacing(5)

        if card.description:
            desc = QLabel(card.description)
            desc.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-1)}px;")
            desc.setWordWrap(True)
            bl.addWidget(desc)

        cap_row = QHBoxLayout()
        cap_row.setSpacing(16)
        for k, v in card.capabilities.items():
            c = _t("accent_green") if v else _t("text_muted")
            cap_lbl = QLabel(f"{k}: {'✓' if v else '✗'}")
            cap_lbl.setStyleSheet(f"color:{c}; font-size:{_fs(-2)}px;")
            cap_row.addWidget(cap_lbl)
        cap_row.addStretch()
        bl.addLayout(cap_row)

        if card.skills:
            sk_row = QHBoxLayout()
            sk_row.setSpacing(5)
            for sk in card.skills:
                sk_name = sk.get("name", sk.get("id", "?"))
                sk_row.addWidget(_badge_label(sk_name, color))
                ex = sk.get("examples", [])
                if ex:
                    ex_lbl = QLabel(f'e.g. "{ex[0][:50]}"')
                    ex_lbl.setStyleSheet(
                        f"color:{_t('text_muted')}; font-size:{_fs(-3)}px; font-style:italic;"
                    )
                    sk_row.addWidget(ex_lbl)
            sk_row.addStretch()
            bl.addLayout(sk_row)

        if card.provider:
            prov = card.provider.get("organization", "")
            if prov:
                p_lbl = QLabel(f"Provider: {prov}")
                p_lbl.setStyleSheet(f"color:{_t('text_muted')}; font-size:{_fs(-2)}px;")
                bl.addWidget(p_lbl)

        outer.addWidget(self._body)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._sep.setVisible(not self._collapsed)
        self._arrow.setText("▶" if self._collapsed else "▼")

class InteractionDetail(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._container = QWidget()
        self._vbox = QVBoxLayout(self._container)
        self._vbox.setContentsMargins(16, 16, 16, 16)
        self._vbox.setSpacing(14)
        self.setWidget(self._container)
        self._all_agent_cards: list = []

    def set_agent_cards(self, cards: list):
        self._all_agent_cards = cards

    def load(self, ix):
        while self._vbox.count():
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sc = (_t("accent_green") if (ix.response and ix.response.state == "completed")
              else _t("text_muted"))
        h = QHBoxLayout()
        title = QLabel(f"Interaction #{ix.index}")
        title.setStyleSheet(f"color:{_t('text_primary')}; font-size:{_fs(3)}px; font-weight:bold;")
        state_str = ix.response.state.upper() if ix.response else "NO RESPONSE"
        status_icon = "✓" if (ix.response and ix.response.state == "completed") else "?"
        h.addWidget(title)
        h.addWidget(_badge_label(f"{status_icon} {state_str}", sc))
        h.addWidget(_badge_label(ix.interaction_type.upper(), _t("accent_blue")))
        h.addStretch()
        self._vbox.addLayout(h)

        goal_lbl = QLabel(ix.user_goal)
        goal_lbl.setStyleSheet(
            f"color:{_t('text_primary')}; font-size:{_fs()}px;"
            f" background:{_t('dark_bg')}; border-radius:4px; padding:10px 14px;"
            f" border-left:3px solid {_t('accent_blue')};"
        )
        goal_lbl.setWordWrap(True)
        goal_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._vbox.addWidget(goal_lbl)

        s1 = StepWidget(
            1,
            "AGENT DISCOVERY  /.well-known/agent-card.json",
            _t("accent_teal"),
        )
        if self._all_agent_cards:
            _card_widgets: list[CollapsibleAgentCard] = []

            show_all_btn = QPushButton("↺  Agent")
            show_all_btn.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{_t('accent_teal')};"
                f" border:1px solid {_t('accent_teal')}55; border-radius:4px;"
                f" padding:3px 12px; font-size:{_fs(-1)}px; }}"
                f"QPushButton:hover {{ background:{_t('accent_teal')}18;"
                f" border-color:{_t('accent_teal')}; }}"
            )
            show_all_btn.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            show_all_btn.clicked.connect(
                lambda: [w.setVisible(True) for w in _card_widgets]
            )
            s1.add_widget(show_all_btn)

            for card in self._all_agent_cards:
                w = CollapsibleAgentCard(card)
                _card_widgets.append(w)
                s1.add_widget(w)
        else:
            s1.add_row("Status", "(no agent cards recovered)")
        self._vbox.addWidget(s1)

        s2 = StepWidget(2, "TASK SUBMISSION  JSON-RPC message/send", _t("accent_blue"))
        req = ix.request
        if req:
            s2.add_row("JSON-RPC id", req.rpc_id)
            s2.add_row("Message ID",  req.message_id or "(not recovered)")
            s2.add_offset(req.memory_offset)
            s2.add_row("Role",     req.role)
            s2.add_row("Blocking", str(req.blocking))
            if req.execution_mode:
                s2.add_row("Exec Mode",   req.execution_mode, _t("accent_org"))
            if req.target_agent:
                s2.add_row("Target Agent", req.target_agent, _t("accent_yel"))
            clean_req = {"jsonrpc": "2.0", "id": req.rpc_id,
                         "method": "message/send", "params": req.raw.get("params", {})}
            payload_str = json.dumps(clean_req, indent=2)
            if len(payload_str) > 1200:
                payload_str = payload_str[:1200] + "\n… (truncated)"
            s2.add_text_block(payload_str)
        else:
            s2.add_row("Status", "(request not recovered)")
        self._vbox.addWidget(s2)

        s3 = StepWidget(3, "TASK COMPLETION", _t("accent_purp"))
        resp = ix.response
        if resp:
            s3.add_row("Task ID",    resp.task_id)
            s3.add_row("Context ID", resp.context_id)
            s3.add_offset(resp.memory_offset)
            state_color = (_t("accent_green") if resp.state == "completed"
                           else (_t("accent_red") if resp.state == "failed"
                                 else _t("text_muted")))
            s3.add_row("Final State", resp.state.upper(), state_color)
            if resp.history:
                for entry in resp.history:
                    role = entry.get("role", "?")
                    rc = _t("accent_blue") if role == "user" else _t("accent_green")
                    parts = entry.get("parts", [])
                    text = ""
                    if parts:
                        for p in parts:
                            if p.get("kind") == "text":
                                text = p["text"][:200].replace("\n", " ")
                    elif "text" in entry:
                        text = entry["text"][:200].replace("\n", " ")
                    if text:
                        s3.add_row(f"[{role}]", f'"{text}"', rc)
            else:
                s3.add_row("History", "(not recovered)")
            plan_data = resp.embedded_plan
            if plan_data:
                plan = plan_data.get("plan", {})
                if isinstance(plan, dict) and plan:
                    s3.add_row("Exec Mode",   plan.get("execution_mode", "?"), _t("accent_org"))
                    s3.add_row("Target Agent",plan.get("target_agent", "?"),   _t("accent_yel"))
                    for step in plan.get("plan_steps", []):
                        s3.add_row(
                            f"Step {step.get('step')}",
                            f"agent={step.get('agent')}  skill={step.get('skill')}"
                        )
        else:
            s3.add_row("Status", "(task not recovered)")
        self._vbox.addWidget(s3)

        s4 = StepWidget(4, "RESULT", _t("accent_green"))
        if resp:
            s4.add_row("Resp Msg ID", resp.response_message_id or "(not recovered)")
            plan_data = resp.embedded_plan
            if plan_data:
                if plan_data.get("_partial"):
                    s4.add_row("Note", "[plan JSON truncated — key fields recovered by regex]",
                               _t("accent_org"))
                exec_mode = plan_data.get("execution_mode") or (
                    plan_data.get("plan", {}).get("execution_mode")
                    if isinstance(plan_data.get("plan"), dict) else None)
                tgt = plan_data.get("target_agent") or (
                    plan_data.get("plan", {}).get("target_agent")
                    if isinstance(plan_data.get("plan"), dict) else None)
                if exec_mode:
                    s4.add_row("Execution Mode", exec_mode, _t("accent_org"))
                if plan_data.get("discovery_type"):
                    s4.add_row("Discovery Type", plan_data["discovery_type"])
                if tgt:
                    s4.add_row("Target Agent", tgt, _t("accent_yel"))
                output = plan_data.get("agent_output", "")
                if output:
                    s4.add_text_block(str(output)[:2000])
                elif resp.response_text and not resp.response_text.strip().startswith('{'):
                    s4.add_text_block(resp.response_text[:2000])
            elif resp.response_text:
                s4.add_text_block(resp.response_text[:2000])
            if resp.artifacts:
                s4.add_row(f"Artifacts ({len(resp.artifacts)})",
                           ", ".join(a.get("name","?") for a in resp.artifacts))
        else:
            s4.add_row("Status", "(result not recovered)")
        self._vbox.addWidget(s4)
        self._vbox.addStretch()

class InteractionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        lv   = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 0, 8)
        lv.setSpacing(6)
        lv.addWidget(_section_label("Interactions"))

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["#", "Type", "State", "Goal"])
        self._tree.setColumnWidth(0, 36)
        self._tree.setColumnWidth(1, 160)
        self._tree.setColumnWidth(2, 100)
        self._tree.currentItemChanged.connect(self._on_select)
        lv.addWidget(self._tree)
        self._splitter.addWidget(left)

        self._detail = InteractionDetail()
        self._splitter.addWidget(self._detail)
        self._splitter.setSizes([320, 720])
        layout.addWidget(self._splitter)

        self._interactions = []

    def populate(self, result: dict):
        self._detail.set_agent_cards(result.get("agent_cards", []))

        self._interactions = result["interactions"]
        self._tree.clear()
        for ix in self._interactions:
            state = ix.response.state.upper() if ix.response else "NO RESP"
            goal_preview = ix.user_goal[:72] + ("…" if len(ix.user_goal) > 72 else "")
            item = QTreeWidgetItem([str(ix.index), ix.interaction_type, state, goal_preview])
            sc = (_t("accent_green") if state == "COMPLETED"
                  else (_t("accent_red") if state == "FAILED" else _t("text_muted")))
            item.setForeground(2, QColor(sc))
            item.setForeground(1, QColor(
                _t("accent_blue") if "direct" in ix.interaction_type else _t("accent_org")))
            self._tree.addTopLevelItem(item)
        if self._interactions:
            self._tree.setCurrentItem(self._tree.topLevelItem(0))

    def _on_select(self, current, previous):
        if not current:
            return
        idx = self._tree.indexOfTopLevelItem(current)
        if 0 <= idx < len(self._interactions):
            self._detail.load(self._interactions[idx])

TYPE_COLORS_KEYS = {
    "agent_card":     "accent_teal",
    "rpc_request":    "accent_blue",
    "rpc_response":   "accent_green",
    "artifact_update":"accent_purp",
    "partial":        "accent_org",
}

class RawObjectsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        filter_bar = QWidget()
        filter_bar.setObjectName("filterBar")
        filter_bar.setFixedHeight(40)
        fb = QHBoxLayout(filter_bar)
        fb.setContentsMargins(8, 4, 8, 4)
        fb.setSpacing(5)
        fb.addWidget(_section_label("Filter:"))

        self._filter_btns: dict[str, QPushButton] = {}
        for label, key, ck in [
            ("All",          "all",            "text_primary"),
            ("Agent Card",   "agent_card",     "accent_teal"),
            ("RPC Request",  "rpc_request",    "accent_blue"),
            ("RPC Response", "rpc_response",   "accent_green"),
            ("Artifact",     "artifact_update","accent_purp"),
            ("Partial",      "partial",        "accent_org"),
        ]:
            c = _t(ck)
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(
                f"QPushButton {{ background:{_t('card_bg')}; color:{c};"
                f" border:1px solid {c}44; border-radius:4px;"
                f" padding:2px 10px; font-size:{_fs(-2)}px; }}"
                f"QPushButton:checked {{ background:{c}22; border-color:{c}; }}"
                f"QPushButton:hover {{ background:{c}11; }}"
            )
            btn.clicked.connect(lambda checked, k=key: self._apply_filter(k))
            self._filter_btns[key] = btn
            fb.addWidget(btn)

        self._filter_btns["all"].setChecked(True)
        sep = QLabel("|")
        sep.setStyleSheet(f"color:{_t('border')}; font-size:{_fs(-2)}px;")
        fb.addWidget(sep)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setMinimumWidth(120)
        self._search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search.textChanged.connect(self._apply_search)
        fb.addWidget(self._search)
        fb.addStretch()
        layout.addWidget(filter_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        lv   = QVBoxLayout(left)
        lv.setContentsMargins(6, 6, 0, 6)
        self._obj_tree = QTreeWidget()
        self._obj_tree.setHeaderLabels(["Type", "Preview", "Offset"])
        self._obj_tree.setColumnWidth(0, 120)
        self._obj_tree.setColumnWidth(1, 210)
        self._obj_tree.setColumnWidth(2, 140)
        self._obj_tree.currentItemChanged.connect(self._on_obj_select)
        lv.addWidget(self._obj_tree)
        splitter.addWidget(left)

        right = QWidget()
        rv    = QVBoxLayout(right)
        rv.setContentsMargins(0, 6, 6, 6)
        rv.setSpacing(6)

        dh = QHBoxLayout()
        dh.setContentsMargins(6, 0, 6, 0)
        self._type_badge   = _badge_label("—", _t("text_muted"))
        self._offset_badge = _mono_label("—")
        self._copy_btn     = QPushButton("Copy JSON")
        self._copy_btn.setMinimumWidth(70)
        self._copy_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._copy_btn.clicked.connect(self._copy_json)
        dh.addWidget(self._type_badge)
        dh.addWidget(self._offset_badge)
        dh.addStretch()
        dh.addWidget(self._copy_btn)
        rv.addLayout(dh)

        v_split = QSplitter(Qt.Orientation.Vertical)

        self._json_tree = JsonTreeWidget()
        self._json_tree.currentItemChanged.connect(self._on_json_item_change)
        v_split.addWidget(self._json_tree)

        self._full_text = QTextEdit()
        self._full_text.setReadOnly(True)
        self._full_text.setPlaceholderText(
            "Click any value in the tree above to see its full text here…"
        )
        self._full_text.setStyleSheet(
            f"QTextEdit {{"
            f" background:{_t('dark_bg')}; color:{_t('text_primary')};"
            f" border:none; border-top:1px solid {_t('border')};"
            f" font-family:'Fira Code','Consolas','Courier New',monospace;"
            f" font-size:{_fs(-1)}px; padding:8px;"
            f"}}"
        )
        self._full_text.setMinimumHeight(60)
        v_split.addWidget(self._full_text)
        v_split.setSizes([480, 160])

        rv.addWidget(v_split)
        splitter.addWidget(right)
        splitter.setSizes([380, 660])
        layout.addWidget(splitter)

        self._all_items: list[tuple[str, dict]] = []
        self._current_obj: Optional[dict] = None
        self._current_filter = "all"

    def populate(self, result: dict):
        classified = result["classified"]
        responses  = result["responses"]
        self._all_items = []
        for o in classified["agent_cards"]:
            self._all_items.append(("agent_card",     o))
        for o in classified["rpc_requests"]:
            self._all_items.append(("rpc_request",    o))
        for o in classified["rpc_responses"]:
            self._all_items.append(("rpc_response",   o))
        for o in classified["artifact_updates"]:
            self._all_items.append(("artifact_update",o))
        for r in responses:
            if r.raw.get("_source") == "partial_regex":
                self._all_items.append(("partial", r.raw))
        self._rebuild_list()

    def _rebuild_list(self):
        self._obj_tree.clear()
        search = self._search.text().lower()
        filt   = self._current_filter
        for type_key, raw in self._all_items:
            if filt != "all" and type_key != filt:
                continue
            raw_str = json.dumps(raw)
            if search and search not in raw_str.lower():
                continue
            color = _t(TYPE_COLORS_KEYS.get(type_key, "text_muted"))
            preview = ""
            for k in ("name", "method", "state", "_preview"):
                if k in raw:
                    preview = str(raw[k])[:60]
                    break
            if not preview:
                r = raw.get("result", {})
                if isinstance(r, dict):
                    preview = r.get("id", "")[:40]
            if not preview:
                preview = raw_str[:60]
            offset = raw.get("_memory_offset")
            offset_str = f"0x{offset:08X}" if offset is not None else "(regex)"
            item = QTreeWidgetItem([type_key.replace("_"," ").title(), preview, offset_str])
            item.setForeground(0, QColor(color))
            item.setData(0, Qt.ItemDataRole.UserRole, raw)
            self._obj_tree.addTopLevelItem(item)

    def _apply_filter(self, key: str):
        self._current_filter = key
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == key)
        self._rebuild_list()

    def _on_json_item_change(self, current, previous):
        if not current:
            self._full_text.clear()
            return
        raw_val = current.data(1, Qt.ItemDataRole.UserRole)
        if isinstance(raw_val, (dict, list)):
            self._full_text.setPlainText(json.dumps(raw_val, indent=2))
        elif raw_val is None:
            self._full_text.setPlainText("null")
        else:
            self._full_text.setPlainText(str(raw_val))

    def _apply_search(self, _):
        self._rebuild_list()

    def _on_obj_select(self, current, previous):
        if not current:
            return
        raw = current.data(0, Qt.ItemDataRole.UserRole)
        if raw is None:
            return
        self._current_obj = raw
        type_key = raw.get("_a2a_type") or (
            "partial" if raw.get("_source") == "partial_regex" else "unknown")
        color = _t(TYPE_COLORS_KEYS.get(type_key, "text_muted"))
        self._type_badge.setText(type_key.replace("_"," ").title())
        self._type_badge.setStyleSheet(
            f"background:{color}22; color:{color}; border:1px solid {color}55;"
            f" border-radius:4px; padding:2px 8px; font-size:{_fs(-2)}px; font-weight:bold;"
        )
        offset = raw.get("_memory_offset")
        end    = raw.get("_memory_offset_end")
        if offset is not None:
            s = f"0x{offset:08X}  ({offset:,} B)"
            if end is not None:
                s += f"  →  0x{end:08X}"
            self._offset_badge.setText(s)
        else:
            self._offset_badge.setText("(partial — regex extraction)")
        clean = {k: v for k, v in raw.items() if not k.startswith("_")}
        self._json_tree.load(clean)

    def _copy_json(self):
        if self._current_obj is None:
            return
        clean = {k: v for k, v in self._current_obj.items() if not k.startswith("_")}
        QApplication.clipboard().setText(json.dumps(clean, indent=2))

class MemoryMapWidget(QWidget):
    object_selected = pyqtSignal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self._items: list[tuple[str, int, dict]] = []
        self._max_offset = 1
        self._hovered_idx = -1
        self.setMouseTracking(True)

    def load(self, items: list, image_size: int):
        self._items = [(t, o, r) for t, o, r in items if o >= 0]
        self._max_offset = max(image_size, 1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w  = self.width() - 48
        h  = self.height()
        x0 = 24
        bar_y = h // 2 - 12
        bar_h = 24

        painter.fillRect(x0, bar_y, w, bar_h, QColor(_t("card_bg")))
        painter.setPen(QPen(QColor(_t("border")), 1))
        painter.drawRect(x0, bar_y, w, bar_h)

        tick_w = max(2, w // 500)
        for i, (type_key, offset, _) in enumerate(self._items):
            frac = offset / self._max_offset
            x    = int(x0 + frac * w)
            color = QColor(_t(TYPE_COLORS_KEYS.get(type_key, "text_muted")))
            if i == self._hovered_idx:
                color = color.lighter(160)
                painter.fillRect(x - 1, bar_y - 5, tick_w + 2, bar_h + 10, color)
            else:
                painter.fillRect(x, bar_y, tick_w, bar_h, color)

        font = QFont()
        font.setPointSize(max(8, _fs() - 4))
        painter.setFont(font)
        fm = QFontMetrics(font)

        painter.setPen(QColor(_t("text_muted")))
        painter.drawText(x0, bar_y + bar_h + 18, "0x00000000")
        end_lbl = f"0x{self._max_offset:08X}"
        painter.drawText(x0 + w - fm.horizontalAdvance(end_lbl), bar_y + bar_h + 18, end_lbl)

        legend_x = x0
        legend_y = bar_y - 32
        for type_key, label in [
            ("agent_card",      "Agent Card"),
            ("rpc_request",     "RPC Request"),
            ("rpc_response",    "RPC Response"),
            ("artifact_update", "Artifact"),
            ("partial",         "Partial"),
        ]:
            color = QColor(_t(TYPE_COLORS_KEYS.get(type_key, "text_muted")))
            painter.fillRect(legend_x, legend_y + 4, 12, 12, color)
            painter.setPen(QColor(_t("text_muted")))
            painter.drawText(legend_x + 16, legend_y + 15, label)
            legend_x += fm.horizontalAdvance(label) + 32

        if self._hovered_idx >= 0:
            type_key, offset, _ = self._items[self._hovered_idx]
            tooltip = f"{type_key.replace('_',' ').title()}  0x{offset:08X}"
            frac    = offset / self._max_offset
            tx      = int(x0 + frac * w)
            ty      = bar_y - 54
            tw      = fm.horizontalAdvance(tooltip) + 18
            painter.setBrush(QBrush(QColor(_t("card_bg"))))
            painter.setPen(QPen(QColor(_t("border")), 1))
            painter.drawRoundedRect(tx - tw // 2, ty, tw, 24, 4, 4)
            painter.setPen(QColor(_t("text_primary")))
            painter.drawText(tx - tw // 2 + 9, ty + 16, tooltip)

    def mouseMoveEvent(self, event):
        w  = self.width() - 48
        x0 = 24
        mx = event.position().x()
        if not self._items or w <= 0:
            return
        best_idx, best_dist = -1, 999999
        for i, (_, offset, _) in enumerate(self._items):
            tx   = x0 + (offset / self._max_offset) * w
            dist = abs(mx - tx)
            if dist < best_dist:
                best_dist = dist
                best_idx  = i
        self._hovered_idx = best_idx if best_dist < 14 else -1
        self.update()

    def mousePressEvent(self, event):
        if self._hovered_idx >= 0:
            type_key, _, raw = self._items[self._hovered_idx]
            self.object_selected.emit(type_key, raw)

    def leaveEvent(self, event):
        self._hovered_idx = -1
        self.update()

class MemoryMapTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(_section_label("Memory Layout — hover to inspect, click to select"))
        self._map = MemoryMapWidget()
        layout.addWidget(self._map)
        layout.addWidget(_section_label("Selected Object"))
        self._json_tree = JsonTreeWidget()
        layout.addWidget(self._json_tree)
        self._map.object_selected.connect(self._on_select)

    def populate(self, result: dict):
        classified = result["classified"]
        responses  = result["responses"]
        image_size = result["image_size"]
        items = []
        for raw in classified["agent_cards"]:
            items.append(("agent_card",     raw.get("_memory_offset", -1), raw))
        for raw in classified["rpc_requests"]:
            items.append(("rpc_request",    raw.get("_memory_offset", -1), raw))
        for raw in classified["rpc_responses"]:
            items.append(("rpc_response",   raw.get("_memory_offset", -1), raw))
        for raw in classified["artifact_updates"]:
            items.append(("artifact_update",raw.get("_memory_offset", -1), raw))
        for r in responses:
            if r.raw.get("_source") == "partial_regex":
                items.append(("partial", -1, r.raw))
        self._map.load(items, image_size)

    def _on_select(self, type_key: str, raw: dict):
        clean = {k: v for k, v in raw.items() if not k.startswith("_")}
        self._json_tree.load(clean, label=type_key)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A2A-MemForensics")
        self.resize(1340, 900)
        self._worker: Optional[AnalysisWorker] = None
        self._result: Optional[dict] = None
        self._image_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(56)
        tb = QHBoxLayout(top_bar)
        tb.setContentsMargins(18, 0, 18, 0)
        tb.setSpacing(12)

        title = QLabel("⬡  A2A-MemForensics")
        title.setObjectName("titleLabel")
        tb.addWidget(title)
        tb.addStretch()

        self._settings_btn = QPushButton("⚙  Settings")
        self._settings_btn.setMinimumWidth(80)
        self._settings_btn.clicked.connect(self._open_settings)
        tb.addWidget(self._settings_btn)

        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setMinimumWidth(70)
        self._browse_btn.clicked.connect(self._browse_file)
        tb.addWidget(self._browse_btn)

        self._analyze_btn = QPushButton("▶  Analyze")
        self._analyze_btn.setObjectName("analyzeBtn")
        self._analyze_btn.setMinimumWidth(80)
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.clicked.connect(self._start_analysis)
        tb.addWidget(self._analyze_btn)

        ml.addWidget(top_bar)

        drop_container = QWidget()
        drop_container.setObjectName("dropContainer")
        drop_container.setFixedHeight(136)
        dc = QVBoxLayout(drop_container)
        dc.setContentsMargins(18, 8, 18, 8)
        dc.setSpacing(6)

        self._drop_zone = DropZone()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        dc.addWidget(self._drop_zone)

        prog_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_lbl = QLabel("Ready.")
        self._progress_lbl.setObjectName("progressLabel")
        self._progress_lbl.setFixedWidth(400)
        prog_row.addWidget(self._progress_bar)
        prog_row.addWidget(self._progress_lbl)
        dc.addLayout(prog_row)

        ml.addWidget(drop_container)

        self._tabs = QTabWidget()
        self._summary_tab      = SummaryTab()
        self._interactions_tab = InteractionsTab()
        self._raw_tab          = RawObjectsTab()
        self._map_tab          = MemoryMapTab()
        self._tabs.addTab(self._summary_tab,       "  Summary  ")
        self._tabs.addTab(self._interactions_tab,  "  Interactions  ")
        self._tabs.addTab(self._raw_tab,           "  Raw Objects  ")
        self._tabs.addTab(self._map_tab,           "  Memory Map  ")
        ml.addWidget(self._tabs)

        self._status = QStatusBar()
        self._status.showMessage("No image loaded.")
        self.setStatusBar(self._status)

    def _open_settings(self):
        dlg = SettingsDialog(dict(_CS), parent=self)
        dlg.settings_applied.connect(self._apply_settings)
        dlg.exec()

    def _apply_settings(self, s: dict):
        _CS.clear()
        _CS.update(s)
        save_settings(s)
        QApplication.instance().setStyleSheet(build_app_style())
        ff = _ff()
        QApplication.instance().setFont(QFont(ff.split(",")[0].strip(), _fs()))
        self._drop_zone.refresh_styles()
        if self._result:
            self._summary_tab.populate(self._result)
            self._interactions_tab.populate(self._result)
            self._raw_tab.populate(self._result)
            self._map_tab.populate(self._result)
            self._map_tab._map.update()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            self._toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Memory Image", str(Path.home()),
            "Memory images (*.vmem *.mem *.raw *.bin);;All files (*)"
        )
        if path:
            self._set_image(path)

    def _on_file_dropped(self, path: str):
        self._set_image(path)

    def _set_image(self, path: str):
        self._image_path = path
        self._drop_zone.set_file(path)
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("Ready to analyze.")
        self._status.showMessage(
            f"Image: {Path(path).name}  ({_fmt_size(Path(path).stat().st_size)})"
        )

    def _start_analysis(self):
        if not self._image_path:
            return
        self._analyze_btn.setEnabled(False)
        self._browse_btn.setEnabled(False)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("Starting…")
        self._worker = AnalysisWorker(self._image_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, msg: str, pct: int):
        self._progress_bar.setValue(pct)
        self._progress_lbl.setText(msg)
        self._status.showMessage(msg)

    def _on_finished(self, result: dict):
        self._result = result
        self._analyze_btn.setEnabled(True)
        self._browse_btn.setEnabled(True)
        self._progress_bar.setValue(100)
        self._progress_lbl.setText("Analysis complete.")
        cards = result["agent_cards"]
        resps = result["responses"]
        ixs   = result["interactions"]
        self._status.showMessage(
            f"{result['image_name']}  —  "
            f"{len(cards)} agent cards  |  "
            f"{len(result['requests'])} requests  |  "
            f"{len(resps)} responses  |  "
            f"{len(ixs)} interactions"
        )
        self._summary_tab.populate(result)
        self._interactions_tab.populate(result)
        self._raw_tab.populate(result)
        self._map_tab.populate(result)
        self._tabs.setCurrentIndex(0)

    def _on_error(self, tb: str):
        self._analyze_btn.setEnabled(True)
        self._browse_btn.setEnabled(True)
        self._progress_bar.setValue(0)
        self._progress_lbl.setText("Error during analysis.")
        QMessageBox.critical(self, "Analysis Error", tb)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("A2A-MemForensics")

    s = load_settings()
    _CS.update(s)
    app.setStyleSheet(build_app_style())
    ff = _ff()
    app.setFont(QFont(ff.split(",")[0].strip(), _fs()))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
