"""Settings window: where memories are stored, companion behaviour and shortcuts."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QKeySequenceEdit, QLabel, QMessageBox, QPushButton, QScrollArea, QSlider,
    QSpinBox, QVBoxLayout, QWidget,
)

from .settings import CHAT_LEVELS
from .shortcuts import MOUSE_GESTURES, SHORTCUT_ACTIONS, parse_hotkey
from .vault import CaptureError, Vault

STYLE = """
    QWidget { background: #100d11; color: #eee7df; font-size: 13px; }
    QLabel#title { color: #fff2df; font-size: 22px; font-weight: 700; }
    QLabel#muted, QLabel#hint { color: #a99b98; }
    QLabel#hint { font-size: 11px; }
    QLabel#path { background: #171319; border: 1px solid #49333a; border-radius: 7px;
                  padding: 7px 9px; color: #ffd5a2; font-family: Consolas, monospace; }
    QLabel#status { color: #ffc27c; font-size: 11px; }
    QGroupBox { border: 1px solid #3a2930; border-radius: 12px; margin-top: 14px;
                padding: 14px 12px 10px 12px; background: #19151b; font-weight: 700; }
    QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; color: #f08a55; }
    QPushButton { background: #592d2a; border: 1px solid #a34e38; border-radius: 8px; padding: 7px 12px; }
    QPushButton:hover { background: #793d30; }
    QPushButton#secondary { background: #211a22; border-color: #4b3741; }
    QPushButton#secondary:hover { background: #33232b; }
    QComboBox, QSpinBox, QKeySequenceEdit { background: #171319; border: 1px solid #49333a;
                border-radius: 7px; padding: 5px 8px; min-height: 22px; }
    QCheckBox::indicator { width: 16px; height: 16px; }
    QScrollArea { border: none; }
"""

CHAT_LABELS = {"off": "Silent", "quiet": "Quiet", "normal": "Normal", "chatty": "Chatty"}
LANGUAGE_LABELS = {"auto": "Automatic (system)", "en": "English", "fa": "فارسی (Persian)"}


def _folder_size(folder: Path) -> int:
    total = 0
    try:
        for path in folder.rglob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
    except OSError:
        pass
    return total


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


class SettingsWindow(QWidget):
    """Edits apply immediately; the controller persists them to settings.json."""

    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Cerberus — Settings")
        self.resize(640, 760)
        self.setMinimumSize(540, 480)
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(6)
        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Changes apply right away and are saved on this computer only.")
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)

        # --- storage ------------------------------------------------------
        storage = QGroupBox("Storage — where your memories go")
        s = QVBoxLayout(storage)
        s.addWidget(QLabel("Memories (database and copied files) are saved in:"))
        self.storage_path = QLabel()
        self.storage_path.setObjectName("path")
        self.storage_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.storage_path.setWordWrap(True)
        s.addWidget(self.storage_path)
        self.storage_details = QLabel()
        self.storage_details.setObjectName("hint")
        self.storage_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.storage_details.setWordWrap(True)
        s.addWidget(self.storage_details)
        row = QHBoxLayout()
        for label, callback, name in (("Open folder", self.open_storage, "secondary"),
                                      ("Change location…", self.change_storage, ""),
                                      ("Use default location", self.reset_storage, "secondary")):
            button = QPushButton(label)
            button.setObjectName(name)
            button.clicked.connect(callback)
            row.addWidget(button)
        row.addStretch(1)
        s.addLayout(row)
        layout.addWidget(storage)

        # --- companion ----------------------------------------------------
        companion = QGroupBox("Companion")
        c = QFormLayout(companion)
        size_row = QHBoxLayout()
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(180, 500)
        self.size_slider.setSingleStep(10)
        self.size_value = QLabel()
        self.size_slider.valueChanged.connect(lambda v: self.size_value.setText(f"{v}px"))
        self.size_slider.sliderReleased.connect(
            lambda: controller.set_pet_size(self.size_slider.value()))
        size_row.addWidget(self.size_slider, 1)
        size_row.addWidget(self.size_value)
        c.addRow("Size", size_row)
        self.roam = QCheckBox("Walk around the screen and turn toward the cursor")
        self.roam.toggled.connect(controller.set_roam)
        c.addRow("", self.roam)
        self.reduced = QCheckBox("Reduced motion (still poses, no particles)")
        self.reduced.toggled.connect(controller.set_reduced_motion)
        c.addRow("", self.reduced)
        self.chat = QComboBox()
        for level in CHAT_LEVELS:
            self.chat.addItem(CHAT_LABELS[level], level)
        self.chat.currentIndexChanged.connect(
            lambda: controller.set_chat_level(self.chat.currentData()))
        c.addRow("Talking & thinking", self.chat)
        self.language = QComboBox()
        for code, label in LANGUAGE_LABELS.items():
            self.language.addItem(label, code)
        self.language.currentIndexChanged.connect(
            lambda: controller.set_language(self.language.currentData()))
        c.addRow("Speech language", self.language)
        layout.addWidget(companion)

        # --- away ---------------------------------------------------------
        away = QGroupBox("Naps and wandering off")
        a = QFormLayout(away)
        self.standby = QSpinBox()
        self.standby.setRange(15, 3600)
        self.standby.setSuffix(" s")
        self.standby.editingFinished.connect(
            lambda: controller.set_standby_seconds(self.standby.value()))
        a.addRow("Nap after", self.standby)
        wander_row = QHBoxLayout()
        self.wander = QCheckBox("Run off the screen after")
        self.wander.toggled.connect(controller.set_wander_off)
        self.away_minutes = QSpinBox()
        self.away_minutes.setRange(1, 120)
        self.away_minutes.setSuffix(" min unused")
        self.away_minutes.editingFinished.connect(
            lambda: controller.set_away_minutes(self.away_minutes.value()))
        wander_row.addWidget(self.wander)
        wander_row.addWidget(self.away_minutes)
        wander_row.addStretch(1)
        a.addRow("", wander_row)
        self.return_button = QCheckBox("Show a small portal button at the screen edge while away")
        self.return_button.toggled.connect(controller.set_return_button)
        a.addRow("", self.return_button)
        hint = QLabel("Hover over Cerberus and click the ↗ button to send it away yourself.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        a.addRow("", hint)
        layout.addWidget(away)

        # --- shortcuts ----------------------------------------------------
        shortcuts = QGroupBox("Shortcuts to call Cerberus")
        k = QFormLayout(shortcuts)
        self.gesture = QComboBox()
        for code, label in MOUSE_GESTURES.items():
            self.gesture.addItem(label, code)
        self.gesture.currentIndexChanged.connect(
            lambda: controller.set_mouse_gesture(self.gesture.currentData()))
        k.addRow("Mouse gesture", self.gesture)
        key_row = QHBoxLayout()
        self.hotkey = QKeySequenceEdit()
        if hasattr(self.hotkey, "setMaximumSequenceLength"):
            self.hotkey.setMaximumSequenceLength(1)
        self.hotkey.editingFinished.connect(self.hotkey_changed)
        clear = QPushButton("Clear")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear_hotkey)
        key_row.addWidget(self.hotkey, 1)
        key_row.addWidget(clear)
        k.addRow("Keyboard shortcut", key_row)
        self.action = QComboBox()
        for code, label in SHORTCUT_ACTIONS.items():
            self.action.addItem(label, code)
        self.action.currentIndexChanged.connect(
            lambda: controller.set_shortcut_action(self.action.currentData()))
        k.addRow("Shortcut does", self.action)
        self.shortcut_status = QLabel()
        self.shortcut_status.setObjectName("status")
        self.shortcut_status.setWordWrap(True)
        k.addRow("", self.shortcut_status)
        note = QLabel("The gesture's clicks are swallowed, so the app under the cursor never "
                      "sees them (no right-click menu). Only button presses are checked — "
                      "never cursor movement or typing.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        k.addRow("", note)
        layout.addWidget(shortcuts)

        # --- capture ------------------------------------------------------
        capture = QGroupBox("Capture")
        p = QVBoxLayout(capture)
        self.clipboard = QCheckBox("Auto-capture newly copied clipboard items")
        self.clipboard.toggled.connect(controller.set_clipboard)
        p.addWidget(self.clipboard)
        warn = QLabel("When on, anything you copy (including passwords) is saved. Off by default.")
        warn.setObjectName("hint")
        warn.setWordWrap(True)
        p.addWidget(warn)
        layout.addWidget(capture)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        done = QPushButton("Done")
        done.clicked.connect(self.close)
        bottom.addWidget(done)
        layout.addLayout(bottom)
        layout.addStretch(1)
        self.refresh()

    # ----- sync ----------------------------------------------------------
    def refresh(self) -> None:
        settings = self.controller.settings
        widgets = (self.size_slider, self.roam, self.reduced, self.chat, self.language,
                   self.standby, self.wander, self.away_minutes, self.return_button,
                   self.gesture, self.hotkey, self.action, self.clipboard)
        for widget in widgets:
            widget.blockSignals(True)
        self.size_slider.setValue(settings.pet_size)
        self.size_value.setText(f"{settings.pet_size}px")
        self.roam.setChecked(settings.roam)
        self.reduced.setChecked(settings.reduced_motion)
        self.chat.setCurrentIndex(max(0, self.chat.findData(settings.chat_level)))
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        self.standby.setValue(settings.standby_seconds)
        self.wander.setChecked(settings.wander_off)
        self.away_minutes.setValue(max(1, round(settings.away_seconds / 60)))
        self.return_button.setChecked(settings.show_return_button)
        self.gesture.setCurrentIndex(max(0, self.gesture.findData(settings.mouse_gesture)))
        self.hotkey.setKeySequence(QKeySequence(settings.hotkey))
        self.action.setCurrentIndex(max(0, self.action.findData(settings.shortcut_action)))
        self.clipboard.setChecked(settings.clipboard_capture)
        for widget in widgets:
            widget.blockSignals(False)
        self.refresh_storage()
        self.shortcut_status.setText(self.controller.shortcut_status())

    def refresh_storage(self) -> None:
        vault = self.controller.vault
        home = vault.home.resolve()
        self.storage_path.setText(str(home))
        total = vault.stats()["total"]
        default = home == self.controller.home.resolve()
        self.storage_details.setText(
            f"Database: {home / 'vault.sqlite3'}\n"
            f"Copied files: {vault.files_dir.resolve()}\n"
            f"Settings file: {self.controller.home.resolve() / 'settings.json'}\n"
            f"{total} memories · {_human(_folder_size(home))} on disk"
            + ("  ·  default location" if default else "  ·  custom location"))

    # ----- storage actions -------------------------------------------------
    def open_storage(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.controller.vault.home)))

    def change_storage(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choose where Cerberus keeps your memories", str(self.controller.vault.home))
        if folder:
            self._switch_storage(Path(folder))

    def reset_storage(self) -> None:
        self._switch_storage(self.controller.home)

    def _switch_storage(self, folder: Path) -> None:
        folder = folder.resolve()
        if folder == self.controller.vault.home.resolve():
            return
        copy = False
        if Vault.has_vault(folder):
            answer = QMessageBox.question(
                self, "Use existing vault?",
                f"{folder}\nalready contains a Cerberus vault.\n\nSwitch to the memories stored there?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        elif self.controller.vault.stats()["total"]:
            answer = QMessageBox.question(
                self, "Copy your memories?",
                "Copy your current memories into the new folder?\n\n"
                "The originals stay in the old folder; delete them yourself once you're happy.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                return
            copy = answer == QMessageBox.StandardButton.Yes
        try:
            self.controller.change_storage(folder, copy_existing=copy)
        except (CaptureError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "Couldn't change storage", str(exc))
            return
        self.refresh_storage()

    # ----- shortcut actions ----------------------------------------------
    def hotkey_changed(self) -> None:
        text = self.hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        text = text.split(",")[0].strip()
        if text and parse_hotkey(text) is None:
            self.shortcut_status.setText(
                "That key needs a modifier: use Ctrl, Alt, Shift or Win (or an F-key).")
            self.hotkey.setKeySequence(QKeySequence(self.controller.settings.hotkey))
            return
        self.controller.set_hotkey(text)
        self.shortcut_status.setText(self.controller.shortcut_status())

    def clear_hotkey(self) -> None:
        self.hotkey.clear()
        self.controller.set_hotkey("")
        self.shortcut_status.setText(self.controller.shortcut_status())

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)
