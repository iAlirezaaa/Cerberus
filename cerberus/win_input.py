"""Windows-only input adapters for the summon shortcuts.

* ``MouseGestureHook`` installs a low-level mouse hook. It inspects only the
  button-press type of each event (never the cursor position) and swallows the
  presses that form the chosen gesture, so e.g. the right-click of a left+right
  chord never reaches the application underneath.
* ``GlobalHotkey`` uses RegisterHotKey, which does not observe any other keys.

On other platforms, or if Windows refuses the hook, ``start``/``register``
return False and the caller falls back to polling or tray-only summoning.
"""
from __future__ import annotations

import sys
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QWidget

from .shortcuts import MOD_NOREPEAT, GestureFilter, parse_hotkey

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                    ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallNextHookEx.restype = LRESULT
    user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.UnregisterHotKey.restype = wintypes.BOOL
    kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    WH_MOUSE_LL = 14
    WM_HOTKEY = 0x0312
    _EVENTS = {0x0201: "L_DOWN", 0x0202: "L_UP", 0x0204: "R_DOWN", 0x0205: "R_UP",
               0x0207: "M_DOWN", 0x0208: "M_UP"}


def read_buttons() -> tuple[bool, bool]:
    """Polling fallback: are the left / right buttons held right now?"""
    if not IS_WINDOWS:
        return False, False
    return (bool(user32.GetAsyncKeyState(0x01) & 0x8000),
            bool(user32.GetAsyncKeyState(0x02) & 0x8000))


class MouseGestureHook(QObject):
    triggered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._hook = None
        self._proc = None
        self.filter = GestureFilter()

    @property
    def active(self) -> bool:
        return self._hook is not None

    def start(self, mode: str) -> bool:
        self.stop()
        if not IS_WINDOWS or mode == "off":
            return False
        self.filter = GestureFilter(mode=mode)
        self._proc = HOOKPROC(self._callback)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc,
                                              kernel32.GetModuleHandleW(None), 0) or None
        if self._hook is None:
            self._proc = None
        return self._hook is not None

    def stop(self) -> None:
        if self._hook is not None:
            user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
        self._proc = None

    def _callback(self, code, wparam, lparam):
        try:
            if code >= 0:
                event = _EVENTS.get(wparam)
                if event is None and wparam in (0x020B, 0x020C):
                    info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    button = "X1" if (info.mouseData >> 16) & 0xFFFF == 1 else "X2"
                    event = f"{button}_{'DOWN' if wparam == 0x020B else 'UP'}"
                if event is not None:
                    ctrl = event == "M_DOWN" and bool(user32.GetAsyncKeyState(0x11) & 0x8000)
                    swallow, fired = self.filter.handle(event, time.monotonic(), ctrl=ctrl)
                    if fired:
                        # Never do real work inside the hook: Windows drops slow hooks.
                        QTimer.singleShot(0, self.triggered.emit)
                    if swallow:
                        return 1
        except Exception:  # A broken hook must never block the user's mouse.
            pass
        return user32.CallNextHookEx(self._hook, code, wparam, lparam)


class GlobalHotkey(QWidget):
    """Hidden native window that receives WM_HOTKEY for one registered shortcut."""

    triggered = Signal()
    HOTKEY_ID = 0xCE7B

    def __init__(self) -> None:
        super().__init__()
        self._registered = False
        self.setWindowTitle("Cerberus hotkey")

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self, text: str) -> bool:
        self.unregister()
        parsed = parse_hotkey(text)
        if not IS_WINDOWS or parsed is None:
            return False
        flags, vk = parsed
        self._registered = bool(user32.RegisterHotKey(int(self.winId()), self.HOTKEY_ID,
                                                      flags | MOD_NOREPEAT, vk))
        return self._registered

    def unregister(self) -> None:
        if self._registered and IS_WINDOWS:
            user32.UnregisterHotKey(int(self.winId()), self.HOTKEY_ID)
        self._registered = False

    def nativeEvent(self, event_type, message):
        if IS_WINDOWS and self._registered:
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
                    QTimer.singleShot(0, self.triggered.emit)
                    return True, 0
            except (ValueError, TypeError, OverflowError):
                pass
        return super().nativeEvent(event_type, message)
