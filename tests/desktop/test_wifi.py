import subprocess
import sys


def main():
    ps = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime; 
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; 
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; 
$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0]; 
$getRadios={$asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]).Invoke($null,@([Windows.Devices.Radios.Radio]::GetRadiosAsync())).Result}; 
$wifi=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi}|Select-Object -First 1; 
if($null -eq $wifi){Write-Output 'NO_WIFI'; exit};
Write-Output ('Initial WiFi State: '+$wifi.State.ToString());
"""

    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True,
        text=True,
    )
    print(r.stdout.strip())
    if r.stderr:
        print("ERR:", r.stderr.strip())


if __name__ == "__main__":
    main()
