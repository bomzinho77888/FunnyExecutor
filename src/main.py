import json
import os.path
import shutil
import sys

from design import Ui_MainWindow

from PySide6.QtCore import QTimer, Qt, QRect
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QTextEdit,
    QLabel, QPushButton, QWidget, QVBoxLayout, QFrame
)
from extras import CodeEditor, MessageBox

import FAPI

executor: FAPI.Executor | None = None
sdk: FAPI.sdk.Roblox | None = None


def load_exec():
    global executor
    global sdk
    if FAPI.roblox_open():
        executor = FAPI.Executor()
        sdk = executor.sdk


def unload_exec():
    global executor
    global sdk
    executor, sdk = None, None


class Window(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self._injecting = False
        self._warned = False
        self._console_visible = False
        self._log_count = 0

        self._setup_console()

        def inject():
            try:
                load_exec()
            except:
                unload_exec()
            if not executor:
                MessageBox.warning("Injection failed", "You must have Roblox open to inject")
                return
            if sdk.datamodel.name != 'Ugc':
                print(sdk.datamodel.name)
                MessageBox.warning("Injection failed", "You must be in-game to inject")
                return
            if executor.injected:
                MessageBox.information("Injection failed", "Already injected")
                return
            if self._injecting:
                return
            self._injecting = True
            executor.inject()
            self._injecting = False

        def execute():
            if not executor or not executor.injected:
                MessageBox.warning("Execution failed", "You must inject before executing")
                return
            script = self._get_current_editor().toPlainText()
            executor.execute(script)

        def update_status():
            if executor:
                if executor.injected:
                    self.statusLabel.setStyleSheet("color: rgb(50,200,50);")
                else:
                    self.statusLabel.setStyleSheet("color: rgb(200,50,50);")
            else:
                self.statusLabel.setStyleSheet("color: rgb(200,50,50);")
            self.statusLabel.update()

        def import_luau():
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open File", "", "Luau Script (*.luau; *.lua);;All Files (*)"
            )
            editor = self._get_current_editor()
            if file_path and editor:
                with open(file_path, 'r', encoding='utf-8') as f:
                    editor.setPlainText(f.read())

        def export_luau():
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", "", "Luau source files (*.lua; *.luau);;All Files (*)"
            )
            editor = self._get_current_editor()
            if file_path and editor:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(editor.toPlainText())

        self._tab_number = 0

        def new_tab(name=None, content=None):
            return self._add_tab(name, content)

        def close_tab(index):
            widget = self.tabWidget.widget(index)
            widget.deleteLater()
            self.tabWidget.removeTab(index)
            if self.tabWidget.count() == 0:
                self._tab_number = 1
                self._add_tab("Script #1")

        def ontop():
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.actionTop_Most.isChecked())
            self.show()

        self.injectButton.clicked.connect(inject)
        self.executeButton.clicked.connect(execute)
        self.importButton.clicked.connect(import_luau)
        self.exportButton.clicked.connect(export_luau)
        self.newTabButton.clicked.connect(lambda: self.tabWidget.setCurrentIndex(new_tab()))

        self.actionExit_Alt_F4.triggered.connect(QApplication.quit)
        self.actionExport.triggered.connect(export_luau)
        self.actionImport.triggered.connect(import_luau)
        self.actionInject.triggered.connect(inject)
        self.actionExecute.triggered.connect(execute)
        self.actionNew_Tab.triggered.connect(lambda: new_tab())
        self.actionSave_Tabs.triggered.connect(lambda: self._save_tabs())
        self.actionClear_Tabs.triggered.connect(self._clear_tabs)
        self.actionTop_Most.triggered.connect(ontop)
        self.tabWidget.tabCloseRequested.connect(close_tab)

        self._load_tabs()

        try:
            load_exec()
        except:
            unload_exec()

        update_status()
        ontop()

        timer_update = QTimer(self)
        timer_update.timeout.connect(update_status)
        timer_update.start(1000)

        timer_autosave = QTimer(self)
        timer_autosave.timeout.connect(self._save_tabs)
        timer_autosave.start(10000)

        timer_poll = QTimer(self)
        timer_poll.timeout.connect(self._poll_logs)
        timer_poll.start(200)

    def _setup_console(self):
        self.consoleToggleButton = QPushButton("Console", self.centralwidget)
        self.consoleToggleButton.setObjectName("consoleToggleButton")
        self.consoleToggleButton.setGeometry(QRect(270, 500, 81, 26))
        self.consoleToggleButton.clicked.connect(self._toggle_console)

        self.consolePanel = QWidget(self.centralwidget)
        self.consolePanel.setObjectName("consolePanel")
        self.consolePanel.setGeometry(QRect(10, 35, 821, 200))
        self.consolePanel.hide()

        layout = QVBoxLayout(self.consolePanel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet("background-color: #101318; border-bottom: 1px solid #1a1d24;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 0, 8, 0)

        server_status = QLabel("●  localhost:9475")
        server_status.setStyleSheet("color: #48d597; font-size: 10px; background: transparent;")
        toolbar_layout.addWidget(server_status)

        self.logCountLabel = QLabel("0 logs")
        self.logCountLabel.setStyleSheet("color: #68717d; font-size: 10px; background: transparent;")
        toolbar_layout.addWidget(self.logCountLabel)

        toolbar_layout.addStretch()

        clearBtn = QPushButton("Limpar")
        clearBtn.setFixedSize(60, 22)
        clearBtn.setStyleSheet(
            "QPushButton { background: #181c22; color: #cbd1d9; border: none; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background: #222832; }"
        )
        clearBtn.clicked.connect(self._clear_logs)
        toolbar_layout.addWidget(clearBtn)

        copyBtn = QPushButton("Copiar")
        copyBtn.setFixedSize(60, 22)
        copyBtn.setStyleSheet(
            "QPushButton { background: #181c22; color: #cbd1d9; border: none; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background: #222832; }"
        )
        copyBtn.clicked.connect(self._copy_logs)
        toolbar_layout.addWidget(copyBtn)

        layout.addWidget(toolbar)

        self.consoleText = QTextEdit()
        self.consoleText.setReadOnly(True)
        self.consoleText.setStyleSheet(
            "QTextEdit { background-color: #0b0d10; color: #d7dce2; border: none;"
            "font-family: Consolas; font-size: 11px; padding: 8px; }"
        )
        layout.addWidget(self.consoleText)

    @staticmethod
    def _normalize_type(value):
        value = str(value)
        if "Warning" in value:
            return "WARN"
        if "Error" in value:
            return "ERROR"
        if "Output" in value:
            return "OUTPUT"
        return value.upper()

    def _clear_logs(self):
        self._log_count = 0
        self.consoleText.clear()
        self.logCountLabel.setText("0 logs")

    def _copy_logs(self):
        content = self.consoleText.toPlainText()
        QApplication.clipboard().setText(content)

    def _toggle_console(self):
        self._console_visible = not self._console_visible
        if self._console_visible:
            self.consolePanel.show()
            self.tabWidget.setGeometry(10, 240, 821, 251)
        else:
            self.consolePanel.hide()
            self.tabWidget.setGeometry(10, 35, 821, 456)

    def _poll_logs(self):
        try:
            with FAPI.bridge._console_logs_lock:
                logs = list(FAPI.bridge._console_logs)
                FAPI.bridge._console_logs.clear()
            for log in logs:
                self._log_count += 1
                if self._console_visible:
                    self._display_log(log.get('message', ''), log.get('tag', 'output'), log.get('timestamp'))
                    self.logCountLabel.setText(f"{self._log_count} log{'s' if self._log_count != 1 else ''}")
        except Exception:
            pass

    def _display_log(self, message, log_type, timestamp=None):
        if timestamp:
            try:
                ts = float(timestamp)
                if ts > 1e12:
                    ts = ts / 1000
                time_text = __import__('datetime').datetime.fromtimestamp(ts).strftime("%H:%M:%S")
            except Exception:
                time_text = __import__('datetime').datetime.now().strftime("%H:%M:%S")
        else:
            time_text = __import__('datetime').datetime.now().strftime("%H:%M:%S")

        typ = self._normalize_type(log_type)

        color = "#8fa1b5"
        if typ == "WARN":
            color = "#e8c56b"
        elif typ == "ERROR":
            color = "#f07878"

        self.consoleText.append(
            f'<span style="color:#59616c;">[{time_text}]</span> '
            f'<span style="color:{color};">{typ:&lt;8}</span> '
            f'<span style="color:#d7dce2;">{message}</span>'
        )
        self.consoleText.moveCursor(QTextCursor.MoveOperation.End)

    def _save_tabs(self):
        data = [self._tab_number]
        for i in range(self.tabWidget.count()):
            data.append([self.tabWidget.tabText(i), self.tabWidget.widget(i).toPlainText()])
        with open(appdata + '\\tabs.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(data))

    def _clear_tabs(self):
        if MessageBox.question(
            'FunnyExecutor',
            'Are you sure you want to clear all of your tabs? This action is irreversible',
            MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
        ) == MessageBox.StandardButton.Yes:
            self.tabWidget.clear()
            self._tab_number = 1
            self._add_tab("Script #1")

    def _add_tab(self, name=None, content=None):
        editor = CodeEditor()
        if content is not None:
            editor.setPlainText(content)
        if name is None:
            self._tab_number += 1
            name = f'Script #{self._tab_number}'
        return self.tabWidget.addTab(editor, name)

    def _load_tabs(self):
        if os.path.exists(appdata + '\\tabs.json'):
            with open(appdata + '\\tabs.json', 'r', encoding='utf-8') as f:
                data = json.loads(f.read())
                self._tab_number = data.pop(0)
                for i in data:
                    self._add_tab(i[0], i[1])
        else:
            self._add_tab()

    def closeEvent(self, event):
        answer = MessageBox.question(
            "Quit", "Are you sure you want to quit?",
            MessageBox.StandardButton.Yes | MessageBox.StandardButton.No
        )
        if answer == MessageBox.StandardButton.Yes:
            self._save_tabs()
            event.accept()
        else:
            event.ignore()

    def _get_current_editor(self):
        return self.tabWidget.currentWidget()


appdata = os.environ['APPDATA'] + '\\FunnyExecutor'

if __name__ == '__main__':
    if not os.path.exists(appdata):
        os.mkdir(appdata)

    if os.path.exists('tabs.json'):
        shutil.copy('tabs.json', appdata + '\\tabs.json')
        os.remove('tabs.json')

    sys.argv += ['-platform', 'windows:darkmode=2']
    app = QApplication(sys.argv)
    app.styleHints().colorScheme = Qt.ColorScheme.Dark

    window = Window()
    window.show()
    sys.exit(app.exec())
