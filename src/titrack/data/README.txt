TITrack - Torchlight Infinite Loot Tracker
==========================================

FIRST TIME SETUP
----------------
If you downloaded this as a ZIP file, you may need to "unblock" it before
the application will run properly:

1. Right-click the downloaded ZIP file (before extracting)
2. Click "Properties"
3. At the bottom, check "Unblock"
4. Click "OK"
5. Now extract the ZIP and run TITrack.exe

REQUIREMENTS
------------
TITrack runs in a native window by default. This requires:

- Windows 10 or 11
- WebView2 Runtime (pre-installed on Windows 11 and recent Windows 10)

If the app doesn't open or shows a blank window:

1. Install WebView2 Runtime:
   https://go.microsoft.com/fwlink/p/?LinkId=2124703

2. If that doesn't help, install .NET 6 Desktop Runtime (x64):
   https://dotnet.microsoft.com/download/dotnet/6.0

BROWSER MODE (FALLBACK)
-----------------------
If native window mode doesn't work on your system, you can run in browser mode:

1. Open Command Prompt in the TITrack folder
2. Run: TITrack.exe serve --no-window
3. Your default browser will open to the dashboard

Or create a shortcut:
- Right-click TITrack.exe -> Create shortcut
- Right-click the shortcut -> Properties
- In "Target", add: serve --no-window
- Example: "C:\path\to\TITrack.exe" serve --no-window

USAGE
-----
1. Run TITrack.exe
2. If prompted, select your Torchlight Infinite game folder
3. Start Torchlight Infinite and log into a character
4. TITrack will automatically track your loot!

To sync your existing inventory, open your in-game bag and click the
Sort button - this updates TITrack with your current items.

MORE INFO
---------
GitHub: https://github.com/astockman99/TITrack
