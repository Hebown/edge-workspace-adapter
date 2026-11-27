param([string]$Match = '')
$procs = Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" |
  Where-Object { $Match -eq '' -or $_.CommandLine -like "*$Match*" }
if (-not $procs) { Write-Output 'no matching msedge.exe'; exit 0 }
Write-Output ("closing {0} process(es)" -f @($procs).Count)
foreach ($p in $procs) {
  try { Stop-Process -Id $p.ProcessId -ErrorAction Stop } catch { }
}
Start-Sleep -Seconds 3
$left = Get-Process msedge -ErrorAction SilentlyContinue
if ($left) { Write-Output ("still running: {0}" -f @($left).Count) } else { Write-Output 'all msedge.exe exited' }
