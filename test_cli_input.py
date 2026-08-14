import sys
import io

inputs = """hi
open chrome
create student database python code
analyze my repository
fix the bug in my Python code
quit
"""
sys.stdin = io.StringIO(inputs)

import main
import asyncio

asyncio.run(main.main_cli())
