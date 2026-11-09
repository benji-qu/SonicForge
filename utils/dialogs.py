"""Shared native file and directory selection dialogs."""
import subprocess
import sys
from typing import List, Optional, Tuple
from utils.logger import logger


def _escape_applescript(text: str) -> str:
    """Escapes double quotes and backslashes for safe AppleScript string interpolation."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def choose_directory(prompt: str = "Select Directory") -> str:
    """Opens a native directory selection dialog."""
    logger.debug(f"Opening directory dialog: {prompt}")
    if sys.platform == "darwin":
        try:
            safe_prompt = _escape_applescript(prompt)
            cmd = [
                "osascript",
                "-e",
                'tell app "System Events" to activate',
                "-e",
                f'tell app "System Events" to return POSIX path of (choose folder with prompt "{safe_prompt}")',
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            # User cancelled in AppleScript (returncode != 0)
            return ""
        except Exception as e:
            logger.debug(f"macOS choose_directory failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title=prompt)
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback choose_directory failed: {e}")
        return ""


def choose_file(
    prompt: str = "Select File",
    extensions: Optional[List[str]] = None,
    tk_filetypes: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Opens a native file selection dialog."""
    logger.debug(f"Opening file dialog: {prompt}")
    if sys.platform == "darwin":
        try:
            safe_prompt = _escape_applescript(prompt)
            type_str = ""
            if extensions:
                quoted_exts = ", ".join(f'"{_escape_applescript(ext)}"' for ext in extensions)
                type_str = f" of type {{{quoted_exts}}}"
            cmd = [
                "osascript",
                "-e",
                'tell app "System Events" to activate',
                "-e",
                f'tell app "System Events" to return POSIX path of (choose file with prompt "{safe_prompt}"{type_str})',
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            return ""
        except Exception as e:
            logger.debug(f"macOS choose_file failed: {e}")
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        if tk_filetypes is None:
            if extensions:
                ext_glob = " ".join(f"*.{ext}" for ext in extensions)
                tk_filetypes = [(f"{'/'.join(e.upper() for e in extensions)} Files", ext_glob)]
            else:
                tk_filetypes = [("All Files", "*.*")]
        path = filedialog.askopenfilename(title=prompt, filetypes=tk_filetypes)
        root.destroy()
        return path
    except Exception as e:
        logger.error(f"Fallback choose_file failed: {e}")
        return ""


def reveal_in_finder(path: str) -> None:
    """Opens the given directory (or reveals a file) in the native OS file manager."""
    import os

    if not path or not os.path.exists(path):
        logger.warning(f"Cannot reveal non-existent path: {path}")
        return

    try:
        if sys.platform == "darwin":
            if os.path.isfile(path):
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            if os.path.isfile(path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(os.path.normpath(path))
        else:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["xdg-open", target])
    except Exception as e:
        logger.error(f"Failed to open path in file manager ({path}): {e}")

