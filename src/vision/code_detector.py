"""
Code Detector

Detects and analyzes code snippets in images.
"""

import logging
from typing import Any

import cv2
import numpy as np

from .models import ImageType

logger = logging.getLogger(__name__)


class CodeDetector:
    """
    Detects and analyzes code in images.

    Provides code detection for:
    - Code snippets and blocks
    - Programming languages
    - Syntax highlighting patterns
    - Function definitions
    - Variable declarations
    """

    def __init__(self):
        """Initialize the code detector."""
        self.min_code_line_size = 50
        self.max_code_line_size = 1000
        self.language_patterns = {
            "python": [
                "def ",
                "import ",
                "from ",
                "class ",
                "if __name__",
                "print(",
                "return ",
            ],
            "javascript": [
                "function ",
                "const ",
                "let ",
                "var ",
                "return ",
                "if (",
                "console.log",
            ],
            "typescript": [
                "function ",
                "const ",
                "let ",
                "var ",
                "interface ",
                "type ",
                "export ",
            ],
            "java": [
                "public class ",
                "private ",
                "public static void",
                "import ",
                "class ",
            ],
            "cpp": ["#include", "int main(", "using namespace", "class ", "struct "],
            "c": ["#include", "int main(", "struct ", "typedef ", "#define "],
            "go": ["func ", "package ", "import ", "var ", "const ", "go "],
            "rust": ["fn ", "pub ", "use ", "let ", "const ", "struct ", "enum "],
            "php": ["<?php", "function ", "class ", "if (", "echo "],
            "ruby": ["def ", "class ", "module ", "if ", "puts "],
            "sql": [
                "SELECT",
                "FROM ",
                "WHERE ",
                "INSERT INTO",
                "UPDATE ",
                "CREATE TABLE",
            ],
            "html": ["<div", "<span", "<p>", "<h1>", "<br>", "</div>"],
            "css": [
                ".",
                "#",
                "{",
                "}",
                "@keyframes",
                "background:",
                "color:",
                "font-size:",
            ],
            "json": ["{", '"', ":", "}", "[", "]"],
        }

    def detect_code(
        self, image: np.ndarray, image_type: ImageType = ImageType.CODE
    ) -> dict:
        """
        Detect code in image.

        Args:
            image: Image to analyze
            image_type: Type of image

        Returns:
            Code detection results
        """
        logger.info(f"Detecting code in {image_type.value} image")

        # Based on image type, use specialized code detection
        if image_type == ImageType.CODE:
            return self._analyze_code_image(image)
        elif image_type == ImageType.SCREENSHOT:
            return self._analyze_code_in_screenshot(image)
        elif image_type == ImageType.DOCUMENT:
            return self._analyze_code_in_document(image)
        else:
            return self._analyze_code_generic(image)

    def _analyze_code_image(self, image: np.ndarray) -> dict:
        """
        Analyze code from code image.

        Args:
            image: Code image

        Returns:
            Code analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect code lines
        code_lines = self._detect_code_lines(gray, image)

        # Detect programming language
        language = self._detect_programming_language(image, code_lines)

        # Extract code snippets
        snippets = self._extract_code_snippets(image, code_lines)

        # Count lines of code
        lines_of_code = len(code_lines)

        result = {
            "language": language,
            "lines": code_lines,
            "snippets": snippets,
            "line_count": lines_of_code,
            "has_syntax_highlighting": self._detect_syntax_highlighting(image),
            "complexity": self._calculate_complexity(snippets, language),
        }

        logger.info(f"Code analysis: {language}, {lines_of_code} lines")

        return result

    def _analyze_code_in_screenshot(self, image: np.ndarray) -> dict:
        """
        Detect code in screenshot.

        Args:
            image: Screenshot image

        Returns:
            Code detection results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect code-like regions
        code_regions = self._detect_code_regions(gray, image)

        # Analyze each region
        results = []
        for region in code_regions:
            image_copy = image.copy()
            x, y, w, h = region["position"].values()

            # Extract region
            roi = image_copy[y : y + h, x : x + w]

            # Detect language
            language = self._detect_programming_language(roi, [])

            # Detect lines
            lines = self._detect_code_lines(gray, image, region)

            results.append(
                {
                    "position": region["position"],
                    "language": language,
                    "lines": lines,
                    "line_count": len(lines),
                }
            )

        result = {
            "code_regions": results,
            "total_regions": len(results),
            "total_lines": sum(r["line_count"] for r in results),
            "complexity": "medium" if len(results) > 0 else "simple",
        }

        logger.info(f"Code in screenshot: {len(results)} regions")

        return result

    def _analyze_code_in_document(self, image: np.ndarray) -> dict:
        """
        Detect code in document.

        Args:
            image: Document image

        Returns:
            Code detection results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect code blocks in document
        code_blocks = self._detect_code_blocks(gray, image)

        # Analyze each block
        results = []
        for block in code_blocks:
            x, y, w, h = block["position"].values()

            # Extract block
            roi = image[y : y + h, x : x + w]

            # Detect language
            language = self._detect_programming_language(roi, [])

            results.append(
                {
                    "position": block["position"],
                    "language": language,
                    "line_count": block["line_count"],
                }
            )

        result = {
            "code_blocks": results,
            "total_blocks": len(results),
            "total_lines": sum(b["line_count"] for b in results),
        }

        logger.info(f"Code in document: {len(results)} blocks")

        return result

    def _analyze_code_generic(self, image: np.ndarray) -> dict:
        """
        Perform generic code detection.

        Args:
            image: Image to analyze

        Returns:
            Generic code detection results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect code-like structures
        code_lines = self._detect_code_lines(gray, image)

        # Detect language
        language = self._detect_programming_language(image, code_lines)

        result = {
            "language": language,
            "lines": code_lines,
            "line_count": len(code_lines),
        }

        logger.info(f"Generic code detection: {language}, {len(code_lines)} lines")

        return result

    def _detect_code_lines(
        self, gray: np.ndarray, image: np.ndarray, region: dict = None
    ) -> list[dict[str, Any]]:
        """
        Detect individual lines of code.

        Args:
            gray: Grayscale image
            image: RGB image
            region: Optional region to analyze

        Returns:
            List of code lines
        """
        code_lines = []

        if region:
            x, y, w, h = region["position"].values()
            roi_gray = gray[y : y + h, x : x + w]
            roi_image = image[y : y + h, x : x + w]
        else:
            roi_gray = gray
            roi_image = image

        # Detect horizontal lines (code lines)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 10))
        horizontal_lines = cv2.morphologyEx(roi_gray, cv2.MORPH_OPEN, kernel)

        _, binary = cv2.threshold(
            horizontal_lines, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Check size
            if w < self.min_code_line_size or w > self.max_code_line_size:
                continue

            # Get line content
            line_roi = roi_image[y : y + h, x : x + w]

            code_lines.append(
                {
                    "position": {"x": x, "y": y, "width": w, "height": h},
                    "length": w,
                    "height": h,
                }
            )

        # Sort lines by y-coordinate
        code_lines.sort(key=lambda l: l["position"]["y"])

        return code_lines

    def _detect_code_regions(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """
        Detect regions containing code.

        Args:
            gray: Grayscale image
            image: RGB image

        Returns:
            List of code regions
        """
        code_regions = []

        # Detect code-like blocks using morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 50))
        dilated = cv2.dilate(gray, kernel, iterations=3)

        _, binary = cv2.threshold(dilated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        min_region_size = 5000
        max_region_size = 500000

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_region_size or area > max_region_size:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Check if region has code-like characteristics
            roi = image[y : y + h, x : x + w]
            if self._has_code_characteristics(roi):
                code_regions.append(
                    {
                        "type": "code_region",
                        "position": {"x": x, "y": y, "width": w, "height": h},
                        "area": area,
                    }
                )

        # Sort regions by size (largest first)
        code_regions.sort(key=lambda r: r["area"], reverse=True)

        return code_regions

    def _detect_code_blocks(
        self, gray: np.ndarray, image: np.ndarray
    ) -> list[dict[str, Any]]:
        """
        Detect code blocks in document.

        Args:
            gray: Grayscale image
            image: RGB image

        Returns:
            List of code blocks
        """
        code_blocks = []

        # Detect rectangular regions
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            # Code blocks are typically substantial
            if area < 2000 or area > 200000:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Check if block has code-like characteristics
            roi = image[y : y + h, x : x + w]
            if self._has_code_characteristics(roi):
                # Count lines
                lines = self._detect_code_lines(gray, image)

                code_blocks.append(
                    {
                        "type": "code_block",
                        "position": {"x": x, "y": y, "width": w, "height": h},
                        "area": area,
                        "line_count": len(lines),
                    }
                )

        # Sort blocks by y-coordinate
        code_blocks.sort(key=lambda b: b["position"]["y"])

        return code_blocks

    def _detect_programming_language(
        self, image: np.ndarray, code_lines: list[dict[str, Any]]
    ) -> str:
        """
        Detect programming language from image or code lines.

        Args:
            image: Image to analyze
            code_lines: Detected code lines

        Returns:
            Detected language
        """
        # Convert to grayscale for analysis
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # Check for syntax highlighting patterns (color differences)
        has_highlighting = self._detect_syntax_highlighting(image)

        # If syntax highlighting is present, use it to infer language
        if has_highlighting:
            # Count colored regions
            colored_regions = self._count_colored_regions(image)
            language = self._infer_language_from_patterns(colored_regions, image)
            if language != "unknown":
                return language

        # Check for language-specific patterns in code lines
        for line in code_lines:
            for lang, patterns in self.language_patterns.items():
                if self._has_language_patterns(line, patterns):
                    return lang

        # Check for language-specific patterns in image
        for lang, patterns in self.language_patterns.items():
            if self._has_language_patterns_in_image(gray, patterns):
                return lang

        return "unknown"

    def _detect_syntax_highlighting(self, image: np.ndarray) -> bool:
        """
        Check if image has syntax highlighting.

        Args:
            image: RGB image

        Returns:
            True if syntax highlighting detected
        """
        # Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)

        # Check for color variation
        color_variance = np.var(hsv[:, :, :2])

        # High color variance indicates syntax highlighting
        return color_variance > 1000

    def _count_colored_regions(self, image: np.ndarray) -> int:
        """
        Count colored regions in image.

        Args:
            image: RGB image

        Returns:
            Number of colored regions
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Count regions
        return len(contours)

    def _infer_language_from_patterns(
        self, region_count: int, image: np.ndarray
    ) -> str:
        """
        Infer programming language from colored region count.

        Args:
            region_count: Number of colored regions
            image: RGB image

        Returns:
            Detected language or 'unknown'
        """
        # This is a heuristic based on typical syntax highlighting
        # Different languages have different highlighting patterns

        if region_count < 10:
            return "unknown"

        # Check for specific patterns
        if self._has_python_patterns(image):
            return "python"

        return "unknown"

    def _has_language_patterns(self, line: dict[str, Any], patterns: list[str]) -> bool:
        """
        Check if line contains language patterns.

        Args:
            line: Code line
            patterns: List of pattern strings

        Returns:
            True if patterns found
        """
        # This would require extracting actual text from the line
        # For now, just return False
        return False

    def _has_language_patterns_in_image(
        self, gray: np.ndarray, patterns: list[str]
    ) -> bool:
        """
        Check if image contains language patterns.

        Args:
            gray: Grayscale image
            patterns: List of pattern strings

        Returns:
            True if patterns found
        """
        # Convert patterns to grayscale and check
        # This is a simplified approach
        return False

    def _has_code_characteristics(self, roi: np.ndarray) -> bool:
        """
        Check if region has code-like characteristics.

        Args:
            roi: Region of interest

        Returns:
            True if region has code characteristics
        """
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # Check for horizontal lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 10))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)

        # Check for dark background with light text
        brightness = np.mean(gray)
        return brightness > 50

    def _extract_code_snippets(
        self, image: np.ndarray, code_lines: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Extract code snippets from code lines.

        Args:
            image: RGB image
            code_lines: Detected code lines

        Returns:
            List of code snippets
        """
        snippets = []

        for line in code_lines:
            x, y, w, h = line["position"].values()
            roi = image[y : y + h, x : x + w]

            snippets.append(
                {
                    "type": "code_line",
                    "position": line["position"],
                    "height": h,
                    "length": w,
                }
            )

        return snippets

    def _calculate_complexity(
        self, snippets: list[dict[str, Any]], language: str
    ) -> str:
        """
        Calculate code complexity.

        Args:
            snippets: Code snippets
            language: Detected language

        Returns:
            Complexity level
        """
        if not snippets:
            return "simple"

        # Count snippets
        snippet_count = len(snippets)

        if snippet_count < 10:
            return "simple"
        elif snippet_count < 50:
            return "medium"
        elif snippet_count < 100:
            return "complex"
        else:
            return "very_complex"

    def _has_python_patterns(self, image: np.ndarray) -> bool:
        """Check if image shows Python patterns."""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # Python typically has indentation and specific patterns
        brightness = np.mean(gray)
        return brightness > 40
