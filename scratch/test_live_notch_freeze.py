import subprocess
import sys
import time
import ctypes

user32 = ctypes.windll.user32

cmd = [sys.executable, "run_voice_notch.py"]
proc = subprocess.Popen(cmd)
print(f"Started run_voice_notch.py with PID {proc.pid}")

try:
    for i in range(12):
        time.sleep(1)
        # Find HWNDs for this PID
        hwnds = []
        def enum_cb(hwnd, _):
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == proc.pid and user32.IsWindowVisible(hwnd):
                hwnds.append(hwnd)
            return True

        ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(ENUM_PROC(enum_cb), 0)

        hung_status = [bool(user32.IsHungAppWindow(h)) for h in hwnds]
        print(f"Second {i+1}: HWNDs found={len(hwnds)}, is_hung={hung_status}")
        if any(hung_status):
            print(">>> DETECTED HUNG / NOT RESPONDING WINDOW! <<<")
            break
finally:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
    print("Process terminated.")
