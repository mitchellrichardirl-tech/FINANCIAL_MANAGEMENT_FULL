import tempfile
import os
from pathlib import Path
from typing import Union
from werkzeug.utils import secure_filename


def save_upload_file(file) -> Path:
    """
    Save an uploaded file to a temporary location.
    
    Args:
        file: Werkzeug FileStorage object
        
    Returns:
        Path to saved file
    """
    # Get secure filename
    filename = secure_filename(file.filename)
    
    # Create temp file with original extension
    suffix = Path(filename).suffix
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    
    try:
        # Save file
        file.save(temp_path)
        os.close(fd)
        return Path(temp_path)
    except Exception:
        os.close(fd)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def cleanup_temp_file(file_path: Union[Path, str]):
    """
    Clean up a temporary file.
    
    Args:
        file_path: Path to file to delete
    """
    try:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass  # Silent cleanup