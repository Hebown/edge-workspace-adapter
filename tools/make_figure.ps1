# Build the before/after figure from Edge's own cached workspace icons.
Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
$raw = Join-Path $root 'figures\raw'
$out = Join-Path $root 'figures\icon-before-after.png'

$emojiPath = Join-Path $raw 'emoji-folder.png'
$defaultPath = Join-Path $raw 'default-wireframe.png'

$bmp = New-Object System.Drawing.Bitmap 900, 300
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(24, 26, 31))
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

$white = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(236, 239, 244))
$muted = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(154, 160, 170))
$blue = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(120, 170, 240))
$fontTitle = New-Object System.Drawing.Font('Microsoft YaHei', 18, [System.Drawing.FontStyle]::Bold)
$font = New-Object System.Drawing.Font('Microsoft YaHei', 12)
$fontMono = New-Object System.Drawing.Font('Consolas', 11)

function Draw-Cell($x, $title, $path, $desc, $accent) {
  $g.DrawString($title, $fontTitle, $accent, $x, 18)
  $icon = [System.Drawing.Image]::FromFile($path)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
  $g.DrawImage($icon, (New-Object System.Drawing.Rectangle ($x + 8), 70, 128, 128),
               (New-Object System.Drawing.Rectangle 0, 0, 32, 32),
               [System.Drawing.GraphicsUnit]::Pixel)
  $icon.Dispose()
  $g.DrawString($desc, $font, $muted, $x, 208)
}

Draw-Cell 40 'BEFORE / 之前' $emojiPath 'details.9 = "F0 9F 93 81"  (U+1F4C1 文件夹)' $white
Draw-Cell 480 'AFTER / 之后' $defaultPath 'details.9 删除 -> 内置线框（色由 details.2 决定）' $blue

$g.DrawString('Edge 158  //  edge_workspace-dt-<id>  //  sync 数据', $fontMono, $muted, 40, 266)
$g.DrawLine((New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(90, 96, 106))), 442, 30, 442, 250)

$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output $out
