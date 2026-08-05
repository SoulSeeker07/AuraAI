"""
Image Preprocessing

Utilities for image preprocessing before OCR and analysis.
"""

import logging

import cv2
import numpy as np

from .models import OCRSettings

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Handles image preprocessing operations.

    Preprocessing steps:
    1. Load and convert image
    2. Rotate and deskew
    3. Resize
    4. Enhance contrast and brightness
    5. Remove noise
    """

    def __init__(self, settings: OCRSettings = None):
        """
        Initialize the image preprocessor.

        Args:
            settings: OCR processing settings
        """
        self.settings = settings or OCRSettings()

    def preprocess_image(
        self, image_path: str, original_size: tuple[int, int] | None = None
    ) -> tuple[np.ndarray, tuple[int, int]]:
        """
        Load and preprocess an image.

        Args:
            image_path: Path to the image file
            original_size: Original dimensions (for reference)

        Returns:
            Tuple of (preprocessed image, processed dimensions)
        """
        logger.info(f"Preprocessing image: {image_path}")

        # Load image
        img = self._load_image(image_path)

        # Get dimensions
        height, width = img.shape[:2]

        # Apply preprocessing steps
        if self.settings.auto_rotate:
            img = self._auto_rotate(img)

        if self.settings.deskew:
            img = self._deskew(img)

        # Resize (keep aspect ratio)
        img = self._resize_image(img)

        # Enhance image
        img = self._enhance_image(img)

        # Remove noise
        img = self._remove_noise(img)

        logger.info(
            f"Preprocessed image: {width}x{height} -> " f"{img.shape[1]}x{img.shape[0]}"
        )
        return img, (img.shape[1], img.shape[0])

    def _load_image(self, image_path: str) -> np.ndarray:
        """Load image from file."""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Convert BGR to RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def _auto_rotate(self, img: np.ndarray) -> np.ndarray:
        """
        Automatically detect and correct image orientation.

        Uses morphological operations to find the dominant angle
        and rotate the image accordingly.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Threshold to create binary image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        # Find the largest contour (likely the document)
        if contours:
            max_contour = max(contours, key=cv2.contourArea)

            # Get bounding box
            x, y, w, h = cv2.boundingRect(max_contour)

            # Calculate angle
            angle = self._detect_rotation_angle(binary, max_contour)

            # Rotate image if angle is significant
            if abs(angle) > 1.0:
                logger.info(f"Auto-rotating image by {angle:.1f} degrees")
                img = self._rotate_image(img, angle)

        return img

    def _detect_rotation_angle(self, image: np.ndarray, contour: np.ndarray) -> float:
        """
        Detect the rotation angle of the image.

        Args:
            image: Binary image
            contour: Contour to analyze

        Returns:
            Rotation angle in degrees
        """
        # Get bounding box coordinates
        rect = cv2.minAreaRect(contour)
        angle = rect[2]

        # The angle is in degrees relative to horizontal
        # Need to adjust based on image orientation
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = -90 + angle

        return angle

    def _rotate_image(self, img: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate an image by the specified angle.

        Args:
            img: Image to rotate
            angle: Rotation angle in degrees

        Returns:
            Rotated image
        """
        # Rotate image
        h, w = img.shape[:2]
        center = (w // 2, h // 2)

        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )

        return rotated

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """
        Deskew the image to correct any remaining skew.

        Uses morphological operations to find the dominant angle
        and correct it.
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Threshold to create binary image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Get image dimensions
        height, width = binary.shape[:2]

        # Find hull of the binary image
        coords = np.column_stack(np.where(binary > 0))
        angle = cv2.minAreaRect(coords)[-1]

        # Correct angle
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = -90 + angle

        if abs(angle) < 1.0:
            return img

        # Rotate
        M = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        deskewed = cv2.warpAffine(
            binary,
            M,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        # Convert back to RGB
        deskewed_rgb = cv2.cvtColor(deskewed, cv2.COLOR_GRAY2RGB)

        logger.debug(f"Deskewing image by {angle:.1f} degrees")
        return deskewed_rgb

    def _resize_image(self, img: np.ndarray, max_width: int = 2048) -> np.ndarray:
        """
        Resize image while maintaining aspect ratio.

        Args:
            img: Image to resize
            max_width: Maximum width for resizing

        Returns:
            Resized image
        """
        height, width = img.shape[:2]

        # Don't resize if image is already small enough
        if width <= max_width:
            return img

        # Calculate new dimensions
        scale = max_width / width
        new_width = max_width
        new_height = int(height * scale)

        # Resize
        resized = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

        logger.debug(f"Resizing from {width}x{height} to {new_width}x{new_height}")
        return resized

    def _enhance_image(self, img: np.ndarray) -> np.ndarray:
        """
        Enhance image contrast and brightness.

        Args:
            img: Image to enhance

        Returns:
            Enhanced image
        """
        # Convert to grayscale for enhancement
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Apply adaptive thresholding for better OCR
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Convert back to RGB
        enhanced_rgb = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

        logger.debug("Enhanced image contrast")
        return enhanced_rgb

    def _remove_noise(self, img: np.ndarray) -> np.ndarray:
        """
        Remove noise from the image.

        Uses morphological operations to remove small artifacts.

        Args:
            img: Image to denoise

        Returns:
            Denoised image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        # Apply morphological closing (remove small holes)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)

        # Apply morphological opening (remove small noise)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)

        # Convert back to RGB
        denoised_rgb = cv2.cvtColor(opened, cv2.COLOR_GRAY2RGB)

        logger.debug("Removed noise from image")
        return denoised_rgb

    def get_preprocessed_image(self, image_path: str) -> np.ndarray:
        """
        Get preprocessed image as numpy array.

        Args:
            image_path: Path to image file

        Returns:
            Preprocessed image as numpy array
        """
        img, _ = self.preprocess_image(image_path)
        return img

    def save_preprocessed_image(self, img: np.ndarray, output_path: str) -> str:
        """
        Save preprocessed image to file.

        Args:
            img: Preprocessed image
            output_path: Output file path

        Returns:
            Path to saved image
        """
        # Convert to BGR for OpenCV save
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img_bgr)

        logger.info(f"Saved preprocessed image to: {output_path}")
        return output_path
