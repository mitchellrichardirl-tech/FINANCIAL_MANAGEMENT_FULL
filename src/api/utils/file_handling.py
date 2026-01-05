import os
import uuid
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set, Tuple, Union
from dataclasses import dataclass
from contextlib import contextmanager

from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import current_app

logger = logging.getLogger(__name__)

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

@dataclass
class FileValidationResult:
    """Result of file validation."""
    is_valid: bool
    original_filename: Optional[str] = None
    secured_filename: Optional[str] = None
    extension: Optional[str] = None
    error: Optional[str] = None


class FileHandler:
    """Handles file operations for uploads."""
    
    MIME_TYPES = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.pdf': 'application/pdf',
        '.webp': 'image/webp',
    }
    
    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        upload_folder: Optional[Path] = None,
        filename_prefix: str = "file"
    ):
        self.allowed_extensions = allowed_extensions
        self.upload_folder = upload_folder
        self.filename_prefix = filename_prefix
    
    @classmethod
    def from_app_config(cls, prefix: str = "file") -> 'FileHandler':
        """Create FileHandler from Flask app configuration."""
        return cls(
            allowed_extensions=set(current_app.config.get(
                'ALLOWED_EXTENSIONS', 
                {'png', 'jpg', 'jpeg', 'pdf'}
            )),
            upload_folder=Path(current_app.config.get('UPLOAD_FOLDER', 'uploads')),
            filename_prefix=prefix
        )
    
    def validate_file(self, file: FileStorage) -> FileValidationResult:
        """Validate an uploaded file."""
        if file is None or file.filename == '':
            return FileValidationResult(is_valid=False, error="No file provided")
        
        original_filename = file.filename
        logger.debug(f"Original filename: {original_filename}")
        secured = secure_filename(original_filename)
        logger.debug(f"Secured filename: {secured}")
        if not secured:
            return FileValidationResult(is_valid=False, error="Invalid filename")
        
        extension = Path(secured).suffix.lower()
        
        logger.debug(f"File extension: {extension}")
        if self.allowed_extensions and extension.lstrip('.') not in self.allowed_extensions:
            allowed = ', '.join(sorted(self.allowed_extensions))
            return FileValidationResult(
                is_valid=False,
                error=f"Invalid file type. Allowed types: {allowed}"
            )
        
        return FileValidationResult(
            is_valid=True,
            original_filename=original_filename,
            secured_filename=secured,
            extension=extension
        )
    
    def generate_stored_filename(self, original_filename: str) -> str:
        """Generate a unique filename for storage."""
        ext = Path(original_filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{self.filename_prefix}_{timestamp}_{unique_id}{ext}"
    
    def get_mime_type(self, filename: Union[str, Path]) -> str:
        """Get MIME type for a file based on extension."""
        ext = Path(filename).suffix.lower()
        return self.MIME_TYPES.get(ext, 'application/octet-stream')
    
    def ensure_upload_folder(self) -> Path:
        """Ensure upload folder exists and return its path."""
        if self.upload_folder:
            self.upload_folder.mkdir(parents=True, exist_ok=True)
            return self.upload_folder
        raise ValueError("Upload folder not configured")
    
    def move_to_permanent(self, temp_path: Path, stored_filename: str) -> Path:
        """Move file from temp location to permanent storage."""
        permanent_path = self.ensure_upload_folder() / stored_filename
        shutil.copy2(temp_path, permanent_path)
        return permanent_path
    
    def delete_file(self, path: Union[str, Path]) -> bool:
        """Safely delete a file."""
        try:
            path = Path(path)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete file {path}: {e}")
            return False
    
    def is_safe_filename(self, filename: str) -> bool:
        """Check if filename is safe (no directory traversal)."""
        return not any(c in filename for c in ['..', '/', '\\'])


class TempFileManager:
    """Manages multiple temporary files with cleanup."""
    
    def __init__(self):
        self.temp_files: list[Path] = []
    
    def create_temp_file(self, suffix: str = "") -> Path:
        """Create a new temporary file and track it."""
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        temp_path = Path(temp_path)
        self.temp_files.append(temp_path)
        return temp_path
    
    def save_file_to_temp(self, file: FileStorage, suffix: str = "") -> Path:
        """Save an uploaded file to a temp location."""
        temp_path = self.create_temp_file(suffix)
        file.save(temp_path)
        return temp_path
    
    def cleanup(self):
        """Clean up all tracked temporary files."""
        for temp_path in self.temp_files:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
        self.temp_files.clear()
    
    def __enter__(self) -> 'TempFileManager':
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False