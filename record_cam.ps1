# Record cam1 to disk in 10-minute files, for the test weekend only.
#
#   record_cam.ps1           start recording (main and sub streams)
#   record_cam.ps1 -Stop     stop recording
#
# The usual way in is the "Cockaigne START + RECORD" desktop shortcut, which
# runs "start_studio.ps1 -Record" and so calls this file. The plain START,
# STOP and Ctrl+Alt+S all stop any recording. The exhibition records nothing:
# after $lastDay below this file refuses to record at all, so a forgotten
# shortcut cannot record in February.
#
# The video is copied straight from the camera without decoding, so it
# barely loads the PC and runs beside the live show; the sensing chain reads
# its own copy of the sub stream (three streams at once were tried on 27 Nov).
# Files go to the T7 at D:\cockaigne recordings\<date>, named like the Light
# Room footage: cam1_main_20261127_171500.mkv. Main measured about 2 GB an
# hour on 27 Nov (allow up to 3.5 GB with a busy room); sub is a few hundred MB.
# A hidden watcher restarts a stream within ten seconds if the camera drops it.
# The files stay on this PC and are never uploaded.
#
# Exit code 0 means recording is running; anything else means it is not.
param([switch]$Stop, [switch]$Watch, [string]$Dir)

$lastDay = [datetime]"2026-11-29"    # the last day recording is allowed
$minFreeGB = 20                      # do not start with less than this free on the T7
$root    = "D:\cockaigne recordings"
$ip      = "192.168.1.101"
$user    = "admin"
$streams = [ordered]@{ main = "h264Preview_01_main"; sub = "h264Preview_01_sub" }
$self    = $MyInvocation.MyCommand.Path

function Get-Ffmpegs {
    Get-CimInstance Win32_Process -Filter "Name = 'ffmpeg.exe'" |
        Where-Object { $_.CommandLine -match [regex]::Escape($ip) }
}

function Get-Watchers {
    Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe'" |
        Where-Object { $_.CommandLine -like "*record_cam.ps1*-Watch*" -and $_.ProcessId -ne $PID }
}

if ($Stop) {
    # The watcher goes first, so it cannot restart the streams being stopped.
    # A forced stop can leave the last file without its index; ffmpeg, VLC
    # and the sensing tools still read such a file.
    $w = @(Get-Watchers); $f = @(Get-Ffmpegs)
    $w + $f | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($f.Count) { Write-Host "Recording stopped." -ForegroundColor Green }
    exit 0
}

if ($Watch) {
    # The hidden watcher: start each stream, and start it again whenever it ends.
    $ffmpeg = (Get-Command ffmpeg).Source
    $url = { param($path) "rtsp://${user}:$([uri]::EscapeDataString($env:COCKAIGNE_RTSP_PASSWORD))@${ip}:554/$path" }
    while ($true) {
        $running = (@(Get-Ffmpegs) | ForEach-Object { $_.CommandLine }) -join " "
        foreach ($name in $streams.Keys) {
            if ($running -match $streams[$name]) { continue }
            $out = Join-Path $Dir "cam1_${name}_%Y%m%d_%H%M%S.mkv"
            $a = "-hide_banner -loglevel error -rtsp_transport tcp -timeout 10000000 -i `"$(& $url $streams[$name])`" " +
                 "-c copy -map 0:v -f segment -segment_time 600 -reset_timestamps 1 -strftime 1 `"$out`""
            Start-Process $ffmpeg -ArgumentList $a -WindowStyle Hidden
        }
        Start-Sleep -Seconds 10
    }
}

# Starting. Every check that fails says why and leaves the show alone.
function No($text) { Write-Host "NOT RECORDING: $text" -ForegroundColor Red; exit 1 }

if ((Get-Date).Date -gt $lastDay) { No "recording was only for the test weekend, up to $($lastDay.ToString('d MMM yyyy'))." }
if (-not $env:COCKAIGNE_RTSP_PASSWORD) { No "no camera password (COCKAIGNE_RTSP_PASSWORD)." }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { No "ffmpeg is not installed." }
$t7 = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID = 'D:'"
if (-not $t7 -or -not $t7.Size) { No "the T7 drive (D:) is not plugged in." }
$freeGB = [math]::Floor($t7.FreeSpace / 1GB)
if ($freeGB -lt $minFreeGB) { No "only $freeGB GB free on the T7." }

if (@(Get-Watchers).Count -eq 0) {
    if (-not $Dir) { $Dir = Join-Path $root (Get-Date -Format "yyyy-MM-dd") }
    New-Item -ItemType Directory -Force $Dir | Out-Null
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "`"$self`"", "-Watch", "-Dir", "`"$Dir`""
}
foreach ($i in 1..10) { if (@(Get-Ffmpegs).Count -ge 2) { break }; Start-Sleep -Seconds 1 }
Start-Sleep -Seconds 3   # a stream the camera refuses ends within a few seconds
if (@(Get-Ffmpegs).Count -lt 2) {
    & $self -Stop | Out-Null
    No "the camera did not give both streams. Check that cam1 is on."
}
Write-Host "RECORDING cam1 to $Dir ($freeGB GB free, about 2 to 3.5 GB an hour)." -ForegroundColor Yellow
exit 0
