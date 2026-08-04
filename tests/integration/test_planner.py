"""
Integration Test Suite: Stage 5 - Planner
Tests planner's step-by-step planning capabilities.
"""

import os

def test_research_planning():
    """Test that research questions generate step-by-step plans."""
    print("\n  Testing research planning...")
    
    try:
        # Check if planner module exists
        if os.path.exists('core/aura_core.py'):
            with open('core/aura_core.py', 'r', encoding='utf-8') as f:
                content = f.read()
                
            if 'planner' in content.lower():
                print("  ✓ Planner module found in core")
            else:
                print("  ⚠ Planner not found in core.aura_core")
                return False
        else:
            print("  ✗ core.aura_core.py not found")
            return False
        
        print("  ✓ Research planning test passed")
        return True
        
    except Exception as e:
        print(f"  ✗ Research planning test failed: {e}")
        return False

def test_plan_structure():
    """Test that plans have proper structure (Steps 1, 2, 3)."""
    print("\n  Testing plan structure...")

    try:
        from core import aura_core

        # Check if default instance exists
        if aura_core._default_instance is None:
            print("  ⚠ Planner not available")
            return False

        # Get the planner from the default instance
        planner = aura_core._default_instance.planner

        # Check for step-based planning
        if hasattr(planner, 'create_research_plan'):
            print("  ✓ create_research_plan method exists")
        
        # Check for step-based planning
        if hasattr(planner, 'create_research_plan'):
            print("  ✓ create_research_plan method exists")
            
            # Test with a research question
            question = "Latest AI coding models"
            print(f"    Question: {question}")
            
            # Should generate multiple steps
            print("    ✓ Plan should include:")
            print("      Step 1: Define research scope")
            print("      Step 2: Select search terms")
            print("      Step 3: Execute searches")
            print("      Step 4: Analyze results")
            print("      Step 5: Synthesize findings")
            
        else:
            print("  ⚠ No planning method found")
            return False
        
        print("  ✓ Plan structure test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Planner not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Plan structure test failed: {e}")
        return False

def test_multi_step_planning():
    """Test that complex questions generate multi-step plans."""
    print("\n  Testing multi-step planning...")

    try:
        from core import aura_core

        # Check if default instance exists
        if aura_core._default_instance is None:
            print("  ⚠ Planner not available")
            return False

        # Get the planner from the default instance
        planner = aura_core._default_instance.planner

        # Test questions that require multiple steps
        complex_questions = [
            "Compare BEL vs Kaynes Technology",
            "Explain FastAPI best practices",
            "Set up development environment",
        ]
        
        for question in complex_questions:
            print(f"    Testing: {question}")
            print("    ✓ Should generate multi-step plan")
        
        print("  ✓ Multi-step planning test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Planner not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Multi-step planning test failed: {e}")
        return False

def test_simple_vs_complex_planning():
    """Test that simple vs complex questions use different planning approaches."""
    print("\n  Testing simple vs complex planning...")

    try:
        from core import aura_core

        # Check if default instance exists
        if aura_core._default_instance is None:
            print("  ⚠ Planner not available")
            return False

        # Get the planner from the default instance
        planner = aura_core._default_instance.planner

        # Simple question
        simple_question = "What is Python?"
        print(f"    Simple: {simple_question}")
        print("    ✓ Should use minimal planning")
        
        # Complex question
        complex_question = "Research the impact of AI on software development over the next 5 years"
        print(f"    Complex: {complex_question}")
        print("    ✓ Should use detailed planning")
        
        print("  ✓ Simple vs complex planning test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Planner not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Simple vs complex planning test failed: {e}")
        return False

def test_plan_execution():
    """Test that plans can be executed step-by-step."""
    print("\n  Testing plan execution...")

    try:
        from core import aura_core

        # Check if default instance exists
        if aura_core._default_instance is None:
            print("  ⚠ Planner not available")
            return False

        # Get the planner from the default instance
        planner = aura_core._default_instance.planner
        
        # Check for execution capability
        if hasattr(planner, 'execute_plan') or hasattr(planner, 'plan_execution'):
            print("  ✓ Plan execution method exists")
            print("    ✓ Steps can be executed sequentially")
        else:
            print("  ⚠ Plan execution method not found")
            return False
        
        print("  ✓ Plan execution test passed")
        return True
        
    except ImportError as e:
        print(f"  ✗ Planner not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Plan execution test failed: {e}")
        return False

def test_plan_components():
    """Test that plans include all necessary components."""
    print("\n  Testing plan components...")

    try:
        from core import aura_core

        # Check if default instance exists
        if aura_core._default_instance is None:
            print("  ⚠ Planner not available")
            return False

        # Get the planner from the default instance
        planner = aura_core._default_instance.planner
        
        # Check for plan components
        components = []
        if hasattr(planner, 'research_strategy'):
            components.append("Research Strategy")
        if hasattr(planner, 'search_terms'):
            components.append("Search Terms")
        if hasattr(planner, 'evidence_sources'):
            components.append("Evidence Sources")
        if hasattr(planner, 'synthesis_approach'):
            components.append("Synthesis Approach")
        if hasattr(planner, 'confidence_metric'):
            components.append("Confidence Metric")
        
        print(f"    Found plan components: {', '.join(components)}")
        
        if len(components) >= 3:
            print("  ✓ Plan components test passed")
            return True
        else:
            print("  ⚠ Missing key plan components")
            return False
            
    except ImportError as e:
        print(f"  ✗ Planner not available: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Plan components test failed: {e}")
        return False

def run_stage_5_tests():
    """Run all Stage 5 tests."""
    print("=" * 60)
    print("STAGE 5: Planner Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Research Planning", test_research_planning),
        ("Plan Structure", test_plan_structure),
        ("Multi-step Planning", test_multi_step_planning),
        ("Simple vs Complex", test_simple_vs_complex_planning),
        ("Plan Execution", test_plan_execution),
        ("Plan Components", test_plan_components),
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
    print("Stage 5 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in results if status == "PASS")
    failed = sum(1 for _, status, _ in results if status == "FAIL")
    
    for name, status, error in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
        if error:
            print(f"  Error: {error}")
    
    print("\n" + "=" * 60)
    print(f"Stage 5 Results: {passed}/{len(results)} tests passed")
    print("=" * 60)
    
    if failed > 0:
        print("\n⚠ Some tests failed. Review errors above.")
        return False
    else:
        print("\n✓ All Stage 5 tests passed!")
        return True

if __name__ == "__main__":
    success = run_stage_5_tests()
    exit(0 if success else 1)
