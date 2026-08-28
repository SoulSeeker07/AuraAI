import time
import sys
import os
import psutil
from pathlib import Path

# Add src to sys.path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(1, str(root))

print("================================================================")
print("             AURA AI — REAL-TIME PLATFORM BENCHMARK             ")
print("================================================================\n")

# 1. Hardware & System Telemetry
cpu_pct = psutil.cpu_percent(interval=0.2)
ram = psutil.virtual_memory()
print(f"[Hardware] CPU: {psutil.cpu_count(logical=False)} Cores / {psutil.cpu_count(logical=True)} Threads ({cpu_pct}% load)")
print(f"[Hardware] RAM: {ram.used / (1024**3):.2f} GB used / {ram.total / (1024**3):.2f} GB total ({ram.percent}%)")

try:
    import torch
    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_name(0)
        vram_alloc = torch.cuda.memory_allocated(0) / (1024**2)
        vram_res = torch.cuda.memory_reserved(0) / (1024**2)
        print(f"[Hardware] GPU: {gpu} (CUDA FP16 Enabled, VRAM Alloc: {vram_alloc:.1f} MB, Reserved: {vram_res:.1f} MB)")
    else:
        print("[Hardware] GPU: CUDA device not active (CPU Mode)")
except Exception as e:
    print(f"[Hardware] GPU: {e}")

# 2. Intent Routing & NLU Classification
try:
    from brain.intent_router import IntentRouter
    from Memory import Memory
    mem = Memory(db_path=str(root / "Memory.db"), chat_log_path=str(root / "Data" / "ChatLog.json"))
    router = IntentRouter(memory=mem)

    queries = [
        "what time is it",
        "open chrome",
        "show logs",
        "what is the weather today",
        "remember that my favorite language is Python",
        "search google for quantum computing",
    ]

    # Warmup
    for q in queries:
        router.detect(q)

    t0 = time.perf_counter()
    N = 200
    for _ in range(N):
        for q in queries:
            router.detect(q)
    elapsed = (time.perf_counter() - t0) * 1000 / (N * len(queries))
    throughput = 1000.0 / elapsed
    print(f"\n[Cognitive Routing] Avg Intent Detection Latency: {elapsed:.3f} ms / query ({throughput:,.0f} queries/sec)")
except Exception as e:
    print(f"\n[Cognitive Routing] Error: {e}")

# 3. Dense Vector Memory Search Benchmark
try:
    facts = mem.facts()
    # Warmup
    mem.search_semantic("warmup query", limit=5)

    t0 = time.perf_counter()
    N_VEC = 30
    for _ in range(N_VEC):
        results = mem.search_semantic("python project architecture", limit=5)
    v_search_ms = (time.perf_counter() - t0) * 1000 / N_VEC
    print(f"[Vector Memory] 384-Dim Neural Cosine Search: {v_search_ms:.2f} ms / query ({len(results)} matches across {len(facts)} persistent facts)")
except Exception as e:
    print(f"[Vector Memory] Note: {e}")

# 4. Live Log HUD High-Speed Binary Tail Benchmark
try:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication
    from gui.widgets.live_log_viewer_overlay import LiveLogViewerOverlay

    app = QApplication.instance() or QApplication([])
    viewer = LiveLogViewerOverlay()

    t0 = time.perf_counter()
    M = 50
    for _ in range(M):
        viewer._refresh_logs()
    tail_ms = (time.perf_counter() - t0) * 1000 / M
    fps_cap = 1000.0 / tail_ms
    print(f"[Live Log HUD] Binary Seek Tail & 6-Filter Refresh: {tail_ms:.2f} ms / cycle ({fps_cap:.0f} FPS capability)")
except Exception as e:
    print(f"[Live Log HUD] Error: {e}")

# 5. Token Quota & Multi-Account Pool
try:
    from gui.real_backend_bridge import RealBackendBridge
    bridge = RealBackendBridge.get_instance()
    tokens = bridge.get_daily_token_usage()
    consumed = tokens.get("consumed", 0)
    limit = tokens.get("limit", 1000000)
    accts = tokens.get("accounts_count", 5)
    pct = tokens.get("pct_used", 0.0)
    print(f"\n[Token Quota Pool] Consumed: {consumed:,} / {limit:,} tokens ({pct}%) across {accts} accounts")
except Exception as e:
    print(f"\n[Token Pool] Error: {e}")

# 6. Display & Refresh Rate
try:
    from gui.widgets.voice_notch_overlay import get_display_refresh_rate
    hz = get_display_refresh_rate()
    frame_budget_ms = 1000.0 / hz
    print(f"[GUI Rendering] Native Display Refresh: {hz:.0f} Hz (Frame Budget: {frame_budget_ms:.2f} ms)")
except Exception as e:
    print(f"[GUI Rendering] Error: {e}")

print("\n================================================================")
