import subprocess
import time
from desktop.native.adapters.com_threading import com_scope
from desktop.native.adapters.uia_adapter import PywinautoUIAAdapter

PS_WINFORMS_CODE = """
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object Windows.Forms.Form
$form.Text = "AuraAI WinForms Probe"
$form.Width = 350
$form.Height = 220

$tb = New-Object Windows.Forms.TextBox
$tb.Text = "Initial Value"
$tb.Top = 20
$tb.Left = 20
$tb.Width = 200
$tb.Name = "TestTextBox"
$form.Controls.Add($tb)

$btn = New-Object Windows.Forms.Button
$btn.Text = "Click Me"
$btn.Top = 60
$btn.Left = 20
$btn.Name = "TestButton"
$btn.Add_Click({ $tb.Text = "Button Was Clicked" })
$form.Controls.Add($btn)

[Windows.Forms.Application]::Run($form)
"""

def test_live_winforms_round_trip():
    print("--- Starting Live Real-OS WinForms UIA Probe ---")
    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", PS_WINFORMS_CODE])
    time.sleep(2.0)
    
    try:
        with com_scope():
            adapter = PywinautoUIAAdapter()
            win_title = "AuraAI WinForms Probe"
            
            # 1. Inspect tree
            print("1. Querying element tree...")
            tree = adapter.get_element_tree(window_title=win_title, depth=3)
            print(f"   Window Root: '{tree.element.name if tree else None}'")
            assert tree is not None
            
            # 2. Locate Edit control
            print("2. Locating Edit control...")
            edit_elem = adapter.find_element(window_title=win_title, control_type="Edit", automation_id="TestTextBox")
            print(f"   Found Edit Element: auto_id='{edit_elem.automation_id}' (type: {edit_elem.control_type})")
            assert edit_elem is not None
            
            # 3. Read initial value
            val0 = adapter.get_element_value(edit_elem, window_title=win_title)
            print(f"   Initial Value: '{val0}'")
            assert val0 == "Initial Value"
            
            # 4. Type new text (Clear-then-type verification)
            print("4. Executing uia.type_text('New Clean Input')...")
            t0 = time.perf_counter()
            type_ok = adapter.type_text(edit_elem, "New Clean Input", window_title=win_title)
            type_dur = (time.perf_counter() - t0) * 1000.0
            print(f"   type_text returned: {type_ok} in {type_dur:.2f}ms")
            assert type_ok is True
            
            # 5. Immediate value read to check UI race conditions
            print("5. Immediate value read to verify state change and check repaint race...")
            t0 = time.perf_counter()
            val1 = adapter.get_element_value(edit_elem, window_title=win_title)
            read_dur = (time.perf_counter() - t0) * 1000.0
            print(f"   get_element_value returned: '{val1}' in {read_dur:.2f}ms")
            assert val1 == "New Clean Input"
            assert "Initial Value" not in val1, "Clear-then-type failed: old text retained!"
            
            # 6. Button Click & Verification
            print("6. Locating and clicking Button control...")
            btn_elem = adapter.find_element(window_title=win_title, control_type="Button", name="Click Me")
            print(f"   Found Button: '{btn_elem.name}' (type: {btn_elem.control_type})")
            assert btn_elem is not None
            
            t0 = time.perf_counter()
            click_ok = adapter.click_element(btn_elem, window_title=win_title)
            click_dur = (time.perf_counter() - t0) * 1000.0
            print(f"   click_element returned: {click_ok} in {click_dur:.2f}ms")
            assert click_ok is True
            
            # 7. Post-click value verification
            val2 = adapter.get_element_value(edit_elem, window_title=win_title)
            print(f"   get_element_value after button click: '{val2}'")
            assert val2 == "Button Was Clicked"
            
            print("\n=== Live Real-OS WinForms UIA Probe SUCCEEDED ===")
            print(f"  - Element Tree: PASSED")
            print(f"  - Clear-then-type Semantics: PASSED ('{val0}' -> '{val1}')")
            print(f"  - Button Click & State Mutation: PASSED ('{val1}' -> '{val2}')")
            print(f"  - UI Race Check: 0 races observed (Read latency {read_dur:.2f}ms)")
    finally:
        print("Cleaning up WinForms probe subprocess...")
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    test_live_winforms_round_trip()
