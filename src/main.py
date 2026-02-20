import ctypes
import sys, subprocess, tempfile, os, json
import keyboard
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *


ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EvilClicker.App")

# ===== CONFIG PATH IN APPDATA =====
CONFIG_DIR = Path(os.getenv("APPDATA")) / "EvilClicker"
CONFIG_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# ===== Embedded AHK Script =====
AHK_SCRIPT = r"""
#SingleInstance Force
SetBatchLines, -1

#If WinActive("Roblox")
~LButton::
while GetKeyState("LButton","P")
{
    Click
    Sleep, 10
}
return
#If
"""

ahk_process = None
ahk_path = None

# ===== Write AHK Script =====
def write_ahk_temp():
    global ahk_path
    temp_dir = tempfile.gettempdir()
    ahk_path = os.path.join(temp_dir, "embedded_clicker.ahk")
    with open(ahk_path, "w") as f:
        f.write(AHK_SCRIPT)

# ===== Get Absolute Path to File =====
def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return filename

# ===== Hotkey Listener Thread =====
class GlobalHotkeyThread(QThread):
    toggled = Signal()

    def __init__(self):
        super().__init__()
        self.current_hotkey = None

    def set_hotkey(self, key):
        self.remove_hotkey()
        if key:
            try:
                self.current_hotkey = key
                keyboard.add_hotkey(self.current_hotkey, self.toggled.emit)
            except Exception as e:
                print(f"Error binding key: {e}")

    def remove_hotkey(self):
        if self.current_hotkey:
            try:
                keyboard.remove_hotkey(self.current_hotkey)
            except:
                pass
            self.current_hotkey = None


# ===== Power Button with SVG =====
class PowerButton(QPushButton):
    def __init__(self, size=80):
        super().__init__()
        self.setCheckable(True)
        self.base_size = size
        self.setFixedSize(size, size)
        self.radius = size // 2
        self.on_state = False
        self.update_style(False)

        # Pulse animation
        self.anim = QPropertyAnimation(self, b"minimumSize")
        self.anim.setDuration(120)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

    def pulse(self):
        # Slight grow then shrink
        grow = QSize(self.base_size + 6, self.base_size + 6)
        normal = QSize(self.base_size, self.base_size)

        self.anim.stop()
        self.anim.setStartValue(normal)
        self.anim.setKeyValueAt(0.5, grow)
        self.anim.setEndValue(normal)
        self.anim.start()

    def update_style(self, on):
        self.on_state = on
        bg_color = "#00ff88" if on else "#1e1f22"
        border = "3px solid #198250" if on else "3px solid #3f4147"

        self.setStyleSheet(f"""
            QPushButton {{
                border-radius: {self.radius}px;
                background-color: {bg_color};
                border: {border};
            }}
        """)
        self.update()  # Trigger repaint

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        icon_color = QColor("#2B2D33") if self.on_state else QColor("#00ff88")
        pen = QPen(icon_color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        painter.translate(self.width() / 2, self.height() / 2)
        scale = self.width() / 48
        painter.scale(scale, scale)

        painter.drawLine(0, -10, 0, -2)

        rect = QRectF(-9, -9, 18, 18)
        start_angle = 120 * 16
        span_angle = 300 * 16
        painter.drawArc(rect, start_angle, span_angle)

# ===== Toggle Keybind Button =====
class HotkeyButton(QPushButton):
    key_changed = Signal(str)

    def __init__(self):
        super().__init__("SET TOGGLE KEY")
        self.listening = False
        self.current_key = None
        self.setFixedHeight(30)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def update_display(self):
        if self.listening:
            self.setText("PRESS ANY KEY...")
            self.setStyleSheet("background:#00ff88;color:#1e1f22;border-radius:4px;font-weight:bold;")
        elif self.current_key:
            self.setText(f"BIND: {self.current_key.upper()}")
            self.setStyleSheet("background:#35373c;color:#00ff88;border-radius:4px;")
        else:
            self.setText("SET TOGGLE KEY")
            self.setStyleSheet("background:#35373c;color:#b5bac1;border-radius:4px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.current_key = None
            self.listening = False
            self.releaseKeyboard()
            self.key_changed.emit("")
            self.update_display()
        else:
            self.listening = True
            self.update_display()
            self.grabKeyboard()

    def keyPressEvent(self, event):
        if not self.listening:
            return
        if event.key() in [Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta]:
            return
        if event.key() == Qt.Key_Escape:
            self.listening = False
            self.releaseKeyboard()
            self.update_display()
            return
        key_text = QKeySequence(event.key()).toString().lower()
        self.current_key = key_text
        self.listening = False
        self.releaseKeyboard()
        self.update_display()
        self.key_changed.emit(self.current_key)


# ===== Main Window =====
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowOpacity(0.85)
        self.setFixedSize(200, 280)

        self.main_container = QFrame(self)
        self.main_container.setGeometry(10, 10, 180, 260)
        self.main_container.setStyleSheet("QFrame { background: #2b2d31; border-radius: 15px; }")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(0)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.main_container.setGraphicsEffect(shadow)

        self.hotkey_thread = GlobalHotkeyThread()
        self.hotkey_thread.toggled.connect(self.external_toggle)

        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(15, 10, 15, 15)

        top = QHBoxLayout()
        title = QLabel("Evil Clicker")
        title.setStyleSheet("color:#949ba4;font-weight:bold; border:none; background:transparent;")
        exit_btn = QPushButton("✕")
        exit_btn.setFixedSize(20, 20)
        exit_btn.setStyleSheet("background:transparent;color:#949ba4;border:none;")
        exit_btn.clicked.connect(self.close)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(exit_btn)
        layout.addLayout(top)

        layout.addStretch()

        self.power = PowerButton()
        self.status = QLabel("OFF")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("color:white;font-size:20px;font-weight:bold; border:none; background:transparent;")

        self.hotkey_btn = HotkeyButton()
        self.hotkey_btn.key_changed.connect(self.save_settings)

        layout.addWidget(self.power, alignment=Qt.AlignCenter)
        layout.addWidget(self.status)
        layout.addStretch()
        layout.addWidget(self.hotkey_btn)

        self.power.clicked.connect(self.toggle_clicker)
        self.drag_pos = None
        self.load_settings()

    def load_settings(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    key = data.get("hotkey")
                    if key:
                        self.hotkey_btn.current_key = key
                        self.hotkey_thread.set_hotkey(key)
            except:
                pass
        self.hotkey_btn.update_display()

    def save_settings(self, key):
        self.hotkey_thread.set_hotkey(key)
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"hotkey": key}, f)
        except:
            pass

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self.drag_pos:
            delta = e.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = e.globalPosition().toPoint()

    def external_toggle(self):
        self.power.setChecked(not self.power.isChecked())
        self.toggle_clicker()

    def toggle_clicker(self):
        global ahk_process
        is_on = self.power.isChecked()
        self.power.update_style(is_on)
        self.power.pulse()
        self.status.setText("ON" if is_on else "OFF")

        if is_on:
            write_ahk_temp()
            try:
                ahk_process = subprocess.Popen(["AutoHotkey.exe", ahk_path])
            except:
                self.power.setChecked(False)
                self.power.update_style(False)
        else:
            if ahk_process:
                ahk_process.terminate()
                ahk_process = None

    def closeEvent(self, event):
        global ahk_process
        if ahk_process:
            try:
                ahk_process.terminate()
                ahk_process.wait(1)
            except:
                pass
            ahk_process = None
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("../icon.ico")))
    w = App()
    w.show()
    sys.exit(app.exec())