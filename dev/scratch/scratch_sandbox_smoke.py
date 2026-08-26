import tempfile
import subprocess
import shutil
import os
import sys
import time
from pathlib import Path
from src.desktop.native.sandbox.restricted_user_sandbox import RestrictedUserSandbox

def main():
    base_staging = Path("D:/Sreekanta/VS Code Project/Desktop AI/AuraAI/.staging").resolve()
    base_staging.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix='aura_test_icacls_', dir=str(base_staging))).resolve()
    print("Temp dir created:", temp_dir)

    # 1. Un-elevated icacls grant to AuraSandboxUser
    res = subprocess.run(['icacls', str(temp_dir), '/grant', 'AuraSandboxUser:(OI)(CI)(M)', '/q'], capture_output=True, text=True)
    print("icacls grant returncode:", res.returncode, "stdout:", res.stdout.strip(), "stderr:", res.stderr.strip())

    # 2. Write an adversarial test script attempting to read .env and user profile
    script = temp_dir / 'test_adversarial.py'
    script.write_text('''from pathlib import Path
import os

# 1. Output in staging should succeed
Path("output.txt").write_text("created_by_sandbox_user")

# 2. Attempt to read host .env
env_leaked = False
try:
    p = Path("D:/Sreekanta/VS Code Project/Desktop AI/AuraAI/.env")
    if p.exists():
        content = p.read_text()
        env_leaked = True
except Exception as e:
    print(f"EXPECTED_BLOCKED_ENV: {e}")

# 3. Attempt to write to host root
host_write_escaped = False
try:
    p = Path("C:/escape_test.txt")
    p.write_text("escaped")
    host_write_escaped = True
except Exception as e:
    print(f"EXPECTED_BLOCKED_ROOT_WRITE: {e}")

print(f"RESULTS: env_leaked={env_leaked}, host_write_escaped={host_write_escaped}")
''', encoding='utf-8')

    venv_python = Path(sys.executable).resolve()
    print("Host Python:", venv_python)

    # 3. Test execution via RestrictedUserSandbox
    sb = RestrictedUserSandbox()
    cmd = f'Set-Location "{temp_dir}"; & "{venv_python}" "{script}"'
    
    t0 = time.perf_counter()
    code, stdout, stderr = sb.execute(cmd, cwd=str(temp_dir), timeout=15.0)
    t1 = time.perf_counter()
    
    print(f"Execution took: {(t1-t0)*1000:.2f}ms")
    print("Return code:", code)
    print("Stdout:\n", stdout)
    print("Stderr:\n", stderr)

    # 4. Check if file was created, readable by host, and deletable by host
    out_file = temp_dir / "output.txt"
    print("out_file exists:", out_file.exists())
    if out_file.exists():
        content = out_file.read_text(encoding='utf-8')
        print("Host read content:", repr(content))
        out_file.unlink()
        print("Host successfully deleted out_file!")

    # 5. Clean up directory
    try:
        shutil.rmtree(temp_dir)
        print("Host successfully rmtree'd temp_dir!")
    except Exception as e:
        print("Host rmtree failed:", e)

if __name__ == '__main__':
    main()
