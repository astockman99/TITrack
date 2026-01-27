"""Log tailer - incremental file reading with position tracking."""

import os
from pathlib import Path
from typing import Generator, Optional


class LogTailer:
    """
    Read log file incrementally, tracking position for resume.

    Handles:
    - Reading from last position
    - Log rotation detection (file shrinks or inode changes)
    - Yielding complete lines only
    """

    def __init__(self, file_path: Path) -> None:
        """
        Initialize log tailer.

        Args:
            file_path: Path to the log file
        """
        self.file_path = file_path
        self._position: int = 0
        self._file_size: int = 0
        self._partial_line: str = ""

    @property
    def position(self) -> int:
        """Current read position in file."""
        return self._position

    @property
    def file_size(self) -> int:
        """Last known file size."""
        return self._file_size

    def set_position(self, position: int, file_size: int) -> None:
        """
        Set position for resuming (e.g., from database).

        If file_size doesn't match current, position is reset to 0
        (log rotation detected).
        """
        current_size = self._get_file_size()
        if current_size is None:
            # File doesn't exist yet
            self._position = 0
            self._file_size = 0
        elif current_size < file_size:
            # File shrunk - rotation detected
            self._position = 0
            self._file_size = current_size
        elif position < 0 or position > 10_000_000_000:
            # Invalid position (corruption or overflow) - reset
            print(f"WARNING: Invalid log position {position}, resetting to 0")
            self._position = 0
            self._file_size = current_size
        elif position > current_size:
            # Position beyond current file - file may have been truncated/rotated
            self._position = 0
            self._file_size = current_size
        else:
            self._position = position
            self._file_size = file_size

    def _get_file_size(self) -> Optional[int]:
        """Get current file size, or None if file doesn't exist."""
        try:
            return os.path.getsize(self.file_path)
        except OSError:
            return None

    def read_new_lines(self) -> Generator[str, None, None]:
        """
        Read new lines from the log file.

        Yields complete lines only. Partial lines are buffered
        until a newline is received.

        Yields:
            Complete log lines (without trailing newline)
        """
        current_size = self._get_file_size()
        if current_size is None:
            return

        # Detect rotation
        if current_size < self._position:
            self._position = 0
            self._partial_line = ""

        if current_size <= self._position:
            return

        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._position)
                content = f.read(current_size - self._position)
                new_position = f.tell()
                # Sanity check: position should be non-negative and reasonable
                # (file may have grown since we checked size, so position > current_size is OK)
                MAX_REASONABLE_POS = 10_000_000_000  # 10GB sanity limit
                if new_position < 0 or new_position > MAX_REASONABLE_POS:
                    print(f"WARNING: f.tell() returned invalid position {new_position}, resetting")
                    new_position = current_size
                self._position = new_position
                self._file_size = current_size
        except (OSError, IOError):
            return

        if not content:
            return

        # Handle partial lines
        content = self._partial_line + content
        self._partial_line = ""

        lines = content.split("\n")

        # Last element is either empty (if content ended with \n)
        # or a partial line
        if content.endswith("\n"):
            lines = lines[:-1]  # Remove empty string after final \n
        else:
            self._partial_line = lines[-1]
            lines = lines[:-1]

        for line in lines:
            yield line

    def read_all_lines(self) -> Generator[str, None, None]:
        """
        Read all lines from the beginning of the file.

        Yields:
            All lines in the file
        """
        self._position = 0
        self._partial_line = ""
        yield from self.read_new_lines()

    def reset(self) -> None:
        """Reset position to start of file."""
        self._position = 0
        self._file_size = 0
        self._partial_line = ""
