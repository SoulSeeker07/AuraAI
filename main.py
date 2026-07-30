import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_DIR))

from core.app import AuraApplication


if __name__ == "__main__":
    print("Starting AuraAI memory-enabled app...")
    app = AuraApplication()
    sys.exit(app.run())
