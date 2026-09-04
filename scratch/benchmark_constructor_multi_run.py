import time
import os
import sys
import subprocess

print("=" * 70)
print("RUNNING 5-ITERATION CONSTRUCTOR BENCHMARK")
print("=" * 70)

results = []
for i in range(5):
    code = """
import sys, os, time
sys.path.insert(0, os.path.abspath("src"))
from core.aura_core import AuraCore
t0 = time.time()
aura = AuraCore()
t1 = time.time()
print(f"TOTAL_CONSTRUCTOR:{(t1 - t0)*1000:.1f}")
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    out = res.stdout + res.stderr
    print(f"--- [RUN {i+1}/5] ---")
    for line in out.splitlines():
        if "AuraCore Init" in line or "TOTAL_CONSTRUCTOR" in line:
            print(line)
        if "TOTAL_CONSTRUCTOR" in line:
            dur = float(line.split(":")[1])
            results.append(dur)

if results:
    avg = sum(results) / len(results)
    med = sorted(results)[len(results)//2]
    print("\n" + "=" * 70)
    print(f"SUMMARY (5 Runs): Mean = {avg:.1f}ms | Median = {med:.1f}ms | Min = {min(results):.1f}ms | Max = {max(results):.1f}ms")
    print("=" * 70)
