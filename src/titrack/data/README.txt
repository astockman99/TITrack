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

If WebView2 is not available, TITrack will show a message with a download
link and automatically open in your default browser instead. Browser mode
works identically to native window mode.

To install WebView2 Runtime manually:
   https://developer.microsoft.com/en-us/microsoft-edge/webview2/

BROWSER MODE (FALLBACK)
-----------------------
You can also force browser mode manually:

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
3. In Torchlight Infinite, go to Settings and click "Enable Log"
4. Log out to the character select screen, then log back in
   IMPORTANT: Do NOT close the game - just log out and back in!
5. TITrack will detect your character and start tracking loot

To sync your existing inventory, open your in-game bag and click the
Sort button - this updates TITrack with your current items.

MORE INFO
---------
GitHub: https://github.com/astockman99/TITrack
