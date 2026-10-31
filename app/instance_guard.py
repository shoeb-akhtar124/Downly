"""
Single Instance Guard Module.
Ensures that only one instance of Downly can run simultaneously on Windows.
If an instance is already running, brings the existing window to the foreground.
"""
import ctypes
from ctypes import wintypes
import sys
from typing import Optional

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
MUTEX_NAME = "Local\\Downly_Universal_Video_Downloader_SingleInstance"


class SingleInstanceGuard:
    """Windows Named Mutex wrapper for single application instance control."""

    def __init__(self, mutex_name: str = MUTEX_NAME):
        self.mutex_name = mutex_name
        self.mutex_handle: Optional[int] = None

    def acquire(self) -> bool:
        """
        Attempt to acquire unique application mutex.
        Returns True if this is the only active instance.
        Returns False if another instance is already running.
        """
        if sys.platform != "win32":
            return True

        if self.mutex_handle is not None:
            # Already acquired by current process
            return True

        kernel32 = ctypes.windll.kernel32
        self.mutex_handle = kernel32.CreateMutexW(None, True, self.mutex_name)
        last_error = kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            self.bring_existing_to_front()
            if self.mutex_handle:
                kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
            return False

        return True

    def bring_existing_to_front(self) -> bool:
        """Locate existing Downly application window and bring it to foreground."""
        if sys.platform != "win32":
            return False

        user32 = ctypes.windll.user32
        found_hwnd = None

        def enum_window_callback(hwnd, extra):
            nonlocal found_hwnd
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title.startswith("Downly"):
                        found_hwnd = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_window_callback), 0)

        if found_hwnd:
            user32.ShowWindow(found_hwnd, SW_RESTORE)
            user32.SetForegroundWindow(found_hwnd)
            return True

        return False

    def release(self) -> None:
        """Release mutex on application exit."""
        if sys.platform == "win32" and self.mutex_handle:
            ctypes.windll.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None


# Global instance
single_instance_guard = SingleInstanceGuard()

