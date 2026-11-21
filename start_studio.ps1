# Start the studio live test with one double-click: Resolume, the sensing
# chain on the shed camera, the controller that fires clips, and the data wall.
#
# A desktop shortcut runs this file. Running it again restarts the sensing
# chain and the controller cleanly, and leaves Resolume as it is.
#   -Stop     closes the sensing chain, the controller and the data wall, and nothing else.
#   -Stop -All  closes Resolume as well, which takes its full-screen picture
#             off the monitors. The Cockaigne STOP shortcut does this, and its
#             key (Ctrl+Alt+S) works even when the picture covers the desktop.
#   -NoWall   does not open the data wall page.
#
# Each of the two programs gets its own window, titled "Cockaigne sensing" and
# "Cockaigne controller". The windows stay open if a program stops, so its
# last words can be read. See RUNBOOK.md, "The studio shed, one double-click".
param([switch]$Stop, [switch]$All, [switch]$NoWall)

$repo        = $PSScriptRoot
$python      = Join-Path $repo ".venv\Scripts\python.exe"
$config      = "config/studio.yaml"
# Resolume Avenue is used when it is installed, otherwise Arena. The controller speaks to either the same way.
$avenue      = "C:\Program Files\Resolume Avenue\Avenue.exe"
$arena       = "C:\Program Files\Resolume Arena\Arena.exe"
if (Test-Path $avenue) { $arena = $avenue }
$resolume    = [IO.Path]::GetFileNameWithoutExtension($arena)   # "Avenue" or "Arena", the process name
# The composition with the sounds loaded (RUNBOOK.md, "Sound"), wherever Resolume saved it.
$compositionName = "cockaigne_e29"
$documents   = [Environment]::GetFolderPath("MyDocuments")
$composition = "Resolume Avenue", "Resolume Arena" |
    ForEach-Object { Join-Path $documents "$_\Compositions\$compositionName.avc" } |
    Where-Object { Test-Path $_ } | Select-Object -First 1
$edge        = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$wallSpot    = "1.75,3.5"   # the viewing spot in config/studio.yaml, drawn on the wall's floor plan
# The data wall's Edge keeps its own profile here, so it is a separate Edge from
# Sam's own and can be placed, and closed, without touching Sam's own windows.
$wallProfile = Join-Path $repo ".edge-wall"
$restUrl     = "http://127.0.0.1:8080/api/v1/composition"
$minClips    = 100          # layer 1 holds 288 clips; fewer than this means the composition is still loading

function Say($text, $colour = "Gray") { Write-Host $text -ForegroundColor $colour }

function Fail($text) {
    Say ""
    Say "COULD NOT START: $text" "Red"
    Say ""
    Read-Host "Press Enter to close this window"
    exit 1
}

function Stop-Ours {
    # Our two programs are found by the module name on their command line.
    $ours = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match "cockaigne_sensing\.run|cockaigne_controller\.run" -and
        $_.ProcessId -ne $PID -and $_.Name -match "^(python|cmd)" }
    foreach ($p in $ours) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($ours) { Start-Sleep -Seconds 2 }
    return @($ours).Count
}

function Port-Open($port) {
    $client = New-Object Net.Sockets.TcpClient
    try { $client.Connect("127.0.0.1", $port); return $true } catch { return $false } finally { $client.Close() }
}

function Clips-Loaded {
    try {
        $c = Invoke-RestMethod $restUrl -TimeoutSec 5
        return @($c.layers[0].clips | Where-Object { $_.name.value }).Count
    } catch { return -1 }
}

function Stop-Wall {
    # Only the Edge that uses the data wall's own profile folder is closed.
    $wall = Get-CimInstance Win32_Process -Filter "Name = 'msedge.exe'" |
        Where-Object { $_.CommandLine -like "*$wallProfile*" }
    foreach ($p in $wall) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($wall) { Start-Sleep -Seconds 1 }
}

function Open-Wall($url) {
    # The data screen is the one that is not the widest; the widest is the landscape.
    # With one screen the wall opens as an ordinary window, as before.
    Add-Type -AssemblyName System.Windows.Forms
    $screens = [System.Windows.Forms.Screen]::AllScreens | Sort-Object { $_.Bounds.Width } -Descending
    $edgeArgs = "--user-data-dir=`"$wallProfile`"", "--no-first-run"
    if (@($screens).Count -gt 1) {
        # Kiosk mode is full screen with no bars, on the screen the window starts on.
        $b = $screens[1].Bounds
        $edgeArgs += "--window-position=$($b.X),$($b.Y)", "--kiosk", $url, "--edge-kiosk-type=fullscreen"
    } else {
        $edgeArgs += "--new-window", $url
    }
    Start-Process $edge -ArgumentList $edgeArgs
    return @($screens).Count -gt 1
}

function Start-Window($title, $module, $arguments) {
    $line = "title $title & `"$python`" -m $module $arguments"
    Start-Process cmd.exe -ArgumentList "/k", $line -WorkingDirectory $repo
}

$Host.UI.RawUI.WindowTitle = "Cockaigne start"
Set-Location $repo

if ($Stop) {
    $n = Stop-Ours
    Stop-Wall
    if ($All) {
        Get-Process Avenue, Arena -ErrorAction SilentlyContinue | Stop-Process -Force
        Say "Stopped the sensing chain, the controller ($n processes), the data wall and Resolume." "Green"
    } else {
        Say "Stopped the sensing chain, the controller ($n processes) and the data wall. Resolume is untouched." "Green"
    }
    Start-Sleep -Seconds 3
    exit 0
}

Say "Cockaigne studio live test" "Cyan"
Say ""

# 1. Things that must exist before anything starts.
if (-not (Test-Path $python)) { Fail "Python is missing at $python" }
if (-not (Test-Path (Join-Path $repo "camera_password.txt")) -and -not $env:COCKAIGNE_RTSP_PASSWORD) {
    Fail "No camera password. Set COCKAIGNE_RTSP_PASSWORD or write camera_password.txt (RUNBOOK.md)."
}

# 2. Resolume, with the Cockaigne composition loaded.
if (-not (Get-Process Avenue, Arena -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $arena))       { Fail "Resolume is missing at $arena" }
    if (-not $composition) { Fail "The composition $compositionName.avc is not in Documents\Resolume Avenue\Compositions" }
    Say "Starting Resolume $resolume with $compositionName ..."
    Start-Process $arena -ArgumentList "`"$composition`"" -WorkingDirectory (Split-Path $arena)
} else {
    Say "Resolume is already running."
}
$clips = -1
foreach ($i in 1..60) {
    $clips = Clips-Loaded
    if ($clips -ge $minClips) { break }
    Start-Sleep -Seconds 2
}
if ($clips -lt 0) { Fail "Resolume does not answer on port 8080. In Resolume: Preferences, Webserver, switch it on." }
if ($clips -lt $minClips) { Fail "Resolume is open but layer 1 holds $clips clips. Load the $compositionName composition, then double-click again." }
Say "Resolume is ready: $clips clips on layer 1." "Green"

# 3. A clean slate, then the sensing chain.
$old = Stop-Ours
if ($old) { Say "Closed an earlier run ($old processes)." }
Say "Starting the sensing chain on the shed camera ..."
Start-Window "Cockaigne sensing" "cockaigne_sensing.run" "--config $config"
$up = $false
foreach ($i in 1..60) { if (Port-Open 8765) { $up = $true; break }; Start-Sleep -Seconds 2 }
if (-not $up) { Fail "The sensing chain did not open its bus on port 8765. Read the 'Cockaigne sensing' window." }
Say "Sensing is up. The camera takes about ten more seconds to settle." "Green"

# 4. The controller, which fires its first clip at once.
Say "Starting the controller ..."
Start-Window "Cockaigne controller" "cockaigne_controller.run" ""
Start-Sleep -Seconds 4

# 5. The data wall.
if (-not $NoWall) {
    $wall = "file:///" + ((Join-Path $repo "datawall\index.html") -replace "\\", "/" -replace " ", "%20") + "?spot=$wallSpot"
    Stop-Wall   # a second double-click replaces the wall rather than adding one
    if (-not (Test-Path $edge)) { Start-Process $wall; Say "Data wall opened. Press F11 in it for full screen." }
    elseif (Open-Wall $wall) { Say "Data wall opened full screen on the data screen." }
    else { Say "Data wall opened. There is one screen, so press F11 in it for full screen." }
}

Say ""
Say "Running. One clip fires each minute; walk into the shed and the ring climbs." "Cyan"
Say "To stop: press Ctrl+Alt+S, or use the 'Cockaigne STOP' shortcut."
Start-Sleep -Seconds 12
