f = "src/desktop/native/desktop_execution_engine.py"
c = open(f, encoding="utf-8").read()

old = '            "read_clipboard": ["read clipboard", "get clipboard", "paste clipboard"],\n            "write_clipboard": ["write clipboard", "set clipboard", "copy to clipboard"],\n            "clear_clipboard": ["clear clipboard", "empty clipboard"],'

new = '            "clipboard.read_text": ["read clipboard", "get clipboard", "paste clipboard", "read copied text"],\n            "clipboard.write_text": ["write clipboard", "set clipboard", "copy to clipboard", "copy text"],\n            "clipboard.clear": ["clear clipboard", "empty clipboard"],\n            "clipboard.read_image": ["read clipboard image", "get clipboard image", "read screenshot"],\n            "clipboard.write_image": ["write clipboard image", "copy image to clipboard"],\n            "clipboard.read_files": ["read clipboard files", "get copied files"],\n            "clipboard.write_files": ["write clipboard files", "copy files to clipboard"],\n            "clipboard.read_html": ["read clipboard html", "get clipboard html"],\n            "clipboard.write_html": ["write clipboard html", "copy html to clipboard"],\n            "clipboard.get_formats": ["clipboard formats", "what is in clipboard", "list clipboard formats"],\n            "clipboard.has_text": ["clipboard has text", "does clipboard have text"],\n            "clipboard.has_image": ["clipboard has image", "does clipboard have image"],\n            "clipboard.has_files": ["clipboard has files", "does clipboard have files"],'

if old in c:
    c = c.replace(old, new)
    open(f, "w", encoding="utf-8").write(c)
    print("SUCCESS: Discovery keywords updated")
else:
    print("ERROR: Old keywords not found")
