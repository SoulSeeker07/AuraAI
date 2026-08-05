"""Script to update clipboard capabilities in the registry."""
import re

filepath = 'src/desktop/native/capability_registry.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the old clipboard section
old_start = '    def _register_clipboard_capabilities(self) -> None:\n        """Register clipboard capabilities"""'
old_end = '            usage_examples=["Clear clipboard", "Remove clipboard content"],\n        ))'

# Find positions
start_idx = content.find(old_start)
if start_idx == -1:
    print("ERROR: Could not find start of clipboard section")
    exit(1)

end_idx = content.find(old_end, start_idx)
if end_idx == -1:
    print("ERROR: Could not find end of clipboard section")
    exit(1)

end_idx += len(old_end)

new_section = '''    def _register_clipboard_capabilities(self) -> None:
        """Register clipboard capabilities (full clipboard surface)"""
        # Text operations
        self.register(CapabilityDescriptor(
            name="clipboard.read_text",
            description="Read plain text from the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Get clipboard text", "Read copied text", "Paste clipboard"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.write_text",
            description="Write plain text to the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Copy text to clipboard", "Set clipboard content"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.clear",
            description="Clear the clipboard contents",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Clear clipboard", "Empty clipboard"],
        ))

        # Image operations
        self.register(CapabilityDescriptor(
            name="clipboard.read_image",
            description="Read image from the clipboard (Windows bitmap)",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Get clipboard image", "Read screenshot"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.write_image",
            description="Write image to the clipboard (Windows bitmap)",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Copy image to clipboard", "Set clipboard image"],
        ))

        # File operations
        self.register(CapabilityDescriptor(
            name="clipboard.read_files",
            description="Read file paths from the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Get copied files", "Read file paths from clipboard"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.write_files",
            description="Write file paths to the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Copy files to clipboard", "Set clipboard files"],
        ))

        # HTML operations
        self.register(CapabilityDescriptor(
            name="clipboard.read_html",
            description="Read HTML content from the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Get clipboard HTML", "Read formatted content"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.write_html",
            description="Write HTML content to the clipboard",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.WRITE,
            permission_label="Write",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            events_triggered=["clipboard_changed"],
            usage_examples=["Copy HTML to clipboard", "Set clipboard HTML"],
        ))

        # Format queries
        self.register(CapabilityDescriptor(
            name="clipboard.get_formats",
            description="Get list of available clipboard formats",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["List clipboard formats", "What's in the clipboard"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.has_text",
            description="Check if clipboard contains text",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Does clipboard have text?", "Check clipboard content"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.has_image",
            description="Check if clipboard contains an image",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Does clipboard have an image?", "Check clipboard for image"],
        ))

        self.register(CapabilityDescriptor(
            name="clipboard.has_files",
            description="Check if clipboard contains files",
            manager="clipboard",
            category="clipboard",
            permission=PermissionRequired.READ,
            permission_label="Read",
            risk_level=RiskLevel.SAFE,
            supports_undo=False,
            usage_examples=["Does clipboard have files?", "Check clipboard for files"],
        ))'''

content = content[:start_idx] + new_section + content[end_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: Clipboard capabilities updated")