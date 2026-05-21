"""Centralised project path constants."""
from pathlib import Path

# Absolute path to the project root (parent of this utils/ directory)
PROJECT_ROOT: Path = Path(__file__).parent.parent

# Hidden cache directory for temporary files (e.g. artwork previews)
CACHE_DIR: Path = PROJECT_ROOT / ".cache"
