import time
import os
import sys
import psutil
import ctypes

sys.path.insert(0, os.path.abspath("src"))

print("=" * 70)
print("1. HARDWARE & CPU CORE DIAGNOSTICS")
print("=" * 70)
phys_cores = psutil.cpu_count(logical=False)
log_cores = psutil.cpu_count(logical=True)
per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)
print(f"Physical Cores: {phys_cores} | Logical Cores: {log_cores}")
print(f"Current Per-CPU Utilization: {per_cpu}")

print("\n" + "=" * 70)
print("2. SetThreadPriority API RETURN VALUE & ERROR CHECK")
print("=" * 70)
# Test setting priority on current thread
handle = ctypes.windll.kernel32.GetCurrentThread()
ret = ctypes.windll.kernel32.SetThreadPriority(handle, -1) # THREAD_PRIORITY_BELOW_NORMAL
last_err = ctypes.windll.kernel32.GetLastError()
print(f"SetThreadPriority(GetCurrentThread(), -1) -> Return: {ret} (Success if non-zero) | LastError: {last_err}")

print("\n" + "=" * 70)
print("3. DECOMPOSING THE COLD EMBEDDING LOAD STEP-BY-STEP")
print("=" * 70)
# Step A: import torch
t0 = time.time()
import torch
t1 = time.time()
print(f"A. import torch: {(t1 - t0)*1000:.1f}ms")

# Step B: import sentence_transformers
t2 = time.time()
from sentence_transformers import SentenceTransformer
t3 = time.time()
print(f"B. from sentence_transformers import SentenceTransformer: {(t3 - t2)*1000:.1f}ms")

# Step C: Load SentenceTransformer model weights
t4 = time.time()
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
t5 = time.time()
print(f"C. SentenceTransformer('all-MiniLM-L6-v2', device='cpu'): {(t5 - t4)*1000:.1f}ms")

# Step D: Vector table & SQLite Fact DB
t6 = time.time()
from memory.vector_memory import VectorMemoryEngine
vm = VectorMemoryEngine.get_instance()
t7 = time.time()
print(f"D. VectorMemoryEngine.get_instance() & SQLite setup: {(t7 - t6)*1000:.1f}ms")

# Step E: Dry-run encoding (first inference)
t8 = time.time()
_ = model.encode("set volume to 60 and summarize today's session")
t9 = time.time()
print(f"E. model.encode() dry-run inference: {(t9 - t8)*1000:.1f}ms")

total_cold = (t9 - t0)*1000
print(f"\nTOTAL DECOMPOSED COLD LOAD TIME: {total_cold:.1f}ms ({total_cold/1000:.2f}s)")
