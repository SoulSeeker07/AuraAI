"""
UI Analyzer

Specialized analysis for UI elements and patterns.
"""


import logging
from typing import List, Dict, Any
import cv2
import numpy as np
from .models import ImageType


logger = logging.getLogger(__name__)


class UIAnalyzer:
    """
    Specialized UI element analysis.

    Provides detailed analysis for:
    - Buttons and clickable elements
    - Menus and menu items
    - Dialogs and modals
    - Forms and input fields
    - Notifications and toasts
    - Tooltips
    """

    def __init__(self):
        """Initialize the UI analyzer."""
        self.button_min_size = 50
        self.button_max_size = 500
        self.input_field_min_size = 100

    def analyze_ui(
        self,
        image: np.ndarray,
        image_type: ImageType = ImageType.SCREENSHOT
    ) -> dict:
        """
        Perform UI analysis.

        Args:
            image: Image to analyze
            image_type: Type of image

        Returns:
            UI analysis results
        """
        logger.info(f"Analyzing UI in {image_type.value} image")

        # Based on image type, use specialized UI analysis
        if image_type == ImageType.SCREENSHOT:
            return self._analyze_ui_screenshot(image)
        elif image_type == ImageType.DOCUMENT:
            return self._analyze_ui_document(image)
        else:
            return self._analyze_generic_ui(image)

    def _analyze_ui_screenshot(self, image: np.ndarray) -> dict:
        """
        Analyze UI in a screenshot.

        Args:
            image: Screenshot image

        Returns:
            UI analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect all UI elements
        buttons = self._detect_buttons(image, gray)
        menus = self._detect_menus(image, gray)
        dialogs = self._detect_dialogs(image, gray)
        forms = self._detect_forms(image, gray)
        notifications = self._detect_notifications(image, gray)
        tooltips = self._detect_tooltips(image, gray)

        # Count UI elements
        result = {
            'buttons': buttons,
            'menus': menus,
            'dialogs': dialogs,
            'forms': forms,
            'notifications': notifications,
            'tooltips': tooltips,
            'total_ui_elements': len(buttons) + len(menus) + len(dialogs) + len(forms) + len(notifications),
            'is_button_heavy': len(buttons) > len(menus) + len(dialogs),
            'is_menu_heavy': len(menus) > len(buttons) + len(dialogs),
            'is_form_heavy': len(forms) > len(buttons) + len(menus)
        }

        logger.info(f"UI analysis complete: "
                   f"{len(buttons)} buttons, {len(menus)} menus, "
                   f"{len(dialogs)} dialogs, {len(forms)} forms")

        return result

    def _analyze_ui_document(self, image: np.ndarray) -> dict:
        """
        Analyze UI in a document (forms, checklists, etc.).

        Args:
            image: Document image

        Returns:
            UI analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect form elements
        inputs = self._detect_form_inputs(image, gray)
        checkboxes = self._detect_checkboxes(image, gray)
        radio_buttons = self._detect_radio_buttons(image, gray)
        dropdowns = self._detect_dropdowns(image, gray)
        buttons = self._detect_buttons(image, gray)

        result = {
            'inputs': inputs,
            'checkboxes': checkboxes,
            'radio_buttons': radio_buttons,
            'dropdowns': dropdowns,
            'buttons': buttons,
            'total_form_elements': len(inputs) + len(checkboxes) + len(radio_buttons) + len(dropdowns) + len(buttons)
        }

        logger.info(f"Document UI analysis complete: "
                   f"{len(inputs)} inputs, {len(checkboxes)} checkboxes, "
                   f"{len(radio_buttons)} radio buttons, {len(dropdowns)} dropdowns")

        return result

    def _analyze_generic_ui(self, image: np.ndarray) -> dict:
        """
        Analyze generic UI elements.

        Args:
            image: Image to analyze

        Returns:
            UI analysis results
        """
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Detect generic interactive elements
        interactive_elements = self._detect_interactive_elements(image, gray)

        result = {
            'interactive_elements': interactive_elements,
            'total_elements': len(interactive_elements)
        }

        logger.info(f"Generic UI analysis complete: {len(interactive_elements)} elements")

        return result

    def _detect_buttons(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect buttons in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected buttons
        """
        buttons = []

        # Detect button-like shapes
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Check size
            if area < self.button_min_size or area > self.button_max_size:
                continue

            # Check aspect ratio (buttons are typically rectangular)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 3:
                continue

            # Check if it's likely a button (lighter, has borders)
            roi = image[y:y+h, x:x+w]
            if self._is_button_like(roi, w, h):
                buttons.append({
                    'type': 'button',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return buttons

    def _detect_menus(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect menus in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected menus
        """
        menus = []

        # Detect menu-like structures
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Check size (menus are usually substantial)
            if area < 500 or area > 100000:
                continue

            # Check aspect ratio
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3:
                continue

            # Check if menu-like
            roi = image[y:y+h, x:x+w]
            if self._is_menu_like(roi):
                menus.append({
                    'type': 'menu',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return menus

    def _detect_dialogs(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect dialog boxes in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected dialogs
        """
        dialogs = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Dialogs are typically square-ish
            if area < 500 or area > 200000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_dialog_like(roi, w, h):
                dialogs.append({
                    'type': 'dialog',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return dialogs

    def _detect_forms(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect form elements in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected form elements
        """
        forms = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Check size
            if area < 1000 or area > 50000:
                continue

            # Check aspect ratio (forms are usually rectangular)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 5:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_form_like(roi, w, h):
                forms.append({
                    'type': 'form',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return forms

    def _detect_notifications(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect notifications/toasts in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected notifications
        """
        notifications = []

        # Notifications are typically small, near edges
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Check size (small notifications)
            if area < 1000 or area > 20000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_notification_like(roi, w, h):
                notifications.append({
                    'type': 'notification',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return notifications

    def _detect_tooltips(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect tooltips in image.

        Args:
            image: Image to analyze
            gray: Grayscale version of image

        Returns:
            List of detected tooltips
        """
        tooltips = []

        # Tooltips are typically very small
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_tooltip_size = 500

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < min_tooltip_size:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 3:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_tooltip_like(roi, w, h):
                tooltips.append({
                    'type': 'tooltip',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return tooltips

    def _detect_form_inputs(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect input fields in document."""
        inputs = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            # Check size (input fields are substantial)
            if area < self.input_field_min_size or area > 50000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 5:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_input_like(roi):
                inputs.append({
                    'type': 'input_field',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h}
                })

        return inputs

    def _detect_checkboxes(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect checkboxes in document."""
        checkboxes = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_size = 200

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < min_size or area > 5000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_checkbox_like(roi):
                checkboxes.append({
                    'type': 'checkbox',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h}
                })

        return checkboxes

    def _detect_radio_buttons(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect radio buttons in document."""
        radio_buttons = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_size = 200

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < min_size or area > 5000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 2:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_radio_button_like(roi):
                radio_buttons.append({
                    'type': 'radio_button',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h}
                })

        return radio_buttons

    def _detect_dropdowns(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect dropdown menus in document."""
        dropdowns = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_size = 500

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < min_size or area > 20000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 3:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_dropdown_like(roi):
                dropdowns.append({
                    'type': 'dropdown',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h}
                })

        return dropdowns

    def _detect_interactive_elements(self, image: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """Detect generic interactive elements."""
        interactive = []

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)

            if area < 500 or area > 50000:
                continue

            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.2 or aspect_ratio > 5:
                continue

            roi = image[y:y+h, x:x+w]
            if self._is_interactive_like(roi, w, h):
                interactive.append({
                    'type': 'interactive_element',
                    'position': {'x': x, 'y': y, 'width': w, 'height': h},
                    'area': area
                })

        return interactive

    def _is_button_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like a button."""
        # Convert to grayscale
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # Check brightness (buttons are typically brighter)
        brightness = np.mean(gray)
        if brightness < 100:
            return False

        # Check for border-like edges
        edges = cv2.Canny(gray, 50, 150)
        edge_ratio = np.sum(edges > 0) / (w * h)

        # Buttons have some edge content
        return edge_ratio > 0.01

    def _is_menu_like(self, roi: np.ndarray) -> bool:
        """Check if region looks like a menu."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # Check for regular patterns
        brightness = np.mean(gray)
        return brightness > 80

    def _is_dialog_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like a dialog."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        # Check brightness (dialogs are typically bright)
        brightness = np.mean(gray)
        if brightness < 80:
            return False

        # Check aspect ratio
        aspect_ratio = w / h if h > 0 else 0
        return 0.5 <= aspect_ratio <= 2

    def _is_form_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like a form."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 70

    def _is_notification_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like a notification."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 80

    def _is_tooltip_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like a tooltip."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 75

    def _is_input_like(self, roi: np.ndarray) -> bool:
        """Check if region looks like an input field."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 70

    def _is_checkbox_like(self, roi: np.ndarray) -> bool:
        """Check if region looks like a checkbox."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 65

    def _is_radio_button_like(self, roi: np.ndarray) -> bool:
        """Check if region looks like a radio button."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 65

    def _is_dropdown_like(self, roi: np.ndarray) -> bool:
        """Check if region looks like a dropdown."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 75

    def _is_interactive_like(self, roi: np.ndarray, w: int, h: int) -> bool:
        """Check if region looks like an interactive element."""
        if len(roi.shape) == 3:
            gray = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
        else:
            gray = roi

        brightness = np.mean(gray)
        return brightness > 70
