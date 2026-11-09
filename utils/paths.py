"""Centralised project path constants and environment setup."""
import os
import sys
import tempfile
from pathlib import Path

# Ensure bundled binaries (e.g. packaged ffmpeg) and Homebrew/local binaries are on PATH
if sys.platform == "darwin":
    extra_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        extra_paths = [
            str(exe_dir),
            str(meipass),
            str(exe_dir.parent / "Frameworks"),
            str(exe_dir.parent / "Resources"),
        ] + extra_paths
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    for p in reversed(extra_paths):
        if p not in path_parts:
            path_parts.insert(0, p)
    os.environ["PATH"] = os.pathsep.join(path_parts)

# Absolute path to the project root (parent of this utils/ directory)
PROJECT_ROOT: Path = Path(__file__).parent.parent


def _resolve_writable_dir() -> Path:
    """Returns a writable directory for cache and logs (handles read-only .app bundles)."""
    if getattr(sys, "frozen", False) or not os.access(PROJECT_ROOT, os.W_OK):
        if sys.platform == "darwin":
            base = Path.home() / "Library" / "Caches" / "SonicForge"
        else:
            base = Path(tempfile.gettempdir()) / "SonicForge"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return PROJECT_ROOT


_WRITABLE_ROOT: Path = _resolve_writable_dir()

# Hidden cache directory for temporary files (e.g. artwork previews)
CACHE_DIR: Path = _WRITABLE_ROOT / ".cache"
LOG_FILE: Path = _WRITABLE_ROOT / "sonicforge.log"


def configure_macos_flet_client() -> None:
    """Ensures Flet on macOS uses a branded SonicForge.app client (icon + menu bar name)."""
    if sys.platform != "darwin" or os.environ.get("FLET_VIEW_PATH"):
        return

    # 1. Check if pre-bundled inside SonicForge.app/Contents/Resources/flet_client
    exe_dir = Path(sys.executable).resolve().parent
    bundled_client_dir = exe_dir.parent / "Resources" / "flet_client"
    if (bundled_client_dir / "SonicForge.app").exists():
        os.environ["FLET_VIEW_PATH"] = str(bundled_client_dir)
        return

    # 2. Prepare branded client in user cache for dev/source runs
    try:
        import plistlib
        import shutil
        import subprocess
        import flet_desktop
        import flet_desktop.version

        ver = getattr(flet_desktop.version, "version", "0.85.1")
        branded_dir = Path.home() / "Library" / "Caches" / "SonicForge" / f"flet-client-{ver}"
        branded_app = branded_dir / "SonicForge.app"
        icon_src = PROJECT_ROOT / "assets" / "icon.icns"

        if not branded_app.exists():
            base_cache = flet_desktop.ensure_client_cached()
            src_app = None
            for entry in os.listdir(base_cache):
                if entry.endswith(".app"):
                    src_app = Path(base_cache) / entry
                    break
            if not src_app:
                return

            branded_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_app, branded_app, symlinks=True, dirs_exist_ok=True)

            # Replace icon and remove Assets.car so pink/blue Flet icon is never used
            res_dir = branded_app / "Contents" / "Resources"
            if icon_src.exists():
                shutil.copy2(icon_src, res_dir / "AppIcon.icns")
            assets_car = res_dir / "Assets.car"
            if assets_car.exists():
                assets_car.unlink()

            # Update Info.plist with SonicForge name and icon
            plist_path = branded_app / "Contents" / "Info.plist"
            if plist_path.exists():
                with open(plist_path, "rb") as fp:
                    pl = plistlib.load(fp)
                pl["CFBundleName"] = "SonicForge"
                pl["CFBundleDisplayName"] = "SonicForge"
                pl["CFBundleIdentifier"] = "com.sonicforge.client"
                pl["CFBundleIconFile"] = "AppIcon.icns"
                pl.pop("CFBundleIconName", None)
                with open(plist_path, "wb") as fp:
                    plistlib.dump(pl, fp)

            subprocess.run(
                ["codesign", "-s", "-", "--force", "--all-architectures", "--timestamp", "--deep", str(branded_app)],
                capture_output=True,
            )

        os.environ["FLET_VIEW_PATH"] = str(branded_dir)
    except Exception:
        pass


