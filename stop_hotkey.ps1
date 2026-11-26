# The stop key. start_studio.ps1 starts this file, hidden, each time the show
# starts. It claims Ctrl+Alt+S from Windows for itself, waits for that key, and
# then runs "start_studio.ps1 -Stop -All", which closes the whole show.
#
# Why it exists: the key used to live on the Cockaigne STOP desktop shortcut.
# Windows hands shortcut keys to the desktop program (Explorer), which ignored
# the key on 27 Nov 2026 while the show covered the screens. A key claimed here
# with RegisterHotKey reaches this program whatever window is in front.
#
# If the key cannot be claimed (another program holds it), the reason is
# written to stop_hotkey.log beside this file; the STOP shortcut still works.

$repo = $PSScriptRoot
$log  = Join-Path $repo "stop_hotkey.log"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class StopKey {
    [StructLayout(LayoutKind.Sequential)]
    public struct MSG { public IntPtr hwnd; public uint message; public UIntPtr wParam; public IntPtr lParam; public uint time; public int x; public int y; }
    [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterHotKey(IntPtr hWnd, int id, uint mods, uint key);
    [DllImport("user32.dll")] static extern int GetMessage(out MSG msg, IntPtr hWnd, uint min, uint max);

    // Ctrl (2) + Alt (1), no auto-repeat (0x4000), the S key (0x53).
    // Returns 0 once the key is pressed, or the Windows error number if the key could not be claimed.
    public static int Wait() {
        if (!RegisterHotKey(IntPtr.Zero, 1, 0x4003, 0x53)) return Marshal.GetLastWin32Error();
        MSG msg;
        while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0) {
            if (msg.message == 0x0312) return 0;   // 0x0312 is the "hot key pressed" message
        }
        return -1;
    }
}
"@

$result = [StopKey]::Wait()
if ($result -ne 0) {
    "$(Get-Date -Format s)  Could not claim Ctrl+Alt+S (Windows error $result)." | Add-Content $log
    exit 1
}
"$(Get-Date -Format s)  Ctrl+Alt+S pressed; stopping the show." | Add-Content $log
Start-Process powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$(Join-Path $repo 'start_studio.ps1')`"", "-Stop", "-All" -WorkingDirectory $repo
