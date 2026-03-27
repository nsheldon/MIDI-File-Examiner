#!/usr/bin/env python3
"""
MIDI File Examiner — GUI Frontend
A PyQt6-based graphical interface for the MIDI File Examiner.
"""

import sys
import os
import io
import re
import contextlib

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget,
        QVBoxLayout, QHBoxLayout,
        QPushButton, QLineEdit, QTextEdit, QFileDialog, QTabWidget,
    )
    from PyQt6.QtGui import (QFont, QKeySequence, QAction,
                              QDragEnterEvent, QDropEvent,
                              QFileOpenEvent, QPalette, QColor)
    from PyQt6.QtCore import Qt, QEvent, QThread, pyqtSignal
except ImportError:
    print("Error: PyQt6 is required. Install it with: pip install PyQt6")
    sys.exit(1)

# Ensure the directory containing this script is on the path so that
# midi_examiner and midi_patches_db can always be found.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from midi_examiner import __version__, analyze_midi_file, print_results

# Mapping from ALL-CAPS section titles (as printed) to shorter tab labels.
_TAB_LABELS = {
    "FILE INFORMATION": "File Info",
    "TIMING INFORMATION": "Timing",
    "METADATA": "Metadata",
    "TRACK INFORMATION": "Tracks",
    "TEXT EVENTS": "Text Events",
    "MARKERS": "Markers",
    "CUE POINTS": "Cue Points",
    "LYRICS": "Lyrics",
    "SYSTEM EXCLUSIVE (SYSEX) MESSAGES": "SysEx",
    "BANK SELECT MESSAGES": "Bank Select",
    "PROGRAM CHANGES": "Programs",
    "CONTROL CHANGES": "Control Changes",
}


def _split_sections(text):
    """Split print_results() output into [(tab_label, body_text), ...] pairs.

    Section headers are delimited by lines of 60 '=' characters. Any text
    before the first header (e.g. warnings) becomes a 'Warnings' tab.
    """
    # re.split with a capturing group interleaves titles with body text:
    # [pre, title1, body1, title2, body2, ...]
    parts = re.split(r'\n={60}\n ([^\n]+)\n={60}', text)
    sections = []

    pre = parts[0].strip('\n')
    if pre.strip():
        sections.append(("Warnings", pre))

    for i in range(1, len(parts), 2):
        raw_title = parts[i].strip()
        body = parts[i + 1].strip('\n') if i + 1 < len(parts) else ""
        # Skip footer sentinels like "END OF ANALYSIS" that have no body
        if not body.strip():
            continue
        label = _TAB_LABELS.get(raw_title, raw_title.title())
        sections.append((label, body))

    return sections


class AnalysisWorker(QThread):
    """Run MIDI analysis in a background thread to keep the UI responsive."""

    finished = pyqtSignal(str)   # emits formatted text output
    error = pyqtSignal(str)      # emits error message

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath

    def run(self):
        try:
            results = analyze_midi_file(self.filepath)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                print_results(results)
            self.finished.emit(output.getvalue())
        except Exception as e:
            self.error.emit(str(e))


# ── appearance helpers ────────────────────────────────────────────────────────

def _is_dark_mode(app):
    """Return True when the OS is currently in dark mode.

    On macOS the Qt platform plugin may not have finished initialising when
    this is first called, so styleHints/palette are unreliable at that point.
    Reading the preference directly with 'defaults' is immediate and works on
    all macOS versions regardless of Qt state.
    """
    if sys.platform == "darwin":
        import subprocess
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip().lower() == "dark"
        except Exception:
            pass
    # Non-macOS or 'defaults' unavailable: fall back to Qt APIs
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        pass
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _dark_palette():
    """Return a QPalette suitable for Fusion dark mode."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(25,  25,  25))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(40,  40,  40))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(53,  53,  53))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.BrightText,      Qt.GlobalColor.red)
    p.setColor(QPalette.ColorRole.Link,            QColor(42,  130, 218))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(42,  130, 218))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(240, 240, 240))
    disabled = QPalette.ColorGroup.Disabled
    p.setColor(disabled, QPalette.ColorRole.WindowText,      QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.Text,            QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.ButtonText,      QColor(127, 127, 127))
    p.setColor(disabled, QPalette.ColorRole.Highlight,       QColor(80,  80,  80))
    p.setColor(disabled, QPalette.ColorRole.HighlightedText, QColor(127, 127, 127))
    return p


def _apply_appearance(app):
    """Set Fusion style and match palette to the current OS appearance."""
    app.setStyle("Fusion")
    if _is_dark_mode(app):
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())


class MidiApplication(QApplication):
    """QApplication subclass that handles macOS file-open Apple Events.

    When a file is dropped onto the Dock icon or opened via a file
    association, macOS delivers an application:openFiles: Apple Event.
    Qt translates this into a QFileOpenEvent, which must be caught here
    (not in the window) because it can arrive before the window exists.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self._window = None
        self._pending_file = None
        _apply_appearance(self)
        # Re-apply when the user switches OS appearance at runtime (Qt 6.5+)
        try:
            self.styleHints().colorSchemeChanged.connect(
                lambda _scheme: _apply_appearance(self)
            )
        except AttributeError:
            pass  # Qt < 6.5 — appearance is applied once at startup

    def set_window(self, window):
        self._window = window
        if self._pending_file:
            window.analyze(self._pending_file)
            self._pending_file = None

    def event(self, e):
        if isinstance(e, QFileOpenEvent):
            path = e.file()
            if path:
                if self._window:
                    self._window.analyze(path)
                else:
                    self._pending_file = path
            return True
        return super().event(e)


class MidiExaminerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MIDI File Examiner {__version__}")
        self.setMinimumSize(900, 680)
        self.worker = None

        self._build_menu()
        self._build_ui()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self):
        menu = self.menuBar()

        file_menu = menu.addMenu("File")

        open_action = QAction("Open…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _make_text_view(self):
        """Create a styled read-only monospace QTextEdit for a section tab."""
        view = QTextEdit()
        view.setReadOnly(True)
        font = QFont("Menlo")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setPointSize(11)
        view.setFont(font)
        return view

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # File selection bar
        file_bar = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select a MIDI file or drag one here…")
        self.file_path_edit.setReadOnly(True)
        self.open_button = QPushButton("Open…")
        self.open_button.clicked.connect(self.open_file_dialog)
        file_bar.addWidget(self.file_path_edit)
        file_bar.addWidget(self.open_button)
        layout.addLayout(file_bar)

        # Tabbed results area — one tab per analysis section
        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        layout.addWidget(self.tab_widget)

        self.statusBar().showMessage("Ready — open a MIDI file to begin.")

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MIDI File",
            "",
            "MIDI Files (*.mid *.midi);;All Files (*)",
        )
        if path:
            self.analyze(path)

    def analyze(self, path):
        if self.worker and self.worker.isRunning():
            return

        self.file_path_edit.setText(path)
        self.tab_widget.clear()
        self.open_button.setEnabled(False)
        self.statusBar().showMessage("Analyzing…")

        self.worker = AnalysisWorker(path)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, text):
        for label, content in _split_sections(text):
            view = self._make_text_view()
            view.setPlainText(content)
            view.moveCursor(view.textCursor().MoveOperation.Start)
            idx = self.tab_widget.addTab(view, label)
            # Gray out tabs whose only content is a "nothing found" placeholder
            if re.match(r'^\s*\(No .+ found\)\s*$', content):
                self.tab_widget.setTabEnabled(idx, False)
        self.open_button.setEnabled(True)
        self.statusBar().showMessage("Analysis complete.")

    def _on_analysis_error(self, message):
        view = self._make_text_view()
        view.setPlainText(f"Error: {message}")
        self.tab_widget.addTab(view, "Error")
        self.open_button.setEnabled(True)
        self.statusBar().showMessage("Error during analysis.")

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith((".mid", ".midi")):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        path = event.mimeData().urls()[0].toLocalFile()
        self.analyze(path)


def main():
    app = MidiApplication(sys.argv)
    app.setApplicationName("MIDI File Examiner")
    app.setApplicationVersion(__version__)

    window = MidiExaminerWindow()
    app.set_window(window)
    window.show()

    # If a file path was passed as a command-line argument, open it immediately.
    if len(sys.argv) > 1:
        window.analyze(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
