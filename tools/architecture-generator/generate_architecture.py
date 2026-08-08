#!/usr/bin/env python
"""
Architecture Generator for AuraAI
===================================

A production-quality tool for generating system & cognitive architecture diagrams
from Python code. Scans all .py files, parses AST, detects 7 architectural layers,
classifies component roles, resolves dependencies, and generates multiple output
formats including PNG, SVG, PDF, DOT, Draw.io XML (.drawio), Mermaid (.mmd),
JSON (.json), and Markdown documentation (ARCHITECTURE.md).

Usage:
    python generate_architecture.py --root . --output docs/architecture
    python generate_architecture.py --root . --visuals
"""

import argparse
import sys
from pathlib import Path

# Add the tools directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from arch_analyzer import ArchitectureAnalyzer
from ast_parser import ASTParser
from graph_generator import GraphGenerator
from output_generators import OutputGenerator

from config import ArchitectureConfig


def print_banner():
    """Print the tool banner."""
    banner = """
+--------------------------------------------------------------------+
|                                                                    |
|     AURA AI ARCHITECTURE & COGNITIVE ANALYZER                      |
|     Production-Grade AST Systems Architecture Generator            |
|                                                                    |
|     v2.0.0                                                         |
|                                                                    |
+--------------------------------------------------------------------+
"""
    try:
        print(banner)
    except Exception:
        print("\n=== AURA ARCHITECTURE GENERATOR v2.0.0 ===\n")


def print_summary(analyzer, graph_generator):
    """Print a human-readable summary of the analysis."""
    print("\n" + "=" * 80)
    print("  SYSTEM ANALYSIS SUMMARY")
    print("=" * 80)

    stats = graph_generator.generate_statistics()

    print(f"\n  Total Modules Analyzed: {stats['total_modules']}")
    print(f"  Total Dependencies Mapped: {stats['total_dependencies']}")
    print(f"  Architecture Violations: {stats['total_violations']}")

    print("\n" + "-" * 80)
    print("  7-LAYER ARCHITECTURE BREAKDOWN")
    print("-" * 80)

    for layer_config in ArchitectureConfig.ALL_LAYERS:
        layer_name = layer_config.name
        layer_data = stats["layers"].get(layer_name, {})

        print(f"\n  {layer_config.icon} Layer {layer_config.level} — {layer_name}:")
        print(f"    Description: {layer_config.description}")
        print(f"    Modules: {layer_data.get('module_count', 0)}")
        print(f"    Classes: {layer_data.get('class_count', 0)}")
        print(f"    Functions: {layer_data.get('function_count', 0)}")
        print(f"    Complexity: {layer_data.get('complexity', 0)}")

    if stats["total_violations"] > 0:
        print("\n" + "-" * 80)
        print("  ARCHITECTURE VIOLATIONS DETECTED")
        print("-" * 80)
        for violation in analyzer.graph.violations[:10]:
            print("\n  [ERROR] Violation:")
            print(f"     {violation['from_module']} imports {violation['to_module']}")
            print(f"     {violation['from_layer']} -> {violation['to_layer']}")


def main():
    """Main execution function."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="Generate architecture diagrams and documentation for AuraAI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="docs/architecture",
        help="Output directory for generated files",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="dot,mermaid,drawio,json,markdown,report",
        help="Output formats to generate",
    )
    parser.add_argument(
        "--visuals",
        action="store_true",
        help="Generate visual diagrams (PNG, SVG, PDF) using Graphviz",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recursively scan subdirectories",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    root_path = Path(args.root).resolve()
    if not root_path.exists():
        print(f"Error: Root directory '{root_path}' does not exist.")
        sys.exit(1)

    print_banner()
    print(f"Scanning Workspace: {root_path}")
    print(f"Output Directory:   {args.output}")

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: AST Parse all Python files
        print("\n[1/5] Parsing Python source files via AST...")
        ast_parser = ASTParser(str(root_path))
        modules = ast_parser.parse_directory(root_path, recursive=not args.no_recursive)

        if not modules:
            print("  No Python files found. Exiting.")
            sys.exit(1)

        print(f"  [OK] Parsed {len(modules)} Python modules.")

        # Step 2: Analyze Architecture Layers & Component Roles
        print("\n[2/5] Analyzing 7 Architectural Layers & Component Roles...")
        analyzer = ArchitectureAnalyzer(ast_parser, str(root_path))
        analyzer.analyze()

        print(
            f"  [OK] Successfully categorized all {len(analyzer.graph.modules)} modules into 7 layers."
        )

        # Step 3: Generate System & Cognitive Graphs
        print("\n[3/5] Building Cognitive Flow & System Graph models...")
        graph_generator = GraphGenerator(analyzer.graph)

        # Step 4: Export Multi-Format Output Files
        print("\n[4/5] Exporting architecture artifacts...")
        output_generator = OutputGenerator(graph_generator)

        saved_files = output_generator.save_all_outputs(
            output_dir, include_visuals=args.visuals
        )

        # Also copy ARCHITECTURE.md to root directory for visibility if output is docs/architecture
        root_arch_md = root_path / "ARCHITECTURE.md"
        output_generator.generate_markdown_docs(root_arch_md)
        print(f"  [OK] Updated root documentation: {root_arch_md}")

        # Step 5: Visual rendering check
        if args.visuals:
            print("\n[5/5] Rendering visual diagrams (Graphviz)...")
            if saved_files["png"]:
                print(f"  [OK] Generated PNG: {saved_files['png']}")
            if saved_files["svg"]:
                print(f"  [OK] Generated SVG: {saved_files['svg']}")
            if saved_files["pdf"]:
                print(f"  [OK] Generated PDF: {saved_files['pdf']}")
        else:
            print(
                "\n[5/5] Skipping visual renders (use --visuals flag if Graphviz is installed)."
            )

        print_summary(analyzer, graph_generator)

        print("\n" + "=" * 80)
        print(f"  [OK] SUCCESS! All architecture artifacts generated in: {output_dir}")
        print("=" * 80)
        print("\n  Generated Files:")
        print(f"    - {output_dir / 'architecture.dot'} (Graphviz Source)")
        print(f"    - {output_dir / 'architecture.mmd'} (Module Mermaid Diagram)")
        print(
            f"    - {output_dir / 'architecture_flow.mmd'} (Cognitive Execution Flow Diagram)"
        )
        print(f"    - {output_dir / 'architecture.drawio'} (Native Draw.io XML Format)")
        print(
            f"    - {output_dir / 'architecture.json'} (Structured Machine JSON Data)"
        )
        print(
            f"    - {output_dir / 'ARCHITECTURE.md'} (System Architecture Documentation)"
        )
        print(
            f"    - {output_dir / 'architecture_report.txt'} (Human-Readable Analysis Report)"
        )
        print(f"    - {root_path / 'ARCHITECTURE.md'} (Root Documentation)")
        print("")

        return 0

    except KeyboardInterrupt:
        print("\n\n  [WARN] Interrupted by user.")
        return 130
    except Exception as e:
        print(f"\n\n  [ERROR] Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
