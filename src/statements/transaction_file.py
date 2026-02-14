from abc import ABC, abstractmethod
from typing import Union, Optional
from io import BytesIO

import pandas as pd
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest
from openpyxl.utils.exceptions import InvalidFileException

from flask import current_app

from src.utils.logging import ContextLogger

logger = ContextLogger(__name__)


class TransactionFile(ABC):
   """Base class for processing uploaded transaction files."""

   def __init__(
       self,
       file: FileStorage,
       start_row: int = 0
   ):
       self.file = file
       self.file_content: Optional[bytes] = None
       self.file_stream: Optional[BytesIO] = None
       self.skip_rows = max(start_row - 1, 0)
       self.filename = secure_filename(file.filename) if file.filename else "unknown"

   def process_file(self) -> Union[pd.DataFrame, None]:
       """Extract and process the file content."""
       logger.debug(f"Processing file: {self.filename} (skip_rows={self.skip_rows})")
       self._extract_content()
       return self._process_content()

   def _extract_content(self) -> None:
       """Read file content into memory after validating size."""
       self.file.seek(0, 2)
       file_size = self.file.tell()
       self.file.seek(0)

       max_size = current_app.config.get("MAX_FILE_SIZE", 10 * 1024 * 1024)

       if file_size > max_size:
           logger.warning(
               f"File {self.filename} too large: "
               f"{file_size} bytes > {max_size} bytes"
           )
           raise RequestEntityTooLarge(
               f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)"
           )

       try:
           self.file_content = self.file.read()
           self.file_stream = BytesIO(self.file_content)
           self.file_stream.seek(0)
           logger.debug(f"Read {file_size} bytes from {self.filename}")
       except Exception as e:
           logger.error(f"Failed to read file {self.filename}: {e}")
           raise

   @abstractmethod
   def _process_content(self) -> Union[pd.DataFrame, None]:
       """Process the file content into a DataFrame."""
       pass


class TransactionCsvFile(TransactionFile):
   """Processes CSV transaction files."""

   ENCODINGS = ['utf-8', 'Windows-1252', 'latin-1']

   def _process_content(self) -> Union[pd.DataFrame, None]:
       """Parse CSV with automatic encoding detection."""
       for encoding in self.ENCODINGS:
           self.file_stream.seek(0)
           try:
               df = pd.read_csv(
                   self.file_stream,
                   skiprows=self.skip_rows,
                   header=0,
                   encoding=encoding
               )
               logger.info(
                   f"Processed CSV {self.filename}: {len(df)} rows "
                   f"(encoding={encoding})"
               )
               return df

           except UnicodeDecodeError:
               logger.debug(
                   f"Encoding {encoding} failed for {self.filename}, "
                   f"trying next"
               )
               continue
           except pd.errors.EmptyDataError:
               logger.warning(f"CSV file is empty: {self.filename}")
               raise BadRequest("CSV file is empty.")
           except pd.errors.ParserError as e:
               logger.error(f"CSV parse error for {self.filename}: {e}")
               raise BadRequest(f"CSV parsing error: {e}")

       logger.error(
           f"Could not decode {self.filename} with any supported encoding "
           f"({', '.join(self.ENCODINGS)})"
       )
       raise BadRequest("Could not decode CSV with any supported encoding")


class TransactionExcelFile(TransactionFile):
   """Processes Excel transaction files (.xls, .xlsx)."""

   def _process_content(self) -> Union[pd.DataFrame, None]:
       """Parse Excel file, falling back to xlrd for older formats."""
       self.file_stream.seek(0)

       # Try openpyxl first (for .xlsx)
       try:
           df = pd.read_excel(
               self.file_stream,
               skiprows=self.skip_rows,
               header=0,
               engine='openpyxl'
           )
           logger.info(
               f"Processed Excel {self.filename}: {len(df)} rows "
               f"(engine=openpyxl)"
           )
           return df

       except InvalidFileException:
           logger.debug(
               f"openpyxl failed for {self.filename}, trying xlrd"
           )
           self.file_stream.seek(0)

           # Fallback to xlrd (for .xls)
           try:
               df = pd.read_excel(
                   self.file_stream,
                   skiprows=self.skip_rows,
                   header=0,
                   engine='xlrd'
               )
               logger.info(
                   f"Processed Excel {self.filename}: {len(df)} rows "
                   f"(engine=xlrd)"
               )
               return df

           except ImportError:
               logger.error(
                   f"xlrd not installed, cannot process {self.filename}"
               )
               raise BadRequest(
                   "xlrd engine is not installed. Please install it to "
                   "process .xls files or convert file to .xlsx."
               )
           except Exception as e:
               logger.error(
                   f"xlrd failed for {self.filename}: {e}"
               )
               raise BadRequest(f"Error processing Excel content: {e}")

       except Exception as e:
           logger.error(f"Failed to process Excel {self.filename}: {e}")
           raise BadRequest(f"Error processing Excel content: {e}")


def get_transaction_file_processor(
   file: FileStorage,
   start_row: int = 0
) -> TransactionFile:
   """
   Factory function to get the appropriate file processor.
   
   Args:
       file: Uploaded file
       start_row: Row number to start reading from (1-indexed)
       
   Returns:
       Appropriate TransactionFile subclass instance
   """
   filename = secure_filename(file.filename)
   file_ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

   logger.debug(f"Creating processor for {filename} (extension={file_ext})")

   if file_ext == 'csv':
       return TransactionCsvFile(file, start_row)
   elif file_ext in ('xls', 'xlsx'):
       return TransactionExcelFile(file, start_row)
   else:
       logger.warning(f"Unsupported file extension: {file_ext}")
       raise BadRequest(f"Unsupported file extension: {file_ext}")