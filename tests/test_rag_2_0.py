"""
Test Script for RAG 2.0 Knowledge Intelligence

This script tests:
- Parser registry and all 11 parsers
- Document parsing
- Metadata extraction
- Parser registration
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge.parsers import get_parser_registry



def test_parser_registry():
    """Test the parser registry and all parsers."""
    print("=" * 70)
    print("TESTING RAG 2.0 - PARSER REGISTRY")
    print("=" * 70)

    # Get the parser registry
    registry = get_parser_registry()

    print(f"\n✓ Parser Registry Initialized")
    print(f"✓ Total Parsers Registered: {len(registry._parsers)}")

    # List all registered parsers
    parsers = registry.list_parsers()
    print(f"\n✓ Registered Parsers:")
    for i, parser_name in enumerate(parsers, 1):
        print(f"  {i}. {parser_name}")

    # List supported extensions
    extensions = registry.list_supported_extensions()
    print(f"\n✓ Supported Extensions ({len(extensions)} total):")
    print(f"  {', '.join(sorted(extensions))}")

    return registry


def test_document_parsing(registry):
    """Test parsing sample documents."""
    print("\n" + "=" * 70)
    print("TESTING DOCUMENT PARSING")
    print("=" * 70)

    # Test files in the project
    test_files = [
        "README.md",
        "LICENSE",
        "main.py",
        "pyproject.toml",
        "requirements.txt",
    ]

    parsed_count = 0
    failed_count = 0

    for file_path in test_files:
        full_path = PROJECT_ROOT / file_path

        if not full_path.exists():
            print(f"\n⚠ File not found: {file_path}")
            continue

        print(f"\n{'─' * 70}")
        print(f"Parsing: {file_path}")
        print(f"{'─' * 70}")

        try:
            # Get appropriate parser
            parser_class = registry.get_parser(full_path)
            if parser_class:
                parser = parser_class()
                chunks = parser.parse(full_path) or []
                metadata = parser.extract_metadata(full_path)

                print(f"✓ Parser Found: {parser.__class__.__name__}")
                # Handle both dict and object return types
                if isinstance(metadata, dict):
                    print(f"✓ File Type: {metadata.get('file_type', 'unknown')}")
                    print(f"✓ Title: {metadata.get('title', 'N/A')}")
                else:
                    print(f"✓ File Type: {getattr(metadata, 'file_type', 'unknown')}")
                    print(f"✓ Title: {getattr(metadata, 'title', 'N/A')}")
                print(f"✓ Chunks Generated: {len(chunks)}")

                # Show first chunk details
                if chunks:
                    first_chunk = chunks[0]
                    print(f"\n  First Chunk:")
                    print(f"    - ID: {first_chunk.id}")
                    print(f"    - Content (preview): {first_chunk.content[:100]}...")
                    # Handle both dict and object for chunk metadata
                    chunk_metadata = getattr(first_chunk, 'metadata', first_chunk)
                    if isinstance(chunk_metadata, dict):
                        print(f"    - Chunk Type: {chunk_metadata.get('chunk_type', 'unknown')}")
                        print(f"    - Source: {chunk_metadata.get('source', 'unknown')}")
                    else:
                        print(f"    - Chunk Type: {getattr(chunk_metadata, 'chunk_type', 'unknown')}")
                        print(f"    - Source: {getattr(chunk_metadata, 'source', 'unknown')}")

                parsed_count += 1
            else:
                print(f"✗ No parser found for file type: {full_path.suffix}")
                failed_count += 1

        except Exception as e:
            print(f"✗ Error parsing {file_path}: {e}")
            failed_count += 1

    print(f"\n{'=' * 70}")
    print(f"Parsing Results: {parsed_count} successful, {failed_count} failed")
    print(f"{'=' * 70}")

    assert parsed_count > 0, "At least one file should parse successfully"

    return parsed_count, failed_count


def run_specific_file(file_path: str):
    """Test parsing a specific file."""
    print("\n" + "=" * 70)
    print(f"TESTING SPECIFIC FILE: {file_path}")
    print("=" * 70)

    full_path = PROJECT_ROOT / file_path

    if not full_path.exists():
        print(f"✗ File not found: {file_path}")
        assert False, f"File not found: {file_path}"

    try:
        registry = get_parser_registry()
        parser_class = registry.get_parser(full_path)

        if parser_class:
            parser = parser_class()
            chunks = parser.parse(full_path) or []
            metadata = parser.extract_metadata(full_path)

            print(f"\n✓ File: {file_path}")
            # Handle both dict and object return types
            if isinstance(metadata, dict):
                print(f"✓ File Type: {metadata.get('file_type', 'unknown')}")
                print(f"✓ Title: {metadata.get('title', 'N/A')}")
            else:
                print(f"✓ File Type: {getattr(metadata, 'file_type', 'unknown')}")
                print(f"✓ Title: {getattr(metadata, 'title', 'N/A')}")
                chunks = chunks or []

                print(f"✓ Total Chunks: {len(chunks)}")

            # Handle chunk_type for metadata
            if isinstance(metadata, dict):
                chunk_type = metadata.get('chunk_type')
            else:
                chunk_type = getattr(metadata, 'chunk_type', None)

            if chunk_type:
                print(f"✓ Chunk Type: {chunk_type}")

            # Handle line numbers for metadata
            if isinstance(metadata, dict):
                line_start = metadata.get('line_start')
                line_end = metadata.get('line_end')
            else:
                line_start = getattr(metadata, 'line_start', None)
                line_end = getattr(metadata, 'line_end', None)

            if line_start is not None and line_start >= 0:
                print(f"✓ Lines: {line_start} - {line_end}")

            print(f"\n{'─' * 70}")
            print("First 3 Chunks:")
            print(f"{'─' * 70}")

            for i, chunk in enumerate(chunks[:3], 1):
                print(f"\nChunk {i}:")
                print(f"  ID: {chunk.id}")
                print(f"  Content: {chunk.content[:150]}...")
                chunk_metadata = getattr(chunk, "metadata", None)

                if isinstance(chunk_metadata, dict):
                    print(f"  Type: {chunk_metadata.get('chunk_type', 'unknown')}")
                elif chunk_metadata is not None:
                    print(f"  Type: {getattr(chunk_metadata, 'chunk_type', 'unknown')}")
                else:
                    print("  Type: unknown")

        else:
            print(f"✗ No parser found for file type: {full_path.suffix}")
            assert False, f"No parser found for file type: {full_path.suffix}"

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"Error parsing {file_path}: {e}"


def main():
    """Main test function."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  RAG 2.0 KNOWLEDGE INTELLIGENCE - PARSER TEST".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        # Test 1: Parser Registry
        registry = test_parser_registry()

        # Test 2: Document Parsing
        parsed, failed = test_document_parsing(registry)

        # Test 3: Specific File Tests
        print("\n" + "=" * 70)
        print("TESTING SPECIFIC FILES")
        print("=" * 70)

        run_specific_file("README.md")
        run_specific_file("main.py")
        run_specific_file("pyproject.toml")

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"✓ Parser Registry: Complete")
        print(f"✓ Total Parsers: {len(registry._parsers)}")
        print(f"✓ Supported Extensions: {len(registry.list_supported_extensions())}")
        print(f"✓ Parsing Tests: {parsed} passed, {failed} failed")
        print("=" * 70)

        if failed == 0:
            print("\n🎉 ALL TESTS PASSED! RAG 2.0 is ready to use.")
            return 0
        else:
            print(f"\n⚠ {failed} test(s) failed. Please review the errors above.")
            return 1

    except Exception as e:
        print(f"\n✗ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
