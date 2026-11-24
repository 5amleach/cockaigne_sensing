# Record cam1 to disk in 10-minute files, for test footage only.
#
#   record_cam.ps1           start recording (main and sub streams)
#   record_cam.ps1 -Stop     stop recording
#
# The exhibition itself records nothing. This is for tuning days only.
# The video is copied straight from the camera without decoding, so it
# barely loads the PC and runs beside the live show. Files go to
# D:\cockaigne recordings\<date>, named like the Light Room footage:
# cam1_main_20261127_101500.mkv. About 3.3 GB an hour for main, little for sub.
# They stay on this PC and are never uploaded.
param([switch]$Stop)

$repo   = $PSScriptRoot
$camera = "cam1"
$ip     = "192.168.1.101"
$user   = "admin"
$root   = "D:\cockaigne recordings"
$streams = @{ main = "h264Preview_01_main"; sub = "h264Preview_01_sub" }

$Host.UI.RawUI.WindowTitle = "Cockaigne recorder"

function Get-Recorders {
    Get-CimInstance Win32_Process -Filter "Name = 'ffmpeg.exe'" |
        Where-Object { $_.CommandLine -match [regex]::Escape($ip) }
}

if ($Stop) {
    $procs = @(Get-Recorders)
    # A forced stop can leave the last file without its index; ffmpeg and
    # the sensing tools still read such a file.
    $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "Recording stopped ($($procs.Count) streams)." -ForegroundColor Green
    Start-Sleep 3
    return
}

if (@(Get-Recorders).Count -gt 0) {
    Write-Host "Already recording. Run record_cam.ps1 -Stop first." -ForegroundColor Yellow
    Start-Sleep 5
    return
}

$pwFile = Join-Path $repo "camera_password.txt"
if (Test-Path $pwFile) { $pw = (Get-Content $pwFile -TotalCount 1).Trim() }
else { $pw = $env:COCKAIGNE_RTSP_PASSWORD }
if (-not $pw) { Write-Host "No camera password (camera_password.txt)." -ForegroundColor Red; Start-Sleep 10; return }

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpeg) { Write-Host "ffmpeg not found." -ForegroundColor Red; Start-Sleep 10; return }

$dir = Join-Path $root (Get-Date -Format "yyyy-MM-dd")
New-Item -ItemType Directory -Force $dir | Out-Null

foreach ($name in $streams.Keys) {
    $url = "rtsp://${user}:$([uri]::EscapeDataString($pw))@${ip}:554/$($streams[$name])"
    $out = Join-Path $dir "${camera}_${name}_%Y%m%d_%H%M%S.mkv"
    $args = "-hide_banner -loglevel error -rtsp_transport tcp -i `"$url`" -c copy -map 0:v " +
            "-f segment -segment_time 600 -reset_timestamps 1 -strftime 1 `"$out`""
    Start-Process $ffmpeg -ArgumentList $args -WindowStyle Hidden
}
Start-Sleep 4
$n = @(Get-Recorders).Count
if ($n -eq 2) { Write-Host "Recording cam1 to $dir" -ForegroundColor Green }
else { Write-Host "Only $n of 2 streams started. Check the camera." -ForegroundColor Red }
Start-Sleep 4
