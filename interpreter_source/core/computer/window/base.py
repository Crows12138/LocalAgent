"""
Cross-platform Window Control Base Class
Provides common interface and OCR functionality
"""

import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional
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
    _paddleocr_instance = None
except ImportError:
    PaddleOCR = None
    _paddleocr_instance = None


@dataclass
class WindowInfo:
    """Window information (cross-platform)"""
    id: str           # Window ID/handle
    pid: int          # Process ID
    title: str        # Window title
    app_name: str = ""  # Application name (optional)

    def __str__(self):
        return f"[{self.id}] {self.title} (PID: {self.pid})"


class WindowBase(ABC):
    """Abstract base class for window control"""

    def __init__(self, computer):
        self.computer = computer

    @abstractmethod
    def list(self) -> List[WindowInfo]:
        """List all open windows"""
        pass

    @abstractmethod
    def find(self, pattern: str) -> List[WindowInfo]:
        """Find windows matching a pattern"""
        pass

    @abstractmethod
    def get_active(self) -> Optional[WindowInfo]:
        """Get the currently active window"""
        pass

    @abstractmethod
    def capture(self, window: str = None, save_path: str = None) -> "Image":
        """Capture a window screenshot"""
        pass

    @abstractmethod
    def focus(self, window: str) -> bool:
        """Focus/activate a window"""
        pass

    @abstractmethod
    def close(self, window: str) -> bool:
        """Close a window"""
        pass

    @abstractmethod
    def move(self, window: str, x: int, y: int, width: int = None, height: int = None) -> bool:
        """Move and optionally resize a window"""
        pass

    # Shared OCR functionality (cross-platform)
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
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        self.capture(window, save_path=temp_path)

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
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return text.strip()

    def _ocr_paddle(self, image_path: str) -> str:
        """Run OCR using PaddleOCR (best for Chinese+English)"""
        global _paddleocr_instance

        if _paddleocr_instance is None:
            import logging
            logging.getLogger('ppocr').setLevel(logging.WARNING)
            _paddleocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang='ch'
            )

        result = _paddleocr_instance.ocr(image_path)

        lines = []
        if result:
            for item in result:
                if hasattr(item, 'rec_texts'):
                    lines.extend(item.rec_texts)
                elif isinstance(item, dict) and 'rec_texts' in item:
                    lines.extend(item['rec_texts'])
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

        # Try to find tessdata path
        lang = "eng"
        for tessdata_path in ["/usr/share/tessdata", "/usr/local/share/tessdata",
                              "C:\\Program Files\\Tesseract-OCR\\tessdata"]:
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
                break

        return pytesseract.image_to_string(image_path, lang=lang)

    def list_names(self) -> List[str]:
        """List all window titles"""
        return [w.title for w in self.list() if w.title]
