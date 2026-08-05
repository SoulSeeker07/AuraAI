"""
Aura Plugin Manifest Generator

Tool for generating plugin manifest files programmatically.
"""

import json
from pathlib import Path
from typing import Any


class PluginManifestGenerator:
    """Generate plugin manifest files."""

    def __init__(self, name: str, category: str = "general"):
        """
        Initialize the manifest generator.

        Args:
            name: Plugin name
            category: Plugin category
        """
        self.name = name
        self.category = category
        self.version = "1.0.0"
        self.author = ""
        self.description = ""
        self.capabilities: list[str] = []
        self.permissions: list[str] = []
        self.dependencies: list[str] = []
        self.min_aura_version = "1.0.0"
        self.is_optional = False
        self.is_system = False

    def set_author(self, author: str) -> "PluginManifestGenerator":
        """Set plugin author."""
        self.author = author
        return self

    def set_description(self, description: str) -> "PluginManifestGenerator":
        """Set plugin description."""
        self.description = description
        return self

    def add_capability(self, capability: str) -> "PluginManifestGenerator":
        """Add a capability."""
        self.capabilities.append(capability)
        return self

    def add_capabilities(self, capabilities: list[str]) -> "PluginManifestGenerator":
        """Add multiple capabilities."""
        self.capabilities.extend(capabilities)
        return self

    def add_permission(self, permission: str) -> "PluginManifestGenerator":
        """Add a permission."""
        self.permissions.append(permission)
        return self

    def add_permissions(self, permissions: list[str]) -> "PluginManifestGenerator":
        """Add multiple permissions."""
        self.permissions.extend(permissions)
        return self

    def add_dependency(self, dependency: str) -> "PluginManifestGenerator":
        """Add a dependency."""
        self.dependencies.append(dependency)
        return self

    def set_min_aura_version(self, version: str) -> "PluginManifestGenerator":
        """Set minimum Aura version."""
        self.min_aura_version = version
        return self

    def set_version(self, version: str) -> "PluginManifestGenerator":
        """Set plugin version."""
        self.version = version
        return self

    def set_optional(self, optional: bool = True) -> "PluginManifestGenerator":
        """Set if plugin is optional."""
        self.is_optional = optional
        return self

    def generate(self) -> dict[str, Any]:
        """
        Generate the manifest dictionary.

        Returns:
            Manifest as dictionary
        """
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "min_aura_version": self.min_aura_version,
            "max_aura_version": "",
            "is_optional": self.is_optional,
            "is_system": self.is_system,
            "plugin_path": "",
            "entry_point": "Plugin",
        }

    def save(self, output_path: str = None) -> str:
        """
        Save manifest to file.

        Args:
            output_path: Path to save the manifest

        Returns:
            Path to the saved manifest
        """
        manifest = self.generate()
        json_content = json.dumps(manifest, indent=2)

        if not output_path:
            output_path = f"{self.name}_manifest.json"

        Path(output_path).write_text(json_content, encoding="utf-8")

        return output_path


def create_plugin_example() -> None:
    """Create an example plugin manifest."""
    generator = (
        PluginManifestGenerator(name="file_search", category="filesystem")
        .set_author("Your Name")
        .set_description("Search for files in the filesystem")
        .add_capabilities(["search", "filter", "export"])
        .add_permissions(["read_file", "list_directory"])
        .add_dependency("file_reader")
        .set_min_aura_version("1.0.0")
        .set_version("1.2.3")
    )

    print("Generated manifest:")
    print(json.dumps(generator.generate(), indent=2))
    print(f"\nSaved to: {generator.save()}")


if __name__ == "__main__":
    create_plugin_example()
