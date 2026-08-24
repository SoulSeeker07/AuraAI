"""
Debug tool query execution traceback
Location: scratch/debug_youtube_tool.py
"""

import asyncio
import sys
import traceback
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _PROJECT_ROOT / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(_PROJECT_ROOT))

from core.aura_core import AuraCore
from core.orchestration import MasterOrchestrator

async def main():
    print("Testing MasterOrchestrator.process_request_async('Search YouTube for Python tutorial')...")
    orchestrator = MasterOrchestrator.get_instance()
    try:
        res = await orchestrator.process_request_async("Search YouTube for Python tutorial")
        print("Result observations:", res.observations)
        print("Result data:", res.data)
        print("Result final_output:", getattr(res, "final_output", None))
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
