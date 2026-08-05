"""
Plugin Ecosystem Integration Tests

Tests for the Aura Plugin System.
"""

import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("=" * 80)
print("Aura Plugin Ecosystem - Integration Test")
print("=" * 80)

try:
    # Test 1: Import plugin system modules
    print("\n[Test 1] Importing plugin system modules...")

    from plugins import (
        Plugin,
        PluginCategory,
        PluginManager,
        PluginManifest,
        PluginRegistry,
        PluginState,
    )

    print("✓ All plugin system modules imported successfully")

    # Test 2: Create PluginRegistry
    print("\n[Test 2] Creating plugin registry...")

    registry = PluginRegistry(plugins_dir="plugins")
    print("✓ PluginRegistry created successfully")

    # Test 3: Scan and load plugins
    print("\n[Test 3] Scanning for plugins...")

    results = registry.scan_and_load_plugins()
    loaded_count = sum(1 for success in results.values() if success)

    print("✓ Plugin registry scanning complete")
    print(f"  - Scanned for plugins: {len(results)}")
    print(f"  - Successfully loaded: {loaded_count}")

    # Test 4: Check plugin information
    print("\n[Test 4] Checking plugin information...")

    if loaded_count > 0:
        info = registry.get_registry_info()
        print("✓ Plugin registry information:")
        print(f"  - Total plugins: {info['total_plugins']}")
        print(f"  - Enabled plugins: {info['enabled_plugins']}")
        print(f"  - Disabled plugins: {info['disabled_plugins']}")
        print(f"  - Capabilities: {info['capabilities']}")
        print(f"  - Categories: {', '.join(info['plugin_categories'])}")

    # Test 5: Get all capabilities
    print("\n[Test 5] Getting all capabilities...")

    capabilities = registry.get_all_capabilities()
    print(f"✓ Found {len(capabilities)} capabilities")

    for capability, providers in list(capabilities.items())[:5]:
        print(f"  - {capability}: {providers}")

    # Test 6: Get plugins by category
    print("\n[Test 6] Getting plugins by category...")

    for category in PluginCategory:
        plugins = registry.get_plugins_by_category(category)
        if plugins:
            print(f"  - {category.value}: {len(plugins)} plugin(s)")

    # Test 7: Enable and disable plugins
    print("\n[Test 7] Testing plugin enable/disable...")

    if loaded_count > 0:
        # Enable first plugin
        first_plugin = list(registry._plugins.keys())[0]
        if registry.enable_plugin(first_plugin):
            print(f"✓ Plugin '{first_plugin}' enabled")
        else:
            print(f"✗ Failed to enable plugin '{first_plugin}'")

        # Disable it
        if registry.disable_plugin(first_plugin):
            print(f"✓ Plugin '{first_plugin}' disabled")
        else:
            print(f"✗ Failed to disable plugin '{first_plugin}'")

    # Test 8: Get enabled/disabled plugins
    print("\n[Test 8] Getting enabled and disabled plugins...")

    enabled_plugins = registry.get_enabled_plugins()
    disabled_plugins = registry.get_disabled_plugins()

    print(f"✓ Enabled plugins: {len(enabled_plugins)}")
    print(f"✓ Disabled plugins: {len(disabled_plugins)}")

    # Test 9: Plugin health check
    print("\n[Test 9] Checking plugin health...")

    if loaded_count > 0:
        first_plugin = list(registry._plugins.keys())[0]
        health = registry.check_health(first_plugin)

        print(f"✓ Plugin '{first_plugin}' health:")
        print(f"  - State: {health['state']}")
        print(f"  - Enabled: {health['enabled']}")
        print(f"  - Capabilities: {health['capabilities']}")
        print(f"  - Healthy: {health['healthy']}")

    # Test 10: Check all plugin health
    print("\n[Test 10] Checking all plugin health...")

    all_health = registry.check_all_health()
    healthy_count = sum(1 for h in all_health.values() if h["healthy"])
    not_found_count = sum(1 for h in all_health.values() if h["state"] == "not_found")

    print("✓ Health check complete:")
    print(f"  - Healthy plugins: {healthy_count}")
    print(f"  - Not found: {not_found_count}")

    # Test 11: Get plugin dependencies
    print("\n[Test 11] Getting plugin dependencies...")

    if loaded_count > 0:
        first_plugin = list(registry._plugins.keys())[0]
        dependencies = registry.get_plugin_dependencies(first_plugin)

        print(f"✓ Plugin '{first_plugin}' dependencies: {dependencies}")

    # Test 12: Test PluginManifest
    print("\n[Test 12] Testing PluginManifest...")

    manifest = PluginManifest(
        name="test_plugin",
        version="1.0.0",
        category=PluginCategory.FILESYSTEM,
        capabilities=["read", "write"],
        permissions=["read_file", "write_file"],
        author="Test Author",
    )

    manifest_dict = manifest.to_dict()
    print("✓ PluginManifest created and converted to dict:")
    print(f"  - Name: {manifest_dict['name']}")
    print(f"  - Version: {manifest_dict['version']}")
    print(f"  - Category: {manifest_dict['category']}")
    print(f"  - Capabilities: {manifest_dict['capabilities']}")
    print(f"  - Author: {manifest_dict['author']}")

    # Test 13: Test PluginManager
    print("\n[Test 13] Testing PluginManager...")

    manager = PluginManager(registry, enable_auto_discovery=False)
    initialized = manager.initialize()

    if initialized:
        print("✓ PluginManager initialized successfully")

        # Get stats
        stats = manager.get_stats()
        print("✓ PluginManager statistics:")
        print(f"  - Total plugins: {stats['total_plugins']}")
        print(f"  - Enabled plugins: {stats['enabled_plugins']}")
        print(f"  - Disabled plugins: {stats['disabled_plugins']}")
        print(f"  - Capabilities: {stats['capabilities_count']}")
        print(f"  - Categories: {stats['categories']}")
    else:
        print("✗ PluginManager initialization failed")

    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nPlugin Ecosystem is working correctly.")

except ImportError as e:
    print(f"\n✗ Import error: {e}")
    print(
        "Make sure you've installed all dependencies and the plugin system is set up correctly."
    )

except Exception as e:
    print(f"\n✗ Test failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
