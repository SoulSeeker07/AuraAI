import subprocess

ps = """
Add-Type -TypeDefinition @"
using System;
using System.Threading.Tasks;
using Windows.Devices.Radios;
using System.Collections.Generic;

public class BTTester {
    public static async Task<string> Test() {
        try {
            var radios = await Radio.GetRadiosAsync();
            Radio bt = null;
            foreach(var r in radios) {
                if (r.Kind == RadioKind.Bluetooth) { bt = r; break; }
            }
            if (bt == null) return "NO_BT";
            
            var offStatus = await bt.SetStateAsync(RadioState.Off);
            await Task.Delay(1500);
            
            var onStatus = await bt.SetStateAsync(RadioState.On);
            await Task.Delay(1500);
            
            return "OFF=" + offStatus.ToString() + " ON=" + onStatus.ToString() + " FINAL=" + bt.State.ToString();
        } catch (Exception ex) {
            return "ERR: " + ex.Message;
        }
    }
}
"@ -ReferencedAssemblies "System.Runtime.WindowsRuntime", "Windows.System.Devices" -ErrorAction Stop

[BTTester]::Test().GetAwaiter().GetResult()
"""

r = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
    capture_output=True,
    text=True,
    timeout=20,
)
print(r.stdout.strip())
if r.stderr:
    print("ERR:", r.stderr.strip())
