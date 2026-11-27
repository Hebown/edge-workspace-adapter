param(
  [string]$UserDataDir,
  [string]$Url = 'edge://version',
  [string]$Extra = '',
  [int]$WaitMs = 9000
)
$exe = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$cmdArgs = @(
  "--user-data-dir=$UserDataDir",
  '--no-first-run',
  '--no-default-browser-check',
  $Url
)
if ($Extra -ne '') { $cmdArgs = @($Extra) + $cmdArgs }
Start-Process -FilePath $exe -ArgumentList $cmdArgs
Start-Sleep -Milliseconds $WaitMs
Get-Process msedge -ErrorAction SilentlyContinue |
  Where-Object { $_.MainWindowTitle -ne '' } |
  Select-Object Id, MainWindowTitle | Format-Table -AutoSize | Out-String -Width 200
