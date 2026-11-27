param(
  [string]$Out = 'figures\screen.png',
  [string]$TitleLike = ''
)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

if ($TitleLike -ne '') {
  Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Wnd {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
}
"@
  $p = Get-Process | Where-Object { $_.MainWindowTitle -like $TitleLike } | Select-Object -First 1
  if ($p) {
    [Wnd]::ShowWindow($p.MainWindowHandle, 9) | Out-Null
    [Wnd]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 900
  } else {
    Write-Output "no window matched: $TitleLike"
  }
}

$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ("saved {0} ({1}x{2})" -f $Out, $b.Width, $b.Height)
