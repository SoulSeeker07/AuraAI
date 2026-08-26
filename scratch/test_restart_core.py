import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

from main import get_aura_core

async def test():
    core = get_aura_core(config={"voice_enabled": False})
    with patch("threading.Thread") as mock_thread:
        res = await core.process_request("restart aura")
        print("Response from restart aura:\n", res)
        assert "Graceful Restart" in res or "Restart" in res
        print("✓ AuraCore.process_request('restart aura') passed cleanly!")

if __name__ == "__main__":
    asyncio.run(test())
