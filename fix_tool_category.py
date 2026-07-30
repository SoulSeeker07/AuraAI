"""Fix ToolCategory.UTILITY to ToolCategory.GENERAL"""

# Read the file
with open('src/execution/tool_adapter.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all occurrences
content = content.replace('ToolCategory.UTILITY', 'ToolCategory.GENERAL')

# Write the file back
with open('src/execution/tool_adapter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed ToolCategory.UTILITY to ToolCategory.GENERAL")
