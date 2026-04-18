import os
import uuid
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Set, Union
from dataclasses import dataclass

from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from flask import current_app

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


def save_upload_file(file) -> Path:
   """
   Save an uploaded file to a temporary location.
   
   Args:
       file: Werkzeug FileStorage object
       
   Returns:
       Path to saved file
   """
   filename = secure_filename(file.filename)
   suffix = Path(filename).suffix

   logger.debug(f"Saving upload to temp: {filename}")

   fd, temp_path = tempfile.mkstemp(suffix=suffix)

   try:
       file.save(temp_path)
       os.close(fd)
       logger.debug(f"Saved upload to: {temp_path}")
       return Path(temp_path)
   except Exception as e:
       os.close(fd)
       if os.path.exists(temp_path):
           os.unlink(temp_path)
       logger.error(f"Failed to save upload {filename}: {e}")
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
           logger.debug(f"Cleaned up temp file: {file_path}")
   except Exception as e:
       logger.warning(f"Failed to cleanup temp file {file_path}: {e}")


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
       allowed = set(current_app.config.get(
           'ALLOWED_EXTENSIONS',
           {'png', 'jpg', 'jpeg', 'pdf'}
       ))
       upload_folder = Path(current_app.config.get('UPLOAD_FOLDER', 'uploads'))

       logger.debug(
           f"Creating FileHandler from config: prefix={prefix}, "
           f"upload_folder={upload_folder}, allowed={allowed}"
       )

       return cls(
           allowed_extensions=allowed,
           upload_folder=upload_folder,
           filename_prefix=prefix
       )

   def validate_file(self, file: FileStorage) -> FileValidationResult:
       """Validate an uploaded file."""
       if file is None or file.filename == '':
           logger.debug("Validation failed: no file provided")
           return FileValidationResult(is_valid=False, error="No file provided")

       original_filename = file.filename
       secured = secure_filename(original_filename)

       if not secured:
           logger.warning(f"Validation failed: invalid filename '{original_filename}'")
           return FileValidationResult(is_valid=False, error="Invalid filename")

       extension = Path(secured).suffix.lower()

       if self.allowed_extensions and extension.lstrip('.') not in self.allowed_extensions:
           allowed = ', '.join(sorted(self.allowed_extensions))
           logger.debug(
               f"Validation failed: extension '{extension}' not in allowed ({allowed})"
           )
           return FileValidationResult(
               is_valid=False,
               error=f"Invalid file type. Allowed types: {allowed}"
           )

       logger.debug(f"Validation passed: {secured} ({extension})")
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
       stored = f"{self.filename_prefix}_{timestamp}_{unique_id}{ext}"

       logger.debug(f"Generated stored filename: {original_filename} -> {stored}")
       return stored

   def get_mime_type(self, filename: Union[str, Path]) -> str:
       """Get MIME type for a file based on extension."""
       ext = Path(filename).suffix.lower()
       mime_type = self.MIME_TYPES.get(ext, 'application/octet-stream')

       if mime_type == 'application/octet-stream':
           logger.debug(f"Unknown MIME type for extension '{ext}', using octet-stream")

       return mime_type

   def ensure_upload_folder(self) -> Path:
       """Ensure upload folder exists and return its path."""
       if self.upload_folder:
           if not self.upload_folder.exists():
               self.upload_folder.mkdir(parents=True, exist_ok=True)
               logger.info(f"Created upload folder: {self.upload_folder}")
           return self.upload_folder
       raise ValueError("Upload folder not configured")

   def move_to_permanent(self, temp_path: Path, stored_filename: str) -> Path:
       """Move file from temp location to permanent storage."""
       permanent_path = self.ensure_upload_folder() / stored_filename
       shutil.copy2(temp_path, permanent_path)

       logger.debug(f"Moved to permanent storage: {temp_path} -> {permanent_path}")
       return permanent_path

   def delete_file(self, path: Union[str, Path]) -> bool:
       """Safely delete a file."""
       try:
           path = Path(path)
           if path.exists():
               path.unlink()
               logger.info(f"Deleted file: {path}")
               return True
           logger.debug(f"File not found for deletion: {path}")
           return False
       except Exception as e:
           logger.warning(f"Failed to delete file {path}: {e}")
           return False

   def is_safe_filename(self, filename: str) -> bool:
       """Check if filename is safe (no directory traversal)."""
       is_safe = not any(c in filename for c in ['..', '/', '\\'])

       if not is_safe:
           logger.warning(f"Unsafe filename detected: {filename}")

       return is_safe


class TempFileManager:
   """Manages multiple temporary files with cleanup."""

   def __init__(self):
       self.temp_files: list[Path] = []
       logger.debug("Initialized TempFileManager")

   def create_temp_file(self, suffix: str = "") -> Path:
       """Create a new temporary file and track it."""
       fd, temp_path = tempfile.mkstemp(suffix=suffix)
       os.close(fd)
       temp_path = Path(temp_path)
       self.temp_files.append(temp_path)

       logger.debug(f"Created temp file: {temp_path}")
       return temp_path

   def save_file_to_temp(self, file: FileStorage, suffix: str = "") -> Path:
       """Save an uploaded file to a temp location."""
       temp_path = self.create_temp_file(suffix)
       file.save(temp_path)

       logger.debug(f"Saved {file.filename} to temp: {temp_path}")
       return temp_path

   def cleanup(self):
       """Clean up all tracked temporary files."""
       if not self.temp_files:
           return

       cleaned = 0
       failed = 0

       for temp_path in self.temp_files:
           if temp_path.exists():
               try:
                   temp_path.unlink()
                   cleaned += 1
               except Exception as e:
                   failed += 1
                   logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")

       logger.debug(f"TempFileManager cleanup: {cleaned} removed, {failed} failed")
       self.temp_files.clear()

   def __enter__(self) -> 'TempFileManager':
       return self

   def __exit__(self, exc_type, exc_val, exc_tb):
       self.cleanup()
       if exc_type is not None:
           logger.debug(
               f"TempFileManager exiting with exception: {exc_type.__name__}"
           )
       return False