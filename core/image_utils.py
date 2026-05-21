import io
from PIL import Image as PILImage
from typing import Union

from utils.logger import logger

def crop_and_resize_image(img: PILImage.Image) -> bytes:
    """
    Crops an image to a square and resizes it to 500x500 pixels.
    Always converts the final image to a standard RGB JPEG format.
    
    Args:
        img: A PIL Image object.
        
    Returns:
        The raw bytes of the processed JPEG image.
    """
    logger.debug(f"Processing image: original size {img.size}")
    width, height = img.size
    if width != height:
        min_dim = min(width, height)
        left = (width - min_dim) / 2
        top = (height - min_dim) / 2
        right = (width + min_dim) / 2
        bottom = (height + min_dim) / 2
        img = img.crop((left, top, right, bottom))
    
    img = img.resize((500, 500), PILImage.Resampling.LANCZOS)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def process_local_image(path: str) -> bytes:
    """
    Reads an image from the local filesystem and processes it.
    
    Args:
        path: Path to the local image file.
        
    Returns:
        The raw bytes of the processed JPEG image.
    """
    logger.info(f"Loading local image from {path}")
    img = PILImage.open(path)
    return crop_and_resize_image(img)

def process_downloaded_image(img_bytes: bytes) -> bytes:
    """
    Processes an image loaded directly from raw network bytes.
    
    Args:
        img_bytes: Raw image bytes downloaded from a URL.
        
    Returns:
        The raw bytes of the processed JPEG image.
    """
    logger.debug("Processing downloaded image bytes.")
    img = PILImage.open(io.BytesIO(img_bytes))
    return crop_and_resize_image(img)
