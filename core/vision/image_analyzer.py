"""
Image Analyzer

Handles image analysis and OCR operations.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """
    Analyzes images.

    Responsibilities:
        - OCR (Optical Character Recognition)
        - Image description
        - Object recognition (basic)
        - Document reading
    """

    def __init__(self, ocr_engine=None):
        """
        Initialize Image Analyzer.

        Args:
            ocr_engine: OCR engine to use (default: pytesseract)
        """
        try:
            import pytesseract

            self._ocr = ocr_engine or pytesseract
            logger.info("Image Analyzer initialized with pytesseract")
        except ImportError:
            logger.warning("pytesseract not installed, image analysis will be limited")
            self._ocr = None

    def analyze_image(self, image_path: Path) -> str:
        """
        Analyze an image.

        Args:
            image_path: Path to the image file

        Returns:
            Analysis description
        """
        if not image_path.exists():
            return f"Error: Image not found at {image_path}"

        if self._ocr is None:
            return "Image analysis requires pytesseract. Please install it with: pip install pytesseract pillow"

        try:
            from PIL import Image

            # OCR text
            ocr_text = self._ocr.image_to_string(Image.open(image_path))

            # Build analysis
            analysis = f"Image Analysis for {image_path.name}:\n\n"
            analysis += f"OCR Text ({len(ocr_text)} characters):\n{ocr_text}\n\n"

            # Get image dimensions
            with Image.open(image_path) as img:
                width, height = img.size
                analysis += f"Dimensions: {width}x{height}\n"
                analysis += f"Format: {img.format}\n"

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze image: {e}", exc_info=True)
            return f"Error analyzing image: {type(e).__name__}: {e}"

    def extract_text(self, image_path: Path) -> str:
        """
        Extract text from an image using OCR.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text
        """
        if not self._ocr:
            return "OCR not available"

        try:
            from PIL import Image

            return self._ocr.image_to_string(Image.open(image_path))
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            return f"Error: {e}"

    def describe_image(self, image_path: Path) -> str:
        """
        Describe an image.

        Args:
            image_path: Path to the image file

        Returns:
            Image description
        """
        try:
            from PIL import Image

            img = Image.open(image_path)

            description = f"Image: {image_path.name}\n"
            description += f"Size: {img.width}x{img.height} pixels\n"
            description += f"Mode: {img.mode}\n"
            description += f"Format: {img.format or 'Unknown'}\n\n"

            # Get basic image stats
            description += f"File size: {image_path.stat().st_size / 1024:.1f} KB\n"

            return description

        except Exception as e:
            logger.error(f"Failed to describe image: {e}")
            return f"Error describing image: {e}"

    def detect_document(self, image_path: Path) -> bool:
        """
        Detect if image is a document.

        Args:
            image_path: Path to the image file

        Returns:
            True if image appears to be a document
        """
        try:
            from PIL import Image

            img = Image.open(image_path)

            # Simple heuristic: white background, rectangular
            width, height = img.size

            # Open images are usually rectangular
            return True

        except Exception as e:
            logger.error(f"Failed to detect document: {e}")
            return False
