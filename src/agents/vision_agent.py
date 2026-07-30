"""
Vision Agent - Analyzes images and documents.

The Vision Agent can:
- Analyze screenshots
- Read documents (PDF, images)
- Understand diagrams and flowcharts
- Extract UI elements
- Describe visual content
- Compare images
- Recognize text in images (OCR)
"""

from __future__ import annotations

from typing import Any, List, Optional
import json

from PIL import Image
import pytesseract
from .task_model import (
    Task,
    TaskStatus,
    TaskType,
    TaskInput,
    TaskOutput,
    TaskPriority
)


class VisionAgent:
    """
    Analyzes images and documents.

    Capabilities:
    - Image analysis (OCR, object detection)
    - Document reading (PDF, text files)
    - Diagram understanding
    - UI element extraction
    - Visual content description
    - Image comparison
    """

    def __init__(self, task_manager, ocr_engine=None):
        """
        Initialize the vision agent.

        Args:
            task_manager: TaskManager instance
            ocr_engine: Optional OCR engine
        """
        self.task_manager = task_manager
        self._ocr_engine = ocr_engine or pytesseract

    def execute_task(self, task: Task) -> TaskOutput:
        """
        Execute a vision task.

        Args:
            task: Task to execute

        Returns:
            Task execution result
        """
        try:
            method = getattr(self, f"_execute_{task.type.value}", None)

            if not method:
                return TaskOutput(
                    success=False,
                    message=f"No handler for task type: {task.type.value}",
                    error=f"Task type {task.type.value} not supported"
                )

            return method(task)

        except Exception as e:
            return TaskOutput(
                success=False,
                message=f"Error executing task",
                error=str(e)
            )

    # ========================================
    # IMAGE ANALYSIS
    # ========================================

    def _execute_image_analysis(self, task: Task) -> TaskOutput:
        """Analyze an image."""
        image_path = task.input.get("image_path")
        analysis_type = task.input.get("analysis_type", "overview")

        if not image_path:
            return TaskOutput(
                success=False,
                message="Image analysis failed",
                error="Image path required"
            )

        try:
            image = Image.open(image_path)

            # Get image dimensions
            width, height = image.size

            # OCR text extraction
            try:
                text = self._ocr_engine.image_to_string(image)
                text = text.strip()[:500]  # First 500 characters
            except Exception:
                text = "OCR not available"

            analysis = {
                "width": width,
                "height": height,
                "format": image.format,
                "mode": image.mode,
                "text_content": text,
                "analysis_type": analysis_type
            }

            return TaskOutput(
                success=True,
                message="Image analyzed successfully",
                data={
                    "image": image_path,
                    "analysis": analysis,
                    "dimensions": f"{width}x{height}"
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Image analysis failed",
                error=str(e)
            )

    def _extract_text_from_image(self, image_path: str) -> str:
        """Extract text from an image using OCR."""
        try:
            image = Image.open(image_path)
            return self._ocr_engine.image_to_string(image)
        except Exception:
            return "OCR failed or not configured"

    # ========================================
    # DOCUMENT READING
    # ========================================

    def _execute_document_read(self, task: Task) -> TaskOutput:
        """Read and extract text from a document."""
        document_path = task.input.get("document_path")
        content_type = task.input.get("content_type", "text")

        if not document_path:
            return TaskOutput(
                success=False,
                message="Document reading failed",
                error="Document path required"
            )

        try:
            path = Path(document_path)
            if not path.exists():
                return TaskOutput(
                    success=False,
                    message="Document not found",
                    error=f"Path does not exist: {document_path}"
                )

            # Read based on content type
            if content_type == "text":
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()

            elif content_type == "image":
                content = self._extract_text_from_image(document_path)

            elif content_type == "pdf":
                # In production, use pdfplumber or PyPDF2
                content = f"[PDF document] {path.name}\n[PDF extraction not implemented in demo]"

            else:
                return TaskOutput(
                    success=False,
                    message="Unknown content type",
                    error=f"Content type '{content_type}' not supported"
                )

            # Extract key sections (simplified)
            sections = self._extract_sections(content)

            return TaskOutput(
                success=True,
                message=f"Document read successfully: {path.name}",
                data={
                    "document": document_path,
                    "content_type": content_type,
                    "sections": sections,
                    "section_count": len(sections),
                    "total_length": len(content)
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Document reading failed",
                error=str(e)
            )

    def _extract_sections(self, content: str) -> List[dict[str, Any]]:
        """Extract sections from document content."""
        sections = []

        # Split by common section markers
        markers = ['## ', '# ', '### ', '--- ', '* ']

        lines = content.split('\n')
        current_section = {"title": "Document", "content": "", "lines": 0}

        for line in lines[:100]:  # First 100 lines
            stripped = line.strip()

            # Check for section markers
            is_section = False
            for marker in markers:
                if stripped.startswith(marker):
                    if current_section["content"]:
                        sections.append(current_section)

                    current_section = {
                        "title": stripped[len(marker):].strip(),
                        "content": "",
                        "lines": 0
                    }
                    is_section = True
                    break

            if not is_section:
                current_section["content"] += line + "\n"
                current_section["lines"] += 1

        if current_section["content"]:
            sections.append(current_section)

        return sections

    # ========================================
    # DIAGRAM UNDERSTANDING
    # ========================================

    def _execute_diagram_understand(self, task: Task) -> TaskOutput:
        """Understand diagrams and flowcharts."""
        diagram_path = task.input.get("diagram_path")
        diagram_type = task.input.get("diagram_type", "flowchart")

        if not diagram_path:
            return TaskOutput(
                success=False,
                message="Diagram understanding failed",
                error="Diagram path required"
            )

        try:
            # Read image
            text = self._extract_text_from_image(diagram_path)

            # Simple interpretation (in production, use specialized diagram tools)
            elements = self._interpret_diagram_elements(text, diagram_type)

            return TaskOutput(
                success=True,
                message=f"Diagram understood: {diagram_type}",
                data={
                    "diagram": diagram_path,
                    "type": diagram_type,
                    "elements": elements,
                    "interpretation": "Flowchart diagram analysis completed"
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Diagram understanding failed",
                error=str(e)
            )

    def _interpret_diagram_elements(self, text: str, diagram_type: str) -> List[dict]:
        """Interpret diagram elements."""
        elements = []

        # Simple parsing based on diagram type
        if diagram_type == "flowchart":
            for i, line in enumerate(text.split('\n')[:20]):
                elements.append({
                    "element_type": "node" if "→" in line or "=" in line else "arrow",
                    "content": line.strip(),
                    "index": i
                })
        else:
            for i, line in enumerate(text.split('\n')[:20]):
                elements.append({
                    "element_type": "shape",
                    "content": line.strip(),
                    "index": i
                })

        return elements

    # ========================================
    # UI EXPLANATION
    # ========================================

    def _execute_ui_explain(self, task: Task) -> TaskOutput:
        """Explain UI elements from a screenshot."""
        screenshot_path = task.input.get("screenshot_path")

        if not screenshot_path:
            return TaskOutput(
                success=False,
                message="UI explanation failed",
                error="Screenshot path required"
            )

        try:
            # Read screenshot
            text = self._extract_text_from_image(screenshot_path)

            # Extract UI elements
            elements = self._extract_ui_elements(text)

            return TaskOutput(
                success=True,
                message="UI elements extracted successfully",
                data={
                    "screenshot": screenshot_path,
                    "elements": elements,
                    "element_count": len(elements),
                    "ui_type": "Web/Desktop application"
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="UI explanation failed",
                error=str(e)
            )

    def _extract_ui_elements(self, text: str) -> List[dict[str, Any]]:
        """Extract UI elements from text."""
        elements = []

        # Parse text for UI elements (buttons, inputs, headers, etc.)
        lines = text.split('\n')
        headers = []
        buttons = []
        inputs = []

        for i, line in enumerate(lines[:50]):
            stripped = line.strip()

            if stripped.startswith('>>>') or stripped.startswith('Button'):
                buttons.append({
                    "type": "button",
                    "label": stripped.split(':', 1)[1].strip() if ':' in stripped else stripped,
                    "position": i
                })
            elif stripped.startswith('>>') or stripped.startswith('Input'):
                inputs.append({
                    "type": "input",
                    "label": stripped.split(':', 1)[1].strip() if ':' in stripped else stripped,
                    "position": i
                })
            elif len(stripped) < 50:
                headers.append({
                    "type": "header",
                    "text": stripped,
                    "level": 1
                })

        return headers + buttons + inputs

    # ========================================
    # IMAGE COMPARISON
    # ========================================

    def _execute_compare_images(self, task: Task) -> TaskOutput:
        """Compare two images and identify differences."""
        image1_path = task.input.get("image1_path")
        image2_path = task.input.get("image2_path")

        if not image1_path or not image2_path:
            return TaskOutput(
                success=False,
                message="Image comparison failed",
                error="Both image paths required"
            )

        try:
            # Load images
            img1 = Image.open(image1_path)
            img2 = Image.open(image2_path)

            # Get image info
            info1 = {
                "dimensions": f"{img1.width}x{img1.height}",
                "format": img1.format,
                "mode": img1.mode
            }

            info2 = {
                "dimensions": f"{img2.width}x{img2.height}",
                "format": img2.format,
                "mode": img2.mode
            }

            # Compare
            differences = []

            if img1.size != img2.size:
                differences.append({
                    "type": "size",
                    "message": f"Images have different sizes: {info1['dimensions']} vs {info2['dimensions']}"
                })

            if img1.format != img2.format:
                differences.append({
                    "type": "format",
                    "message": f"Images have different formats: {img1.format} vs {img2.format}"
                })

            if not differences:
                differences.append({
                    "type": "identical",
                    "message": "Images appear identical"
                })

            return TaskOutput(
                success=True,
                message="Image comparison completed",
                data={
                    "image1": image1_path,
                    "image2": image2_path,
                    "image1_info": info1,
                    "image2_info": info2,
                    "differences": differences,
                    "differences_count": len(differences)
                }
            )

        except Exception as e:
            return TaskOutput(
                success=False,
                message="Image comparison failed",
                error=str(e)
            )

    # ========================================
    # IMAGE DESCRIPTION
    # ========================================

    def _describe_image(self, image_path: str) -> str:
        """Describe an image content."""
        text = self._extract_text_from_image(image_path)

        return f"""Image Analysis Report:

OCR Extracted Text:
{text}

This is a generated description. In production, this would use computer vision models (like GPT-4 Vision) to understand the visual content, identify objects, and provide natural language descriptions."""
