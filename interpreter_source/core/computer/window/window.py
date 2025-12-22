"""
X11 Window Control Module for Linux
Provides window listing, capturing, and OCR functionality
"""

import subprocess
import re
import tempfile
from typing import List, Dict, Optional
from dataclasses import dataclass

# Lazy imports
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

# PaddleOCR - best for Chinese+English mixed text
try:
    from paddleocr import PaddleOCR
    _paddleocr_instance = None  # Lazy initialization
except ImportError:
    PaddleOCR = None
    _paddleocr_instance = None


@dataclass
class WindowInfo:
    """Window information"""
    id: str           # Window ID (hex)
    desktop: int      # Desktop number (-1 = sticky)
    pid: int          # Process ID
    hostname: str     # Hostname
    title: str        # Window title

    def __str__(self):
        return f"[{self.id}] {self.title} (PID: {self.pid})"


class Window:
    """X11 Window Control for Linux"""

    def __init__(self, computer):
        self.computer = computer
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
        except Exception as e:
            return ""

    def list(self) -> List[WindowInfo]:
        """
        List all open windows

        Returns:
            List of WindowInfo objects
        """
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed. Run: sudo pacman -S wmctrl")

        output = self._run_command(["wmctrl", "-l", "-p"])
        windows = []

        for line in output.split("\n"):
            if not line.strip():
                continue

            # Parse wmctrl output: 0x01c00003  0 1792   hostname Title
            parts = line.split(None, 4)
            if len(parts) >= 5:
                windows.append(WindowInfo(
                    id=parts[0],
                    desktop=int(parts[1]),
                    pid=int(parts[2]),
                    hostname=parts[3],
                    title=parts[4]
                ))
            elif len(parts) == 4:
                windows.append(WindowInfo(
                    id=parts[0],
                    desktop=int(parts[1]),
                    pid=int(parts[2]),
                    hostname=parts[3],
                    title=""
                ))

        return windows

    def list_names(self) -> List[str]:
        """
        List all window titles (simple version)

        Returns:
            List of window titles
        """
        return [w.title for w in self.list() if w.title]

    def find(self, pattern: str) -> List[WindowInfo]:
        """
        Find windows matching a pattern

        Args:
            pattern: Regex pattern or substring to match window title

        Returns:
            List of matching WindowInfo objects
        """
        windows = self.list()
        matched = []

        try:
            regex = re.compile(pattern, re.IGNORECASE)
            for w in windows:
                if regex.search(w.title):
                    matched.append(w)
        except re.error:
            # Fallback to simple substring match
            pattern_lower = pattern.lower()
            for w in windows:
                if pattern_lower in w.title.lower():
                    matched.append(w)

        return matched

    def get_active(self) -> Optional[WindowInfo]:
        """
        Get the currently active window

        Returns:
            WindowInfo of active window, or None
        """
        if not self._has_xdotool:
            return None

        window_id = self._run_command(["xdotool", "getactivewindow"])
        if not window_id:
            return None

        # Convert decimal to hex
        try:
            hex_id = hex(int(window_id))
        except:
            return None

        for w in self.list():
            if w.id.lower() == hex_id.lower():
                return w

        return None

    def _get_window_geometry(self, window_id: str) -> Optional[tuple]:
        """
        Get window geometry (x, y, width, height) using xdotool

        Args:
            window_id: Window ID in decimal format

        Returns:
            Tuple of (x, y, width, height) or None if failed
        """
        if not self._has_xdotool:
            return None

        output = self._run_command(["xdotool", "getwindowgeometry", "--shell", window_id])
        if not output:
            return None

        # Parse xdotool --shell output:
        # WINDOW=12345
        # X=100
        # Y=200
        # WIDTH=800
        # HEIGHT=600
        # SCREEN=0
        geometry = {}
        for line in output.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                geometry[key] = int(value)

        if all(k in geometry for k in ["X", "Y", "WIDTH", "HEIGHT"]):
            return (geometry["X"], geometry["Y"], geometry["WIDTH"], geometry["HEIGHT"])
        return None

    def capture(self, window: str = None, save_path: str = None) -> "Image":
        """
        Capture a window screenshot

        Args:
            window: Window title pattern, window ID, or None for active window
            save_path: Optional path to save the screenshot

        Returns:
            PIL Image object
        """
        if Image is None:
            raise RuntimeError("Pillow not installed")

        # Determine window ID (xdotool uses decimal, wmctrl uses hex)
        if window is None:
            # Capture active window
            if self._has_xdotool:
                window_id = self._run_command(["xdotool", "getactivewindow"])
            else:
                raise RuntimeError("xdotool not installed for active window capture")
        elif window.startswith("0x"):
            # Convert hex to decimal for xdotool
            window_id = str(int(window, 16))
        else:
            # Search by title
            matches = self.find(window)
            if not matches:
                raise ValueError(f"No window found matching: {window}")
            # Convert hex to decimal for xdotool
            window_id = str(int(matches[0].id, 16))

        # Create temp file path if no save path
        import os
        if save_path is None:
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            save_path = temp_file.name
            temp_file.close()
            # Remove the empty file - scrot won't overwrite it
            os.unlink(save_path)

        captured = False

        # Method 1: Use scrot with window geometry (most reliable)
        if self._has_scrot and self._has_xdotool:
            geometry = self._get_window_geometry(window_id)
            if geometry:
                x, y, w, h = geometry
                # Use scrot with region capture (doesn't require focus)
                result = subprocess.run(
                    ["scrot", "-a", f"{x},{y},{w},{h}", save_path],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    captured = True

        # Method 2: Fallback to focus-based capture
        if not captured and self._has_scrot and self._has_xdotool:
            import time
            # Focus the window first
            self._run_command(["xdotool", "windowactivate", "--sync", window_id])
            time.sleep(0.3)
            # Capture focused window
            result = subprocess.run(
                ["scrot", "-u", save_path],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                captured = True

        # Method 3: Use ImageMagick import
        if not captured and self._has_import:
            result = subprocess.run(
                ["import", "-window", window_id, save_path],
                capture_output=True,
                timeout=10
            )
            if result.returncode == 0:
                captured = True

        if not captured:
            raise RuntimeError("Failed to capture window. Install scrot and xdotool, or ImageMagick")

        # Verify the file was created and has content
        import os
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            raise RuntimeError(f"Screenshot file is empty or missing: {save_path}")

        # Load and return image
        return Image.open(save_path)

    def get_text(self, window: str = None, engine: str = "auto") -> str:
        """
        Get text content from a window using OCR

        Args:
            window: Window title pattern, window ID, or None for active window
            engine: OCR engine to use:
                    - "auto": PaddleOCR if available, else Tesseract (default)
                    - "paddle": Force PaddleOCR (best for Chinese+English)
                    - "tesseract": Force Tesseract

        Returns:
            Extracted text
        """
        import os

        # Capture the window to a temp file
        temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        os.unlink(temp_path)  # Remove empty file

        image = self.capture(window, save_path=temp_path)

        # Select OCR engine
        use_paddle = False
        if engine == "auto":
            use_paddle = PaddleOCR is not None
        elif engine == "paddle":
            if PaddleOCR is None:
                raise RuntimeError("PaddleOCR not installed. Run: pip install paddlepaddle paddleocr")
            use_paddle = True
        elif engine == "tesseract":
            if pytesseract is None:
                raise RuntimeError("pytesseract not installed")
            use_paddle = False

        try:
            if use_paddle:
                text = self._ocr_paddle(temp_path)
            else:
                text = self._ocr_tesseract(temp_path)
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return text.strip()

    def _ocr_paddle(self, image_path: str) -> str:
        """Run OCR using PaddleOCR (best for Chinese+English)"""
        global _paddleocr_instance

        # Lazy initialization (first call takes longer)
        if _paddleocr_instance is None:
            import logging
            logging.getLogger('ppocr').setLevel(logging.WARNING)
            _paddleocr_instance = PaddleOCR(
                use_angle_cls=True,  # Detect text rotation
                lang='ch'            # Chinese model (supports English too)
            )

        result = _paddleocr_instance.ocr(image_path)

        # Extract text from result
        # PaddleOCR 3.x returns OCRResult objects with 'rec_texts' attribute
        lines = []
        if result:
            for item in result:
                # PaddleOCR 3.x: OCRResult object with rec_texts attribute
                if hasattr(item, 'rec_texts'):
                    lines.extend(item.rec_texts)
                # Dict-like access
                elif isinstance(item, dict) and 'rec_texts' in item:
                    lines.extend(item['rec_texts'])
                # Old format: [[box, (text, conf)], ...]
                elif isinstance(item, list):
                    for line in item:
                        if line and len(line) >= 2:
                            text_info = line[1]
                            if isinstance(text_info, tuple):
                                lines.append(text_info[0])
                            elif isinstance(text_info, str):
                                lines.append(text_info)

        return "\n".join(lines)

    def _ocr_tesseract(self, image_path: str) -> str:
        """Run OCR using Tesseract (fallback)"""
        import os

        if pytesseract is None:
            raise RuntimeError("pytesseract not installed")

        # Auto-detect available languages
        lang = None
        tessdata_path = "/usr/share/tessdata"
        if os.path.exists(tessdata_path):
            available = [f.replace(".traineddata", "")
                        for f in os.listdir(tessdata_path)
                        if f.endswith(".traineddata")]
            preferred = []
            if "chi_sim" in available:
                preferred.append("chi_sim")
            if "eng" in available:
                preferred.append("eng")
            if preferred:
                lang = "+".join(preferred)
            elif available:
                lang = next((l for l in available if l != "osd"), available[0])
        if not lang:
            lang = "eng"

        return pytesseract.image_to_string(image_path, lang=lang)

    def focus(self, window: str) -> bool:
        """
        Focus/activate a window

        Args:
            window: Window title pattern or window ID

        Returns:
            True if successful
        """
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        if window.startswith("0x"):
            # Window ID
            result = subprocess.run(["wmctrl", "-i", "-a", window], capture_output=True)
        else:
            # Window title
            result = subprocess.run(["wmctrl", "-a", window], capture_output=True)

        return result.returncode == 0

    def close(self, window: str) -> bool:
        """
        Close a window

        Args:
            window: Window title pattern or window ID

        Returns:
            True if successful
        """
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        if window.startswith("0x"):
            result = subprocess.run(["wmctrl", "-i", "-c", window], capture_output=True)
        else:
            result = subprocess.run(["wmctrl", "-c", window], capture_output=True)

        return result.returncode == 0

    def move(self, window: str, x: int, y: int, width: int = None, height: int = None) -> bool:
        """
        Move and optionally resize a window

        Args:
            window: Window title pattern or window ID
            x, y: New position
            width, height: New size (optional)

        Returns:
            True if successful
        """
        if not self._has_wmctrl:
            raise RuntimeError("wmctrl not installed")

        # Build geometry string
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
