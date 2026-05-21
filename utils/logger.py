import logging
import sys
from pathlib import Path

# Resolve project root (this file lives at <root>/utils/logger.py)
_LOG_FILE = Path(__file__).parent.parent / "sonicforge.log"

def setup_logger(name: str = "sonicforge") -> logging.Logger:
    """Configures and returns the main application logger."""
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist (guard against duplicate setup)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Console handler — INFO and above
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler — DEBUG and above, absolute path
        try:
            fh = logging.FileHandler(str(_LOG_FILE))
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception:
            pass  # Fallback to console-only if the file can't be created
            
    return logger

logger = setup_logger()
