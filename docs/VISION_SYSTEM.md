# Vision System Documentation

## Overview

The Vision System provides Aura with "eyes" - the ability to see and understand what's happening on the user's desktop. It captures screenshots, analyzes images using computer vision techniques, and extracts structured information about visual elements.

## Architecture

```
Vision System Pipeline
┌─────────────────────────────────────────────────────────────┐
│  Vision Plugin                                                │
│  - Plugin Interface                                          │
│  - Configuration Management                                  │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│  Vision Manager                                             │
│  - Orchestration                                            │
│  - Pipeline Coordination                                    │
│  - Feature Management                                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────┼─────────────────────────────────────────┐
│                                                               │
┌───────────────────▼────┐  ┌─────────────────────────────┐  │
│  Screenshot Manager    │  │  Image Loader               │  │
│  - Capture methods     │  │  - Load images               │  │
│  - Format handling     │  │  - Type detection            │  │
│  - Region selection    │  │  - Validation                │  │
└───────────────────────┘  └─────────────────────────────┘  │
┌───────────────────▼────┐  ┌─────────────────────────────┐  │
│  Image Preprocessor    │  │  OCR Engine                 │  │
│  - Rotation detection  │  │  - Text extraction          │  │
│  - Deskewing           │  │  - Table detection          │  │
│  - Enhancement         │  │  - Language support          │  │
└───────────────────┬────┘  └─────────────────────────────┘  │
                    │                                       │
┌───────────────────▼─────────────────────────────────────────┐
│  Analyzers (5 specialized analyzers)                         │
│                                                               │
│  1. Object Detector           - Buttons, menus, dialogs     │
│  2. Layout Analyzer           - Title bars, sections, cols  │
│  3. UI Analyzer               - Inputs, checkboxes, forms    │
│  4. Diagram Analyzer          - Nodes, connections          │
│  5. Code Detector             - Code language, snippets     │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│  Vision Context Coordinator                                   │
│  - Context Creation                                          │
│  - Analysis Updates                                          │
│  - Finalization                                              │
│  - LLM Integration Decision                                  │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│  Vision Context                                              │
│  - Structured Analysis Results                               │
│  - Extracted Elements                                        │
│  - Metadata                                                  │
└─────────────────────────────────────────────────────────────┘
```

## Features

### 1. Screenshot Capture

Multiple capture methods:
- **Full Screen** - Capture entire monitor
- **Active Monitor** - Capture specific monitor
- **Active Window** - Capture focused window
- **Selected Region** - Capture custom region
- **Window by Title** - Capture specific window
- **Menu Capture** - Capture menu bar

### 2. Image Understanding

#### Object Detection
- **Buttons** - Interactive rectangular elements
- **Menus** - Menu bars and dropdowns
- **Dialogs** - Modal and popup dialogs
- **Paragraphs** - Text blocks
- **Table Regions** - Tabular data

#### Layout Analysis
- **Title Bar** - Window title area
- **Menu Bar** - Menu navigation
- **Content Area** - Main content region
- **Footer** - Bottom section
- **Scrollbars** - Scrolling elements
- **Sidebar** - Side navigation
- **Margins** - Document margins
- **Columns** - Multi-column layouts
- **Sections** - Document sections
- **Elements** - Generic layout elements

#### UI Analysis
- **Buttons** - Clickable elements
- **Menus** - Menu items
- **Dialogs** - Modal windows
- **Forms** - Input forms
- **Notifications** - Toasts and alerts
- **Tooltips** - Context hints
- **Input Fields** - Text inputs
- **Checkboxes** - Selection boxes
- **Radio Buttons** - Radio selection
- **Dropdowns** - Selection menus

#### Diagram Analysis
- **Flowcharts** - Process diagrams
- **Network Diagrams** - Network topology
- **Circuit Diagrams** - Circuit components
- **Nodes** - Diagram elements
- **Connections** - Links between elements
- **Sections** - Diagram sections

#### Code Detection
- **Language Detection** - Programming language identification
- **Code Lines** - Individual lines of code
- **Code Snippets** - Code blocks
- **Syntax Highlighting** - Pattern detection

## Installation

### Requirements

```bash
pip install opencv-python
pip install numpy
pip install Pillow
```

Or from requirements.txt:

```bash
pip install -r requirements.txt
```

### Python Requirements

- Python 3.10+
- OpenCV 4.5+
- NumPy 1.20+
- Pillow 8.0+

## Quick Start

### Basic Usage

```python
from src.vision.vision_manager import VisionManager

# Initialize Vision Manager
vision_manager = VisionManager()

# Capture and analyze screenshot
context = vision_manager.capture_and_analyze()

# Get results
print(f"Image type: {context.image_type}")
print(f"Objects detected: {len(context.objects)}")
print(f"Buttons: {len(context.buttons)}")
print(f"Menus: {len(context.menus)}")
```

### Analyze Existing Image

```python
from src.vision.vision_manager import VisionManager
from src.vision.models import ImageType

# Initialize
vision_manager = VisionManager()

# Analyze image file
context = vision_manager.analyze_image(
    "screenshot.png",
    ImageType.SCREENSHOT
)

# Access results
print(f"Summary: {context.summary}")
print(f"Layout: {context.layout}")
```

### Using Vision Plugin

```python
from src.vision.vision_plugin import VisionPlugin

# Initialize plugin
plugin = VisionPlugin()

# Load plugin
plugin.load(config={
    'enabled': True,
    'features': {
        'object_detection': True,
        'ui_analysis': True
    }
})

# Use vision capabilities
result = plugin.capture_and_analyze()
print(f"Analysis complete: {result}")
```

## Configuration

### Screenshot Settings

```python
from src.vision.models import ScreenshotSettings

settings = ScreenshotSettings(
    capture_type='active_window',  # full_screen, active_monitor, active_window, selected_region
    monitor_index=0,
    selected_region=(100, 100, 500, 500),
    format='png',  # png, jpg, bmp
    quality=95,
    include_cursor=True,
    include_timestamp=False,
    save_path='output/screenshots'
)
```

### OCR Settings

```python
from src.vision.models import OCRSettings, VisionProvider

settings = OCRSettings(
    provider=VisionProvider.OPENAI,  # local_ocr, openai, gemini
    language='eng',  # eng, spa, fra, etc.
    table_detection=True,
    code_detection=True,
    diagram_detection=True,
    auto_rotate=True,
    deskew=True,
    confidence_threshold=0.8
)
```

### Feature Configuration

```python
vision_manager = VisionManager()

# Enable/disable features
vision_manager.enable_feature('auto_rotate', enabled=True)
vision_manager.enable_feature('deskew', enabled=True)
vision_manager.enable_feature('table_detection', enabled=False)

# Configure screenshot settings
vision_manager.configure_screenshot(
    capture_type='active_window',
    include_cursor=True
)

# Configure OCR settings
vision_manager.configure_ocr(
    provider=VisionProvider.OPENAI,
    language='eng',
    confidence_threshold=0.8
)
```

## Vision Context

The VisionContext contains structured analysis results:

```python
from src.vision.models import VisionContext

# Access all fields
context = VisionContext(
    image_path="screenshot.png",
    image_type=ImageType.SCREENSHOT,
    image_width=1920,
    image_height=1080
)

# Fields include:
context.image_path          # Path to analyzed image
context.image_type          # Type of image
context.image_width         # Width in pixels
context.image_height        # Height in pixels
context.detected_text       # Extracted text (if OCR used)
context.objects             # Detected objects
context.bounding_boxes      # Object positions
context.layout              # Layout information
context.elements            # Layout elements
context.sections            # Document sections
context.tables              # Table regions
context.code_snippets       # Code blocks
context.buttons             # Button elements
context.menus               # Menu elements
context.dialogs             # Dialog elements
context.forms               # Form elements
context.notifications       # Notification elements
context.network_devices     # Network devices (diagrams)
context.ip_addresses        # IP addresses (network diagrams)
context.vlan_ids            # VLAN IDs (network diagrams)
context.errors_detected     # Detection errors
context.metadata            # Processing metadata
```

## Components

### 1. VisionManager

Main orchestrator for the Vision System.

**Methods:**
- `capture_and_analyze()` - Capture and analyze screenshot
- `capture_active_window_and_analyze()` - Capture active window
- `analyze_image()` - Analyze existing image
- `get_last_context()` - Get last processed context
- `get_last_image_path()` - Get last image path
- `get_context_info()` - Get context information
- `configure_screenshot()` - Configure screenshot settings
- `configure_ocr()` - Configure OCR settings
- `enable_feature()` - Enable/disable features

### 2. ScreenshotManager

Handles various screenshot capture types.

**Methods:**
- `capture_full_screen()` - Capture entire screen
- `capture_active_monitor()` - Capture specific monitor
- `capture_active_window()` - Capture focused window
- `capture_selected_region()` - Capture custom region
- `capture_window_by_title()` - Capture window by title
- `capture_menu()` - Capture menu bar
- `capture_dialog()` - Capture dialog

### 3. ObjectDetector

Detects objects in images.

**Features:**
- Button detection
- Menu detection
- Dialog detection
- Paragraph detection
- Table region detection

### 4. LayoutAnalyzer

Analyzes layout structures.

**Features:**
- UI layout detection
- Document layout detection
- Diagram layout detection
- Generic layout detection
- Section identification

### 5. UIAnalyzer

Specialized UI element analysis.

**Features:**
- Button detection
- Menu detection
- Dialog detection
- Form detection
- Notification detection
- Tooltip detection
- Input field detection
- Checkbox detection
- Radio button detection
- Dropdown detection

### 6. DiagramAnalyzer

Specialized diagram analysis.

**Features:**
- Flowchart analysis
- Network diagram analysis
- Circuit diagram analysis
- Generic diagram analysis
- Node detection
- Connection detection
- Section identification

### 7. CodeDetector

Detects and analyzes code.

**Features:**
- Language detection
- Code line detection
- Code snippet extraction
- Syntax highlighting detection
- Complexity calculation

## Image Types

```python
from src.vision.models import ImageType

ImageType.SCREENSHOT      # Screenshot images
ImageType.DOCUMENT        # Document images
ImageType.DIAGRAM         # Diagram images
ImageType.CODE            # Code screenshots
ImageType.UI              # UI screenshots
ImageType.NETWORK         # Network diagrams
ImageType.WHITEBOARD      # Whiteboard images
ImageType.PHOTO           # Photographs
ImageType.UNKNOWN         # Unknown type
```

## Vision Provider

```python
from src.vision.models import VisionProvider

VisionProvider.LOCAL_OCR  # Local OCR engine
VisionProvider.OPENAI     # OpenAI OCR
VisionProvider.GEMINI     # Gemini OCR
VisionProvider.FUTURE     # Future OCR providers
```

## Testing

Run the test suite:

```bash
pytest tests/test_vision_system.py -v
```

## Examples

### Example 1: Analyze Desktop Screenshot

```python
from src.vision.vision_manager import VisionManager

# Initialize
vision = VisionManager()

# Analyze current screen
context = vision.capture_and_analyze()

# Print summary
print(f"Screen analyzed: {context.image_width}x{context.image_height}")
print(f"Buttons found: {len(context.buttons)}")
print(f"Menus found: {len(context.menus)}")
print(f"Dialogs found: {len(context.dialogs)}")
```

### Example 2: Analyze Specific Window

```python
from src.vision.vision_manager import VisionManager
from src.vision.models import ImageType

vision = VisionManager()

# Analyze specific window by title
context = vision.capture_active_window_and_analyze(window_title="Chrome")

# Focus on UI elements
print(f"UI Analysis: {context.ui_analysis}")
print(f"Forms detected: {len(context.forms)}")
print(f"Inputs found: {len(context.input_fields)}")
```

### Example 3: Analyze Document

```python
from src.vision.vision_manager import VisionManager

vision = VisionManager()

# Analyze document
context = vision.analyze_image("document.png", ImageType.DOCUMENT)

# Extract structure
print(f"Layout: {context.layout}")
print(f"Sections: {context.sections}")
print(f"Columns: {context.columns}")
print(f"Table regions: {len(context.table_regions)}")
```

### Example 4: Analyze Code

```python
from src.vision.vision_manager import VisionManager

vision = VisionManager()

# Analyze code screenshot
context = vision.analyze_image("code.png", ImageType.CODE)

# Get code information
print(f"Detected language: {context.code_language}")
print(f"Code lines: {len(context.code_lines)}")
print(f"Snippets: {len(context.code_snippets)}")
print(f"Has syntax highlighting: {context.syntax_highlighting}")
```

### Example 5: Network Diagram Analysis

```python
from src.vision.vision_manager import VisionManager

vision = VisionManager()

# Analyze network diagram
context = vision.analyze_image("network.png", ImageType.NETWORK)

# Extract network info
print(f"Devices: {len(context.network_devices)}")
print(f"Nodes: {len(context.nodes)}")
print(f"Connections: {len(context.connections)}")
print(f"IP addresses: {context.ip_addresses}")
print(f"VLANs: {context.vlan_ids}")
```

## Limitations

1. **OCR**: OCR engine not yet implemented (local OCR configured but not used)
2. **Precision**: Object detection relies on heuristics and may not be 100% accurate
3. **Complex UI**: Very complex UI may require manual tuning of detection thresholds
4. **Real-time**: Not optimized for real-time processing (sub-second latency)
5. **Multi-language**: Primary language support for English, other languages may have lower accuracy

## Future Enhancements

1. **Advanced OCR**: Integrate Tesseract or cloud OCR services
2. **Object Detection ML**: Use ML-based object detection for better accuracy
3. **OCR Table Detection**: Advanced table structure recognition
4. **Performance Optimization**: Optimize for real-time usage
5. **More Image Types**: Support for video frames, animations
6. **Pattern Recognition**: Learn from user interactions to improve detection

## Troubleshooting

### Issue: No objects detected

**Solution**: Check image preprocessing settings and adjust thresholds in analyzer modules.

### Issue: Poor layout detection

**Solution**: Ensure image is properly rotated and deskewed. Use OCR settings to enable auto_rotate and deskew.

### Issue: Memory issues with large images

**Solution**: Process images at reasonable sizes or use region-based analysis.

## License

See LICENSE file for details.

## Contributing

Contributions welcome! Please read the contributing guidelines.

## Support

For issues and questions, please open an issue on GitHub.
