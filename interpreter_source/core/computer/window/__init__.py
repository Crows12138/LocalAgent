"""
Cross-platform Window Control Module

Automatically selects the correct implementation based on the OS:
- Linux: Uses wmctrl, xdotool, scrot (X11)
- Windows: Uses pywin32, pyautogui
- macOS: Uses AppleScript, screencapture, Quartz

Usage:
    from interpreter_source.core.computer.window import Window, WindowInfo

    window = Window(computer)
    windows = window.list()
    text = window.get_text("Chrome")
"""

import sys

from .base import WindowInfo, WindowBase

# Auto-select platform implementation
if sys.platform == "linux":
    from .window_linux import WindowLinux as Window
elif sys.platform == "darwin":
    from .window_mac import WindowMac as Window
elif sys.platform == "win32":
    from .window_win import WindowWindows as Window
else:
    # Fallback - try Linux implementation
    from .window_linux import WindowLinux as Window

__all__ = ["Window", "WindowInfo", "WindowBase"]
