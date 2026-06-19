import os
import tempfile
import aiofiles
import logging
from fastapi import UploadFile

logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {'image/jpeg', 'image/jpg', 'image/png'}

def validate_file(file: UploadFile) -> bool:
    """Validate if the uploaded file type is supported."""
    return file.content_type in ALLOWED_EXTENSIONS

async def save_temp_file(file: UploadFile) -> str:
    """Save an uploaded file safely to the system's temporary directory."""
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    fd, path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        async with aiofiles.open(path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        return path
    except Exception as e:
        logger.error(f"Failed to save temp file: {e}")
        cleanup_temp_file(path)
        raise

def cleanup_temp_file(path: str):
    """Safely remove a temporary file."""
    if os.path.exists(path):
        try:
            os.remove(path)
            logger.debug(f"Cleaned up temp file: {path}")
        except Exception as e:
            logger.warning(f"Failed to remove temp file {path}: {e}")
