import sys
from PySide6.QtCore import Qt, QBuffer, QByteArray
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtGui import QFont
from PIL import Image
from io import BytesIO
from playwright.sync_api import sync_playwright
import numpy as np
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"
sys.path.insert(0, str(_SRC_DIR))

from engineering.visual_regression import compute_ssim, generate_diff_image

app = QApplication.instance() or QApplication(sys.argv)

# Build precise Qt card with pixel sizes
card = QFrame()
card.setFixedSize(400, 180)
card.setStyleSheet("""
    QFrame {
        background-color: rgba(22, 28, 40, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
    }
""")

layout = QVBoxLayout(card)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)

hdr = QHBoxLayout()
hdr.setContentsMargins(0, 0, 0, 0)
title = QLabel("Neural Agent Dispatcher")
f_title = QFont("Segoe UI", -1)
f_title.setPixelSize(14)
f_title.setBold(True)
title.setFont(f_title)
title.setStyleSheet("color: #f3f6fc; background: transparent; border: none;")
hdr.addWidget(title)

badge = QLabel("AUTONOMOUS")
f_badge = QFont("Consolas", -1)
f_badge.setPixelSize(10)
f_badge.setBold(True)
badge.setFont(f_badge)
badge.setStyleSheet("""
    background-color: rgba(0, 229, 255, 0.15);
    color: #00e5ff;
    border: 1px solid rgba(0, 229, 255, 0.3);
    border-radius: 4px;
    padding: 2px 6px;
""")
hdr.addWidget(badge, alignment=Qt.AlignRight)
layout.addLayout(hdr)

sub = QLabel("The AuraAI agent ecosystem operates on top of native design tokens.")
f_sub = QFont("Segoe UI", -1)
f_sub.setPixelSize(12)
sub.setFont(f_sub)
sub.setWordWrap(True)
sub.setStyleSheet("color: #a5b4cb; background: transparent; border: none;")
layout.addWidget(sub)
layout.addStretch()

card.show()
app.processEvents()
pixmap = card.grab()
card.close()

ba = QByteArray()
buf = QBuffer(ba)
buf.open(QBuffer.WriteOnly)
pixmap.save(buf, "PNG")
buf.close()

qt_img = Image.open(BytesIO(ba.data()))

card_html = """<!DOCTYPE html>
<html>
<head>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; font-family: 'Segoe UI', sans-serif; }
    #card {
      width: 400px;
      height: 180px;
      background: rgba(22, 28, 40, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 16px;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      gap: 8px;
    }
    .hdr {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .title {
      font-size: 14px;
      font-weight: bold;
      color: #f3f6fc;
      line-height: 1.2;
    }
    .badge {
      font-family: Consolas, monospace;
      font-size: 10px;
      font-weight: bold;
      background: rgba(0, 229, 255, 0.15);
      color: #00e5ff;
      border: 1px solid rgba(0, 229, 255, 0.3);
      border-radius: 4px;
      padding: 2px 6px;
    }
    .sub {
      font-size: 12px;
      color: #a5b4cb;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <div id="card">
    <div class="hdr">
      <span class="title">Neural Agent Dispatcher</span>
      <span class="badge">AUTONOMOUS</span>
    </div>
    <div class="sub">
      The AuraAI agent ecosystem operates on top of native design tokens.
    </div>
  </div>
</body>
</html>"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
    page = browser.new_page(viewport={"width": 600, "height": 400})
    page.set_content(card_html)
    page.wait_for_timeout(100)
    loc = page.locator("#card")
    web_img = Image.open(BytesIO(loc.screenshot()))
    browser.close()

# Let's inspect SSIM with matching 400x180 normalization
qt_resized = qt_img.resize((400, 180))
web_resized = web_img.resize((400, 180))

score = compute_ssim(qt_resized, web_resized)
print(f"=== PARITY DIAGNOSTIC RESULTS ===")
print(f"Qt Raw: {qt_img.size}, Web Raw: {web_img.size}")
print(f"Pixel-Aligned Structural SSIM: {score:.4f}")

diff = generate_diff_image(qt_resized, web_resized)
diff.save("tests/visual_regression/diagnose_diff.png")
print("Saved tests/visual_regression/diagnose_diff.png")
