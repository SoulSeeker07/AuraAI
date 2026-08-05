"""
Aura Plugin CLI

Command-line tool for creating and managing Aura plugins.
Usage: aura-plugin-cli [command] [options]
"""

import sys
from pathlib import Path


class PluginCLIParser:
    """CLI parser for Aura plugin commands."""

    def __init__(self):
        self.plugins_dir = Path("plugins")

    def create_plugin(self, plugin_name: str, category: str = "general"):
        """
        Create a new plugin.

        Args:
            plugin_name: Name of the plugin
            category: Category of the plugin (desktop, filesystem, browser, etc.)
        """
        try:
            # Create plugin directory
            category_dir = self.plugins_dir / category
            category_dir.mkdir(parents=True, exist_ok=True)

            plugin_dir = category_dir / plugin_name
            plugin_dir.mkdir(exist_ok=True)

            # Create plugin template
            template_file = (
                Path(__file__).parent.parent.parent.parent / "plugins" / "template.py"
            )
            template_content = template_file.read_text(encoding="utf-8")

            # Create main plugin file
            plugin_file = plugin_dir / f"{plugin_name}.py"
            plugin_content = (
                template_content.replace(
                    "ExamplePlugin", f"{self._to_pascal_case(plugin_name)}Plugin"
                )
                .replace(
                    "Example Aura Plugin.",
                    f"{self._to_pascal_case(plugin_name)} Plugin.",
                )
                .replace(
                    "Replace this with your plugin's functionality.",
                    f"Replace this with {self._to_pascal_case(plugin_name)}'s functionality.",
                )
            )

            plugin_file.write_text(plugin_content, encoding="utf-8")

            # Create __init__.py
            init_file = plugin_dir / "__init__.py"
            init_content = f'"""{self._to_pascal_case(plugin_name)} Plugin"""'
            init_file.write_text(init_content, encoding="utf-8")

            # Create plugin manifest (inline metadata)
            manifest_file = plugin_dir / "_manifest.json"
            manifest_content = f"""{{
  "name": "{plugin_name}",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "Your plugin description",
  "category": "{category}",
  "capabilities": [
    "capability1",
    "capability2"
  ],
  "permissions": [
    "permission1"
  ],
  "dependencies": [],
  "min_aura_version": "1.0.0",
  "is_optional": false,
  "is_system": false
}}"""
            manifest_file.write_text(manifest_content, encoding="utf-8")

            # Create README
            readme_file = plugin_dir / "README.md"
            readme_content = f"""# {self._to_pascal_case(plugin_name)} Plugin

## Description
Your plugin description goes here.

## Capabilities
- `capability1` - Description of capability 1
- `capability2` - Description of capability 2

## Permissions
- `permission1` - Description of permission

## Installation
1. Place this plugin in the plugins/{category}/ directory
2. Restart Aura
3. Plugin will be auto-discovered

## Usage
```python
from execution import execute_capability

result = execute_capability(
    "capability1",
    parameter="value"
)
```

## Development
Edit the plugin file to implement your functionality.
"""

            readme_file.write_text(readme_content, encoding="utf-8")

            print(f"✓ Plugin '{plugin_name}' created successfully!")
            print(f"  Location: {plugin_dir}")
            print(f"  Category: {category}")
            print("\nNext steps:")
            print("  1. Edit the plugin file to implement your functionality")
            print("  2. Update the manifest with your capabilities and permissions")
            print("  3. Restart Aura to load the plugin")

        except Exception as e:
            print(f"✗ Failed to create plugin: {e}")
            sys.exit(1)

    def list_plugins(self):
        """List all available plugins."""
        try:
            if not self.plugins_dir.exists():
                print("No plugins directory found.")
                return

            categories = [
                "desktop",
                "filesystem",
                "browser",
                "terminal",
                "git",
                "networking",
                "vision",
                "voice",
                "office",
                "email",
                "calendar",
                "knowledge",
                "docker",
                "database",
                "mcp",
            ]

            for category in categories:
                category_dir = self.plugins_dir / category
                if category_dir.exists():
                    plugins = [
                        p.name
                        for p in category_dir.iterdir()
                        if p.is_dir() and not p.name.startswith("__")
                    ]
                    if plugins:
                        print(f"\n{category.upper()} Plugins:")
                        for plugin in plugins:
                            print(f"  - {plugin}")

        except Exception as e:
            print(f"✗ Failed to list plugins: {e}")

    def show_help(self):
        """Show help information."""
        print("""
Aura Plugin CLI

Usage: aura-plugin-cli <command> [options]

Commands:
  create-plugin <name> [category]  Create a new plugin
  list                             List all available plugins
  help                             Show this help message

Examples:
  aura-plugin-cli create-plugin myplugin desktop
  aura-plugin-cli create-plugin file-reader filesystem
  aura-plugin-cli list

Plugin Categories:
  desktop, filesystem, browser, terminal, git
  networking, vision, voice, office, email
  calendar, knowledge, docker, database, mcp
""")


def main():
    """Main entry point."""
    parser = PluginCLIParser()

    if len(sys.argv) < 2:
        parser.show_help()
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "create-plugin" and len(sys.argv) >= 3:
        plugin_name = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else "general"
        parser.create_plugin(plugin_name, category)

    elif command == "list":
        parser.list_plugins()

    elif command == "help" or command == "-h" or command == "--help":
        parser.show_help()

    else:
        print(f"Unknown command: {command}")
        parser.show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
