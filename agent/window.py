"""Scoped Win32 topmost state for the uniquely identified game window."""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager

def find_game_windows(user32):
    """Toolkit enumeration is unavailable inside Maa's out-of-process Agent."""
    handles = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    @callback_type
    def collect(hwnd, _):
        title = ctypes.create_unicode_buffer(256)
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, len(title))
        user32.GetClassNameW(hwnd, class_name, len(class_name))
        if title.value == "AzurPromilia" and class_name.value == "UnityWndClass":
            handles.append(hwnd)
        return True

    if not user32.EnumWindows(collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return handles


@contextmanager
def game_on_top(enabled=True):
    if not enabled:
        yield
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    windows = find_game_windows(user32)
    if len(windows) != 1:
        raise RuntimeError("自动置顶需要唯一的 AzurPromilia 游戏窗口")
    hwnd = windows[0]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    was_topmost = bool(user32.GetWindowLongW(hwnd, -20) & 0x00000008)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # HWND_TOPMOST; preserve size/position. Maa Seize handles input focus.
    if not user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not was_topmost and user32.IsWindow(hwnd):
            if not user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010):
                print("无法恢复游戏窗口置顶状态，请手动检查。", flush=True)
