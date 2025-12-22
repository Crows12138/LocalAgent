"""
Windows Window Control Module
Uses pywin32 and pyautogui for window management
"""

import re
import tempfile
from typing import List, Optional

from .base import WindowBase, WindowInfo

try:
    from PIL import Image
except ImportError:
    Image = None

# Windows-specific imports
try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


class WindowWindows(WindowBase):
    """Windows Window Control using Win32 API"""

    def __init__(self, computer):
        super().__init__(computer)
        if not HAS_WIN32:
            raise RuntimeError(
                "pywin32 not installed. Run: pip install pywin32"
            )

    def list(self) -> List[WindowInfo]:
        """List all open windows"""
        windows = []

        def enum_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only windows with titles
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    except:
                        pid = 0
                    windows.append(WindowInfo(
                        id=str(hwnd),
                        pid=pid,
                        title=title,
                        app_name=""
                    ))
            return True

        win32gui.EnumWindows(enum_callback, None)
        return windows

    def find(self, pattern: str) -> List[WindowInfo]:
        """Find windows matching a pattern"""
        windows = self.list()
        matched = []

        try:
            regex = re.compile(pattern, re.IGNORECASE)
            for w in windows:
                if regex.search(w.title):
                    matched.append(w)
        except re.error:
            pattern_lower = pattern.lower()
            for w in windows:
                if pattern_lower in w.title.lower():
                    matched.append(w)

        return matched

    def get_active(self) -> Optional[WindowInfo]:
        """Get the currently active window"""
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None

        title = win32gui.GetWindowText(hwnd)
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except:
            pid = 0

        return WindowInfo(
            id=str(hwnd),
            pid=pid,
            title=title,
            app_name=""
        )

    def _get_window_handle(self, window: str) -> int:
        """Get window handle from title pattern or handle string"""
        if window.isdigit():
            return int(window)

        matches = self.find(window)
        if not matches:
            raise ValueError(f"No window found matching: {window}")
        return int(matches[0].id)

    def _get_window_rect(self, hwnd: int) -> tuple:
        """Get window rectangle (left, top, right, bottom)"""
        return win32gui.GetWindowRect(hwnd)

    def capture(self, window: str = None, save_path: str = None) -> "Image":
        """Capture a window screenshot"""
        if Image is None:
            raise RuntimeError("Pillow not installed")

        import os

        # Get window handle
        if window is None:
            hwnd = win32gui.GetForegroundWindow()
        else:
            hwnd = self._get_window_handle(window)

        # Get window position and size
        left, top, right, bottom = self._get_window_rect(hwnd)
        width = right - left
        height = bottom - top

        # Create save path if needed
        if save_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            save_path = temp_file.name
            temp_file.close()
            os.unlink(save_path)

        # Capture using pyautogui (cross-platform screenshot)
        if HAS_PYAUTOGUI:
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            screenshot.save(save_path)
        else:
            # Fallback: Use PIL's ImageGrab
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
                screenshot.save(save_path)
            except Exception as e:
                raise RuntimeError(f"Screenshot failed: {e}. Install pyautogui: pip install pyautogui")

        return Image.open(save_path)

    def focus(self, window: str) -> bool:
        """Focus/activate a window"""
        try:
            hwnd = self._get_window_handle(window)
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # Bring to foreground
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

    def close(self, window: str) -> bool:
        """Close a window"""
        try:
            hwnd = self._get_window_handle(window)
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return True
        except Exception:
            return False

    def move(self, window: str, x: int, y: int, width: int = None, height: int = None) -> bool:
        """Move and optionally resize a window"""
        try:
            hwnd = self._get_window_handle(window)

            if width is None or height is None:
                # Get current size
                left, top, right, bottom = self._get_window_rect(hwnd)
                if width is None:
                    width = right - left
                if height is None:
                    height = bottom - top

            win32gui.MoveWindow(hwnd, x, y, width, height, True)
            return True
        except Exception:
            return False

    def minimize(self, window: str) -> bool:
        """Minimize a window"""
        try:
            hwnd = self._get_window_handle(window)
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            return True
        except Exception:
            return False

    def maximize(self, window: str) -> bool:
        """Maximize a window"""
        try:
            hwnd = self._get_window_handle(window)
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            return True
        except Exception:
            return False


# Alias for compatibility
Window = WindowWindows
