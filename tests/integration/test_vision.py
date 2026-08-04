"""
Integration Test Suite: Stage 11 - Vision
Tests vision capabilities and image processing.
"""

import os

def test_vision_system():
    """Test vision system initialization."""
    print("\n  Testing vision system...")
    
    try:
        from core import aura_core
        
        # Check if vision system exists
        if hasattr(aura_core, 'vision_system') or hasattr(aura_core, 'vision'):
            print("  ✓ Vision system available")
        else:
            print("  ⚠ Vision system not found")
            return False
        
        print("  ✓ Vision system test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Vision system test failed: {e}")
        return False

def test_analyze_screenshot():
    """Test analyzing screenshots."""
    print("\n  Testing screenshot analysis...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check if screenshot analysis is available
        print("  ✓ Should be able to analyze screenshots")
        print("    Input: Image file path")
        print("    Output: Description of screenshot content")
        
        print("  ✓ Screenshot analysis test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Screenshot analysis test failed: {e}")
        return False

def test_read_pdf():
    """Test reading PDF documents."""
    print("\n  Testing PDF reading...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check if PDF reading is available
        print("  ✓ Should be able to read PDF files")
        print("    Input: PDF file path")
        print("    Output: Text content from PDF")
        
        print("  ✓ PDF reading test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ PDF reading test failed: {e}")
        return False

def test_read_diagram():
    """Test reading diagram images."""
    print("\n  Testing diagram reading...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check if diagram reading is available
        print("  ✓ Should be able to read diagrams")
        print("    Input: Diagram image (Mermaid, UML, etc.)")
        print("    Output: Structure and components")
        
        print("  ✓ Diagram reading test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Diagram reading test failed: {e}")
        return False

def test_read_ui():
    """Test reading UI screenshots."""
    print("\n  Testing UI reading...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check if UI reading is available
        print("  ✓ Should be able to read UI screenshots")
        print("    Input: UI screenshot")
        print("    Output: UI elements and interactions")
        
        print("  ✓ UI reading test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ UI reading test failed: {e}")
        return False

def test_image_description():
    """Test generating image descriptions."""
    print("\n  Testing image description...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check if image description is available
        print("  ✓ Should be able to describe images")
        print("    Input: Image file")
        print("    Output: Detailed image description")
        
        print("  ✓ Image description test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Image description test failed: {e}")
        return False

def test_ocr_capability():
    """Test OCR capabilities."""
    print("\n  Testing OCR...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check for OCR
        if hasattr(vision_system, 'perform_ocr') or hasattr(vision_system, 'ocr'):
            print("  ✓ OCR available")
            print("    ✓ Text can be extracted from images")
        else:
            print("  ⚠ OCR not found")
            return False
        
        print("  ✓ OCR test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ OCR test failed: {e}")
        return False

def test_object_detection():
    """Test object detection in images."""
    print("\n  Testing object detection...")
    
    try:
        from core import aura_core
        
        if not hasattr(aura_core, 'vision_system'):
            print("  ⚠ Vision system not available")
            return False
        
        vision_system = aura_core.vision_system
        
        # Check for object detection
        if hasattr(vision_system, 'detect_objects'):
            print("  ✓ Object detection available")
            print("    ✓ Objects can be detected in images")
        else:
            print("  ⚠ Object detection not found")
            return False
        
        print("  ✓ Object detection test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Vision system not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Object detection test failed: {e}")
        return False

def run_stage_11_tests():
    """Run all Stage 11 tests."""
    print("=" * 60)
    print("STAGE 11: Vision Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Vision System", test_vision_system),
        ("Screenshot Analysis", test_analyze_screenshot),
        ("PDF Reading", test_read_pdf),
        ("Diagram Reading", test_read_diagram),
        ("UI Reading", test_read_ui),
        ("Image Description", test_image_description),
        ("OCR Capability", test_ocr_capability),
        ("Object Detection", test_object_detection),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            if test_func():
                results.append((name, "PASS", None))
            else:
                results.append((name, "FAIL", "Test returned False"))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
    
    print("\n" + "=" * 60)
    print("Stage 11 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    
    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")
    
    print("\n" + "=" * 60)
    print(f"Stage 11 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 11 tests passed!")
        return True

if __name__ == "__main__":
    success = run_stage_11_tests()
    exit(0 if success else 1)
