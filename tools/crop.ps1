param(
  [string]$In,
  [string]$Out,
  [int]$X = 0,
  [int]$Y = 0,
  [int]$W = 200,
  [int]$H = 400,
  [int]$Scale = 3
)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile($In)
$rect = New-Object System.Drawing.Rectangle $X, $Y, $W, $H
$crop = New-Object System.Drawing.Bitmap $W, $H
$g = [System.Drawing.Graphics]::FromImage($crop)
$g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, $W, $H), $rect, [System.Drawing.GraphicsUnit]::Pixel)
$g.Dispose()
$big = New-Object System.Drawing.Bitmap ($W * $Scale), ($H * $Scale)
$g2 = [System.Drawing.Graphics]::FromImage($big)
$g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$g2.DrawImage($crop, 0, 0, ($W * $Scale), ($H * $Scale))
$g2.Dispose()
$big.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$src.Dispose(); $crop.Dispose(); $big.Dispose()
Write-Output $Out
