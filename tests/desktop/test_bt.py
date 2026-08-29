import subprocess
import sys


def main():
    ps = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime; 
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; 
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime]|Out-Null; 
$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods()|?{$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'})[0]; 
$getRadios={$asTask.MakeGenericMethod([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]]).Invoke($null,@([Windows.Devices.Radios.Radio]::GetRadiosAsync())).Result}; 
$bt=(&$getRadios)|?{$_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth}|Select-Object -First 1; 

$setStatus={$asTask.MakeGenericMethod([Windows.Devices.Radios.RadioAccessStatus]).Invoke($null,@($bt.SetStateAsync($args[0]))).Result}; 

Write-Output ('Initial:'+$bt.State.ToString());
$r1 = &$setStatus ([Windows.Devices.Radios.RadioState]::Off);
Write-Output ('SetOffResult:'+$r1.ToString());
Start-Sleep -Milliseconds 1000;
Write-Output ('StateAfterOff:'+$bt.State.ToString());

$r2 = &$setStatus ([Windows.Devices.Radios.RadioState]::On);
Write-Output ('SetOnResult:'+$r2.ToString());
Start-Sleep -Milliseconds 1000;
Write-Output ('StateAfterOn:'+$bt.State.ToString());
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
