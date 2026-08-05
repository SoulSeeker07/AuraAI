"""
Image Loader

Handles loading and validation of images for the Vision System.
"""

import logging
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image

from .models import ImageType

logger = logging.getLogger(__name__)


class ImageLoader:
    """
    Handles loading and validating images.

    Provides utilities for:
    - Loading images from various sources
    - Validating image format and size
    - Converting between image formats
    """

    def __init__(self):
        """Initialize the image loader."""
        self.supported_formats = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}

    def load_image(
        self, image_path: Union[str, Path], return_format: str = "cv2"
    ) -> tuple[np.ndarray, ImageType]:
        """
        Load an image from a file.

        Args:
            image_path: Path to image file
            return_format: Format to return ('cv2', 'pil', 'numpy')

        Returns:
            Tuple of (image, image_type)
        """
        image_path = Path(image_path)

        # Validate file exists
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Validate file extension
        if image_path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"Unsupported image format: {image_path.suffix}")

        # Load image using PIL first (more reliable)
        with Image.open(image_path) as pil_img:
            # Convert to RGB if necessary
            if pil_img.mode in ("RGBA", "LA", "P"):
                pil_img = pil_img.convert("RGB")

            # Get image type based on extension
            image_type = self._detect_image_type(image_path.suffix)

            # Convert to requested format
            if return_format == "pil":
                return pil_img, image_type
            elif return_format == "numpy":
                img_array = np.array(pil_img)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                return img_array, image_type
            elif return_format == "cv2":
                img_array = np.array(pil_img)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                return img_array, image_type
            else:
                raise ValueError(f"Unsupported return format: {return_format}")

    def load_from_cv2(self, image_array: np.ndarray) -> tuple[np.ndarray, ImageType]:
        """
        Load image from numpy array (already in OpenCV format).

        Args:
            image_array: OpenCV format image array

        Returns:
            Tuple of (image_array, image_type)
        """
        if len(image_array.shape) != 3:
            raise ValueError("Image must be in 3-channel format (H, W, C)")

        # Detect image type based on size and characteristics
        image_type = self._detect_image_type_from_array(image_array)

        return image_array, image_type

    def load_from_pil(self, pil_image: Image.Image) -> tuple[np.ndarray, ImageType]:
        """
        Load image from PIL Image object.

        Args:
            pil_image: PIL Image object

        Returns:
            Tuple of (cv2 image array, image_type)
        """
        # Convert to RGB if necessary
        if pil_image.mode in ("RGBA", "LA", "P"):
            pil_image = pil_image.convert("RGB")

        # Convert to numpy array
        img_array = np.array(pil_image)

        # Convert to OpenCV format
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Detect image type
        image_type = self._detect_image_type_from_array(img_array)

        return img_array, image_type

    def load_from_bytes(
        self, image_bytes: bytes, return_format: str = "cv2"
    ) -> tuple[np.ndarray, ImageType]:
        """
        Load image from bytes.

        Args:
            image_bytes: Image data as bytes
            return_format: Format to return ('cv2', 'pil', 'numpy')

        Returns:
            Tuple of (image, image_type)
        """
        # Load using PIL
        pil_img = Image.open(image_bytes)

        # Convert to RGB if necessary
        if pil_img.mode in ("RGBA", "LA", "P"):
            pil_img = pil_img.convert("RGB")

        # Get image type
        image_type = self._detect_image_type_from_pil(pil_img)

        # Convert to requested format
        if return_format == "pil":
            return pil_img, image_type
        elif return_format == "numpy":
            img_array = np.array(pil_img)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            return img_array, image_type
        elif return_format == "cv2":
            img_array = np.array(pil_img)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            return img_array, image_type
        else:
            raise ValueError(f"Unsupported return format: {return_format}")

    def load_from_base64(
        self, base64_str: str, return_format: str = "cv2"
    ) -> tuple[np.ndarray, ImageType]:
        """
        Load image from base64 encoded string.

        Args:
            base64_str: Base64 encoded image string
            return_format: Format to return ('cv2', 'pil', 'numpy')

        Returns:
            Tuple of (image, image_type)
        """
        import base64

        # Decode base64
        image_bytes = base64.b64decode(base64_str)

        return self.load_from_bytes(image_bytes, return_format)

    def validate_image(self, image: Union[np.ndarray, Image.Image]) -> bool:
        """
        Validate an image object.

        Args:
            image: Image to validate

        Returns:
            True if valid, False otherwise
        """
        if isinstance(image, np.ndarray):
            return self._validate_cv2_image(image)
        elif isinstance(image, Image.Image):
            return self._validate_pil_image(image)
        else:
            return False

    def _validate_cv2_image(self, image: np.ndarray) -> bool:
        """Validate an OpenCV format image."""
        if len(image.shape) != 3:
            return False

        height, width = image.shape[:2]
        return width > 0 and height > 0

    def _validate_pil_image(self, image: Image.Image) -> bool:
        """Validate a PIL Image object."""
        if image is None:
            return False

        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")

        width, height = image.size
        return width > 0 and height > 0

    def _detect_image_type(self, suffix: str) -> ImageType:
        """
        Detect image type from file extension.

        Args:
            suffix: File extension

        Returns:
            Detected ImageType
        """
        suffix_lower = suffix.lower()

        if suffix_lower in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"):
            # Try to detect more specifically
            # This is a heuristic based on file characteristics
            return ImageType.UNKNOWN

        return ImageType.UNKNOWN

    def _detect_image_type_from_pil(self, pil_image: Image.Image) -> ImageType:
        """Detect image type from PIL Image."""
        width, height = pil_image.size

        # Screen captures are typically landscape with higher aspect ratio
        if height > width * 1.2 and width > 1920:
            return ImageType.SCREENSHOT

        # Code files typically have lots of horizontal lines
        # This is a simplification - actual detection would require analysis
        return ImageType.UNKNOWN

    def _detect_image_type_from_array(self, image_array: np.ndarray) -> ImageType:
        """Detect image type from numpy array."""
        height, width = image_array.shape[:2]

        # Screen captures are typically landscape with higher aspect ratio
        if height > width * 1.2 and width > 1920:
            return ImageType.SCREENSHOT

        return ImageType.UNKNOWN

    def get_image_info(self, image: Union[np.ndarray, Image.Image]) -> dict:
        """
        Get information about an image.

        Args:
            image: Image to analyze

        Returns:
            Dictionary with image information
        """
        if isinstance(image, np.ndarray):
            height, width = image.shape[:2]
            channels = image.shape[2] if len(image.shape) == 3 else 1
            return {
                "width": width,
                "height": height,
                "channels": channels,
                "dtype": str(image.dtype),
                "type": "cv2",
            }
        elif isinstance(image, Image.Image):
            width, height = image.size
            return {"width": width, "height": height, "mode": image.mode, "type": "pil"}
        else:
            return {}

    def resize_image(
        self,
        image: Union[np.ndarray, Image.Image],
        max_width: int = 2048,
        max_height: int = 2048,
    ) -> tuple[Union[np.ndarray, Image.Image], tuple[int, int]]:
        """
        Resize image while maintaining aspect ratio.

        Args:
            image: Image to resize
            max_width: Maximum width
            max_height: Maximum height

        Returns:
            Tuple of (resized image, (width, height))
        """
        if isinstance(image, np.ndarray):
            return self._resize_cv2_image(image, max_width, max_height)
        elif isinstance(image, Image.Image):
            return self._resize_pil_image(image, max_width, max_height)
        else:
            raise ValueError("Unsupported image type")

    def _resize_cv2_image(
        self, image: np.ndarray, max_width: int, max_height: int
    ) -> tuple[np.ndarray, tuple[int, int]]:
        """Resize a CV2 image."""
        height, width = image.shape[:2]

        # Calculate scale
        scale = min(max_width / width, max_height / height, 1.0)

        # Don't resize if already small enough
        if scale >= 1.0:
            return image, (width, height)

        # Resize
        new_width = int(width * scale)
        new_height = int(height * scale)

        resized = cv2.resize(
            image, (new_width, new_height), interpolation=cv2.INTER_AREA
        )

        return resized, (new_width, new_height)

    def _resize_pil_image(
        self, image: Image.Image, max_width: int, max_height: int
    ) -> tuple[Image.Image, tuple[int, int]]:
        """Resize a PIL Image."""
        width, height = image.size

        # Calculate scale
        scale = min(max_width / width, max_height / height, 1.0)

        # Don't resize if already small enough
        if scale >= 1.0:
            return image, (width, height)

        # Resize
        new_width = int(width * scale)
        new_height = int(height * scale)

        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return resized, (new_width, new_height)

    def convert_format(
        self, image: Union[np.ndarray, Image.Image], target_format: str = "cv2"
    ) -> Union[np.ndarray, Image.Image]:
        """
        Convert image to target format.

        Args:
            image: Image to convert
            target_format: Target format ('cv2', 'pil')

        Returns:
            Converted image
        """
        if isinstance(image, np.ndarray):
            if target_format == "pil":
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                return Image.fromarray(image_rgb)
            elif target_format == "cv2":
                return image
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
        elif isinstance(image, Image.Image):
            if target_format == "pil":
                return image
            elif target_format == "cv2":
                img_array = np.array(image)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                return img_array
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
        else:
            raise ValueError("Unsupported image type")
