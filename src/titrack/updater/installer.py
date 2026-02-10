"""Update installer - download and apply updates."""

import os
import shutil
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

from titrack.config.paths import get_app_dir, is_frozen


class UpdateInstaller:
    """Downloads and installs updates."""

    def __init__(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """
        Initialize installer.

        Args:
            on_progress: Callback for download progress (bytes_downloaded, total_bytes)
        """
        self._on_progress = on_progress
        self._download_path: Optional[Path] = None

    def download_update(
        self,
        download_url: str,
        expected_size: Optional[int] = None,
    ) -> Optional[Path]:
        """
        Download update ZIP file to temp directory.

        Args:
            download_url: URL to download from
            expected_size: Expected file size in bytes (for progress)

        Returns:
            Path to downloaded file, or None on failure
        """
        try:
            # Create temp directory for download
            temp_dir = Path(tempfile.gettempdir()) / "titrack_update"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Extract filename from URL
            filename = download_url.split("/")[-1]
            if not filename.endswith(".zip"):
                filename = "TITrack-update.zip"

            download_path = temp_dir / filename

            # Download with progress
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "TITrack-Updater"},
            )

            with urllib.request.urlopen(req, timeout=300) as response:
                total_size = expected_size or int(
                    response.headers.get("Content-Length", 0)
                )
                downloaded = 0
                chunk_size = 8192

                with open(download_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if self._on_progress:
                            self._on_progress(downloaded, total_size)

            self._download_path = download_path
            return download_path

        except urllib.error.HTTPError as e:
            print(f"Download error: {e.code} {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"Network error: {e.reason}")
            return None
        except Exception as e:
            print(f"Unexpected download error: {e}")
            return None

    def prepare_update(self, zip_path: Path) -> Optional[Path]:
        """
        Extract update ZIP and prepare for installation.

        Args:
            zip_path: Path to downloaded ZIP file

        Returns:
            Path to extracted update directory, or None on failure
        """
        try:
            import zipfile

            extract_dir = zip_path.parent / "extracted"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            # Find the TITrack directory inside extracted
            for item in extract_dir.iterdir():
                if item.is_dir() and "titrack" in item.name.lower():
                    return item

            # If no TITrack subdir, use extract_dir itself
            return extract_dir

        except Exception as e:
            print(f"Extract error: {e}")
            return None

    def create_update_script(self, update_dir: Path) -> Optional[Path]:
        """
        Create a batch script to apply the update and restart.

        The script:
        1. Waits for TITrack.exe to exit
        2. Copies new files over old
        3. Restarts TITrack.exe
        4. Cleans up temp files

        Args:
            update_dir: Path to extracted update files

        Returns:
            Path to batch script, or None on failure
        """
        if not is_frozen():
            print("Update scripts only work in frozen mode")
            return None

        app_dir = get_app_dir()
        exe_path = app_dir / "TITrack.exe"
        script_path = update_dir.parent / "update.bat"

        script_content = f'''@echo off
REM TITrack Update Script
REM Auto-generated - do not edit

echo Waiting for TITrack to close...
:waitloop
tasklist /FI "IMAGENAME eq TITrack.exe" 2>NUL | find /I /N "TITrack.exe">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto waitloop
)

REM Kill overlay if still running (it file-locks TITrackOverlay.exe)
tasklist /FI "IMAGENAME eq TITrackOverlay.exe" 2>NUL | find /I /N "TITrackOverlay.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Closing overlay...
    taskkill /IM TITrackOverlay.exe >nul 2>&1
)

:waitoverlay
tasklist /FI "IMAGENAME eq TITrackOverlay.exe" 2>NUL | find /I /N "TITrackOverlay.exe">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto waitoverlay
)

echo Applying update...
timeout /t 2 /nobreak >nul

REM Verify TITrack.exe is unlocked before copying (Windows can hold locks briefly after exit)
set RETRY=0
:waitunlock
set /a RETRY+=1
ren "{app_dir}\\TITrack.exe" "TITrack.exe.old" >nul 2>&1
if errorlevel 1 (
    if %RETRY% LSS 10 (
        echo Waiting for file lock to release... (attempt %RETRY%)
        timeout /t 2 /nobreak >nul
        goto waitunlock
    )
    echo WARNING: Could not verify file unlock, attempting copy anyway...
) else (
    ren "{app_dir}\\TITrack.exe.old" "TITrack.exe" >nul 2>&1
)

REM Copy new files (preserve data directory)
xcopy /E /Y /I "{update_dir}\\*" "{app_dir}\\" >nul 2>&1

if errorlevel 1 (
    echo ERROR: Update failed!
    pause
    exit /b 1
)

echo Update complete!
echo Starting TITrack...

REM Start the updated app from its own directory
cd /d "{app_dir}"
start "" "{exe_path}"

REM Clean up temp files
timeout /t 5 /nobreak >nul
rmdir /s /q "{update_dir.parent}" >nul 2>&1

exit /b 0
'''

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            return script_path
        except Exception as e:
            print(f"Failed to create update script: {e}")
            return None

    def apply_update(self, script_path: Path) -> bool:
        """
        Execute the update script and exit current process.

        This will NOT return if successful - the process exits.

        Args:
            script_path: Path to update batch script

        Returns:
            False if execution failed (only returns on failure)
        """
        if not is_frozen():
            print("Cannot apply update in development mode")
            return False

        try:
            import subprocess

            # Kill overlay process before exiting so it doesn't file-lock
            # TITrackOverlay.exe and prevent the update from overwriting it
            subprocess.run(
                ["taskkill", "/IM", "TITrackOverlay.exe"],
                capture_output=True,
            )

            # Start the update script in a new process
            subprocess.Popen(
                ["cmd", "/c", str(script_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )

            # Exit current process to allow update
            # Use os._exit() instead of sys.exit() because sys.exit() raises
            # SystemExit which gets caught by FastAPI/uvicorn and doesn't
            # actually terminate the process
            print("Exiting for update...")
            os._exit(0)

        except Exception as e:
            print(f"Failed to start update: {e}")
            return False

    def cleanup(self) -> None:
        """Clean up any temporary download files."""
        if self._download_path and self._download_path.exists():
            try:
                temp_dir = self._download_path.parent
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Cleanup error: {e}")
