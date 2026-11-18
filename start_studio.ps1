# Start the studio live test with one double-click: Resolume, the sensing
# chain on the shed camera, the controller that fires clips, and the data wall.
#
# A desktop shortcut runs this file. Running it again restarts the sensing
# chain and the controller cleanly, and leaves Resolume as it is.
#   -Stop     closes the sensing chain and the controller, and nothing else.
#   -NoWall   does not open the data wall page.
#
# Each of the two programs gets its own window, titled "Cockaigne sensing" and
# "Cockaigne controller". The windows stay open if a program stops, so its
# last words can be read. See RUNBOOK.md, "The studio shed, one double-click".
param([switch]$Stop, [switch]$NoWall)

$repo        = $PSScriptRoot
$python      = Join-Path $repo ".venv\Scripts\python.exe"
$config      = "config/studio.yaml"
$arena       = "C:\Program Files\Resolume Arena\Arena.exe"
$composition = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Resolume Arena\Compositions\cockaigne_studio.avc"
$edge        = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$wallSpot    = "1.75,3.5"   # the viewing spot in config/studio.yaml, drawn on the wall's floor plan
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

function Start-Window($title, $module, $arguments) {
    $line = "title $title & `"$python`" -m $module $arguments"
    Start-Process cmd.exe -ArgumentList "/k", $line -WorkingDirectory $repo
}

$Host.UI.RawUI.WindowTitle = "Cockaigne start"
Set-Location $repo

if ($Stop) {
    $n = Stop-Ours
    Say "Stopped the sensing chain and the controller ($n processes). Resolume is untouched." "Green"
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
if (-not (Get-Process Arena -ErrorAction SilentlyContinue)) {
    if (-not (Test-Path $arena))       { Fail "Resolume Arena is missing at $arena" }
    if (-not (Test-Path $composition)) { Fail "The composition is missing at $composition" }
    Say "Starting Resolume with cockaigne_studio ..."
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
if ($clips -lt $minClips) { Fail "Resolume is open but layer 1 holds $clips clips. Load the cockaigne_studio composition, then double-click again." }
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
    if (Test-Path $edge) { Start-Process $edge -ArgumentList "--new-window", $wall }
    else { Start-Process $wall }
    Say "Data wall opened. Press F11 in it for full screen."
}

Say ""
Say "Running. One clip fires each minute; walk into the shed and the ring climbs." "Cyan"
Say "To stop: close the two Cockaigne windows, or use the 'Cockaigne STOP' shortcut."
Start-Sleep -Seconds 12
