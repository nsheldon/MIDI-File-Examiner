#!/usr/bin/env python3
"""
MIDI File Examiner — GUI Frontend
A PyQt6-based graphical interface for the MIDI File Examiner.
"""

import sys
import os
import io
import contextlib

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget,
        QVBoxLayout, QHBoxLayout,
        QPushButton, QLineEdit, QTextEdit, QFileDialog,
    )
    from PyQt6.QtGui import QFont, QKeySequence, QAction, QDragEnterEvent, QDropEvent
    from PyQt6.QtCore import Qt, QUrl, QThread, pyqtSignal
except ImportError:
    print("Error: PyQt6 is required. Install it with: pip install PyQt6")
    sys.exit(1)

# Ensure the directory containing this script is on the path so that
# midi_examiner and midi_patches_db can always be found.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from midi_examiner import __version__, analyze_midi_file, print_results


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

        # Results area
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        font = QFont("Menlo")
        if not font.exactMatch():
            font = QFont("Courier New")
        font.setPointSize(11)
        self.results_view.setFont(font)
        layout.addWidget(self.results_view)

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
        self.results_view.clear()
        self.open_button.setEnabled(False)
        self.statusBar().showMessage("Analyzing…")

        self.worker = AnalysisWorker(path)
        self.worker.finished.connect(self._on_analysis_done)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_done(self, text):
        self.results_view.setPlainText(text)
        self.results_view.moveCursor(self.results_view.textCursor().MoveOperation.Start)
        self.open_button.setEnabled(True)
        self.statusBar().showMessage("Analysis complete.")

    def _on_analysis_error(self, message):
        self.results_view.setPlainText(f"Error: {message}")
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
    app = QApplication(sys.argv)
    app.setApplicationName("MIDI File Examiner")
    app.setApplicationVersion(__version__)

    window = MidiExaminerWindow()
    window.show()

    # If a file path was passed as a command-line argument, open it immediately.
    if len(sys.argv) > 1:
        window.analyze(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
