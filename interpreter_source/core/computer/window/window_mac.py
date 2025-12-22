"""
macOS Window Control Module
Uses AppleScript and Quartz for window management
"""

import subprocess
import re
import tempfile
import json
from typing import List, Optional

from .base import WindowBase, WindowInfo

try:
    from PIL import Image
except ImportError:
    Image = None

# macOS-specific imports
try:
    import Quartz
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowOwnerPID,
        kCGWindowNumber,
        kCGWindowName,
        kCGWindowOwnerName,
        kCGWindowBounds
    )
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False


class WindowMac(WindowBase):
    """macOS Window Control using AppleScript and Quartz"""

    def __init__(self, computer):
        super().__init__(computer)

    def _run_applescript(self, script: str) -> str:
        """Run AppleScript and return output"""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _run_jxa(self, script: str) -> str:
        """Run JavaScript for Automation (JXA) and return output"""
        try:
            result = subprocess.run(
                ["osascript", "-l", "JavaScript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def list(self) -> List[WindowInfo]:
        """List all open windows"""
        windows = []

        if HAS_QUARTZ:
            # Use Quartz (more reliable)
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly,
                kCGNullWindowID
            )

            for window in window_list:
                # Skip windows without names or with empty names
                title = window.get(kCGWindowName, "")
                owner = window.get(kCGWindowOwnerName, "")

                if title or owner:
                    windows.append(WindowInfo(
                        id=str(window.get(kCGWindowNumber, 0)),
                        pid=window.get(kCGWindowOwnerPID, 0),
                        title=title if title else owner,
                        app_name=owner
                    ))
        else:
            # Fallback to AppleScript
            script = '''
            tell application "System Events"
                set windowList to {}
                repeat with proc in (every process whose background only is false)
                    set procName to name of proc
                    set procPID to unix id of proc
                    try
                        repeat with win in (every window of proc)
                            set winName to name of win
                            set end of windowList to procPID & "|" & procName & "|" & winName
                        end repeat
                    end try
                end repeat
                return windowList
            end tell
            '''
            output = self._run_applescript(script)

            for line in output.split(", "):
                parts = line.split("|")
                if len(parts) >= 3:
                    windows.append(WindowInfo(
                        id=parts[0],
                        pid=int(parts[0]) if parts[0].isdigit() else 0,
                        title=parts[2],
                        app_name=parts[1]
                    ))

        return windows

    def find(self, pattern: str) -> List[WindowInfo]:
        """Find windows matching a pattern"""
        windows = self.list()
        matched = []

        try:
            regex = re.compile(pattern, re.IGNORECASE)
            for w in windows:
                if regex.search(w.title) or regex.search(w.app_name):
                    matched.append(w)
        except re.error:
            pattern_lower = pattern.lower()
            for w in windows:
                if pattern_lower in w.title.lower() or pattern_lower in w.app_name.lower():
                    matched.append(w)

        return matched

    def get_active(self) -> Optional[WindowInfo]:
        """Get the currently active window"""
        script = '''
        tell application "System Events"
            set frontApp to first application process whose frontmost is true
            set appName to name of frontApp
            set appPID to unix id of frontApp
            try
                set winName to name of front window of frontApp
            on error
                set winName to appName
            end try
            return appPID & "|" & appName & "|" & winName
        end tell
        '''
        output = self._run_applescript(script)
        parts = output.split("|")

        if len(parts) >= 3:
            return WindowInfo(
                id=parts[0],
                pid=int(parts[0]) if parts[0].isdigit() else 0,
                title=parts[2],
                app_name=parts[1]
            )
        return None

    def _get_window_bounds(self, window: str) -> Optional[tuple]:
        """Get window bounds (x, y, width, height)"""
        if HAS_QUARTZ:
            matches = self.find(window)
            if matches:
                window_id = int(matches[0].id)
                window_list = CGWindowListCopyWindowInfo(
                    kCGWindowListOptionOnScreenOnly,
                    kCGNullWindowID
                )
                for win in window_list:
                    if win.get(kCGWindowNumber) == window_id:
                        bounds = win.get(kCGWindowBounds, {})
                        return (
                            int(bounds.get('X', 0)),
                            int(bounds.get('Y', 0)),
                            int(bounds.get('Width', 0)),
                            int(bounds.get('Height', 0))
                        )

        # Fallback to AppleScript
        matches = self.find(window)
        if matches:
            app_name = matches[0].app_name or matches[0].title
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    set winBounds to position of front window & size of front window
                    return winBounds
                end tell
            end tell
            '''
            output = self._run_applescript(script)
            parts = output.replace("{", "").replace("}", "").split(", ")
            if len(parts) >= 4:
                return tuple(int(p) for p in parts)

        return None

    def capture(self, window: str = None, save_path: str = None) -> "Image":
        """Capture a window screenshot"""
        if Image is None:
            raise RuntimeError("Pillow not installed")

        import os

        # Create save path if needed
        if save_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            save_path = temp_file.name
            temp_file.close()
            os.unlink(save_path)

        if window is None:
            # Capture active window
            subprocess.run(
                ["screencapture", "-w", save_path],
                capture_output=True,
                timeout=10
            )
        else:
            # Find window and capture by bounds
            matches = self.find(window)
            if not matches:
                raise ValueError(f"No window found matching: {window}")

            # Try to capture specific window by ID
            window_id = matches[0].id
            result = subprocess.run(
                ["screencapture", "-l", window_id, save_path],
                capture_output=True,
                timeout=10
            )

            # If that fails, try by bounds
            if result.returncode != 0 or not os.path.exists(save_path):
                bounds = self._get_window_bounds(window)
                if bounds:
                    x, y, w, h = bounds
                    subprocess.run(
                        ["screencapture", "-R", f"{x},{y},{w},{h}", save_path],
                        capture_output=True,
                        timeout=10
                    )

        if not os.path.exists(save_path):
            raise RuntimeError("Screenshot failed")

        return Image.open(save_path)

    def focus(self, window: str) -> bool:
        """Focus/activate a window"""
        matches = self.find(window)
        if not matches:
            return False

        app_name = matches[0].app_name or matches[0].title
        script = f'''
        tell application "{app_name}"
            activate
        end tell
        '''
        self._run_applescript(script)
        return True

    def close(self, window: str) -> bool:
        """Close a window"""
        matches = self.find(window)
        if not matches:
            return False

        app_name = matches[0].app_name or matches[0].title
        win_title = matches[0].title

        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                try
                    click button 1 of (first window whose name is "{win_title}")
                on error
                    keystroke "w" using command down
                end try
            end tell
        end tell
        '''
        self._run_applescript(script)
        return True

    def move(self, window: str, x: int, y: int, width: int = None, height: int = None) -> bool:
        """Move and optionally resize a window"""
        matches = self.find(window)
        if not matches:
            return False

        app_name = matches[0].app_name or matches[0].title

        if width is not None and height is not None:
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    set position of front window to {{{x}, {y}}}
                    set size of front window to {{{width}, {height}}}
                end tell
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                tell process "{app_name}"
                    set position of front window to {{{x}, {y}}}
                end tell
            end tell
            '''

        self._run_applescript(script)
        return True

    def minimize(self, window: str) -> bool:
        """Minimize a window"""
        matches = self.find(window)
        if not matches:
            return False

        app_name = matches[0].app_name or matches[0].title
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set miniaturized of front window to true
            end tell
        end tell
        '''
        self._run_applescript(script)
        return True

    def maximize(self, window: str) -> bool:
        """Maximize/fullscreen a window"""
        matches = self.find(window)
        if not matches:
            return False

        app_name = matches[0].app_name or matches[0].title
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set value of attribute "AXFullScreen" of front window to true
            end tell
        end tell
        '''
        self._run_applescript(script)
        return True


# Alias for compatibility
Window = WindowMac
