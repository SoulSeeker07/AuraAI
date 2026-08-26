import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(1, str(PROJECT_ROOT))

print("1. Importing AuraCore...", flush=True)
from core.aura_core import AuraCore

print("2. Instantiating AuraCore...", flush=True)
core = AuraCore(config={"voice_enabled": False})

print("3. AuraCore instantiated successfully!", flush=True)
