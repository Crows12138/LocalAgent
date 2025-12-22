"""
Linux X11 Window Control Module
Uses wmctrl, xdotool, and scrot for window management
"""

import subprocess
import re
import tempfile
from typing import List, Optional

from .base import WindowBase, WindowInfo

try:
    from PIL import Image
except ImportError:
    Image = None


class WindowLinux(WindowBase):
    """X11 Window Control for Linux"""

    def __init__(self, computer):
        super().__init__(computer)
        self._check_tools()

    def _check_tools(self):
        """Check if required tools are installed"""
        self._has_wmctrl = self._command_exists("wmctrl")
        self._has_xdotool = self._command_exists("xdotool")
        self._has_scrot = self._command_exists("scrot")
        self._has_import = self._command_exists("import")  # ImageMagick

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists"""
        try:
            subprocess.run(["which", cmd], capture_output=True, check=True)
            return True
        except:
            return False

    def _run_command(self, cmd: List[str]) -> str:
        """Run a shell command and return output"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout.strip()
        except Exception:
            return ""

    def list(self) -> List[WindowInfo]:
        """List all open windows"""
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed. Run: sudo pacman -S wmctrl")

        output = self._run_command(["wmctrl", "-l", "-p"])
        windows = []

        for line in output.split("\n"):
            if not line.strip():
                continue

            parts = line.split(None, 4)
            if len(parts) >= 5:
                windows.append(WindowInfo(
                    id=parts[0],
                    pid=int(parts[2]),
                    title=parts[4],
                    app_name=""
                ))
            elif len(parts) == 4:
                windows.append(WindowInfo(
                    id=parts[0],
                    pid=int(parts[2]),
                    title="",
                    app_name=""
                ))

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
        if not self._has_xdotool:
            return None

        window_id = self._run_command(["xdotool", "getactivewindow"])
        if not window_id:
            return None

        try:
            hex_id = hex(int(window_id))
        except:
            return None

        for w in self.list():
            if w.id.lower() == hex_id.lower():
                return w

        return None

    def _get_window_geometry(self, window_id: str) -> Optional[tuple]:
        """Get window geometry (x, y, width, height)"""
        if not self._has_xdotool:
            return None

        output = self._run_command(["xdotool", "getwindowgeometry", "--shell", window_id])
        if not output:
            return None

        geometry = {}
        for line in output.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                geometry[key] = int(value)

        if all(k in geometry for k in ["X", "Y", "WIDTH", "HEIGHT"]):
            return (geometry["X"], geometry["Y"], geometry["WIDTH"], geometry["HEIGHT"])
        return None

    def capture(self, window: str = None, save_path: str = None) -> "Image":
        """Capture a window screenshot"""
        if Image is None:
            raise RuntimeError("Pillow not installed")

        import os

        # Determine window ID
        if window is None:
            if self._has_xdotool:
                window_id = self._run_command(["xdotool", "getactivewindow"])
            else:
                raise RuntimeError("xdotool not installed")
        elif window.startswith("0x"):
            window_id = str(int(window, 16))
        else:
            matches = self.find(window)
            if not matches:
                raise ValueError(f"No window found matching: {window}")
            window_id = str(int(matches[0].id, 16))

        # Create temp file path if no save path
        if save_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            save_path = temp_file.name
            temp_file.close()
            os.unlink(save_path)

        captured = False

        # Method 1: scrot with geometry
        if self._has_scrot and self._has_xdotool:
            geometry = self._get_window_geometry(window_id)
            if geometry:
                x, y, w, h = geometry
                result = subprocess.run(
                    ["scrot", "-a", f"{x},{y},{w},{h}", save_path],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    captured = True

        # Method 2: Focus-based capture
        if not captured and self._has_scrot and self._has_xdotool:
            import time
            self._run_command(["xdotool", "windowactivate", "--sync", window_id])
            time.sleep(0.3)
            result = subprocess.run(
                ["scrot", "-u", save_path],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                captured = True

        # Method 3: ImageMagick import
        if not captured and self._has_import:
            result = subprocess.run(
                ["import", "-window", window_id, save_path],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                captured = True

        if not captured:
            raise RuntimeError("Failed to capture window. Install scrot and xdotool")

        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            raise RuntimeError(f"Screenshot file is empty: {save_path}")

        return Image.open(save_path)

    def focus(self, window: str) -> bool:
        """Focus/activate a window"""
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        if window.startswith("0x"):
            result = subprocess.run(["wmctrl", "-i", "-a", window], capture_output=True)
        else:
            result = subprocess.run(["wmctrl", "-a", window], capture_output=True)

        return result.returncode == 0

    def close(self, window: str) -> bool:
        """Close a window"""
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        if window.startswith("0x"):
            result = subprocess.run(["wmctrl", "-i", "-c", window], capture_output=True)
        else:
            result = subprocess.run(["wmctrl", "-c", window], capture_output=True)

        return result.returncode == 0

    def move(self, window: str, x: int, y: int, width: int = None, height: int = None) -> bool:
        """Move and optionally resize a window"""
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        if width and height:
            geometry = f"0,{x},{y},{width},{height}"
        else:
            geometry = f"0,{x},{y},-1,-1"

        if window.startswith("0x"):
            result = subprocess.run(
                ["wmctrl", "-i", "-r", window, "-e", geometry],
                capture_output=True
            )
        else:
            result = subprocess.run(
                ["wmctrl", "-r", window, "-e", geometry],
                capture_output=True
            )

        return result.returncode == 0


# Alias for compatibility
Window = WindowLinux
