param(
  [string]$SourceDir,
  [string]$OutDir
)
Add-Type -AssemblyName System.Drawing
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

Get-ChildItem -LiteralPath $SourceDir -File | Where-Object { $_.Extension -eq '' } | ForEach-Object {
  try {
    $icon = New-Object System.Drawing.Icon($_.FullName)
    $w = $icon.Width; $h = $icon.Height
    $bmp = $icon.ToBitmap()
    $out = Join-Path $OutDir ($_.BaseName + '.png')
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output ("{0} -> {1}x{2} -> {3}" -f $_.Name, $w, $h, $out)
    $bmp.Dispose(); $icon.Dispose()
  } catch {
    Write-Output ("SKIP {0}: {1}" -f $_.Name, $_.Exception.Message)
  }
}
