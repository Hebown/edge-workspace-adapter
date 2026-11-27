param([string]$TitleLike = '*Microsoft*Edge*')
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Wnd2 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
$p = Get-Process | Where-Object { $_.MainWindowTitle -like $TitleLike } | Select-Object -First 1
if ($p) {
  [Wnd2]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
  [Wnd2]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
  Start-Sleep -Milliseconds 800
  [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
  Start-Sleep -Milliseconds 600
  Write-Output ("sent ENTER to " + $p.MainWindowTitle)
} else {
  Write-Output 'no window matched'
}
