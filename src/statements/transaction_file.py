from abc import ABC, abstractmethod
from typing import Union, Optional
from pathlib import Path
from io import BytesIO
import logging

import pandas as pd
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest
from openpyxl.utils.exceptions import InvalidFileException

from flask import current_app

logger = logging.getLogger(__name__)

class TransactionFile(ABC):
    def __init__(self,
                 file: FileStorage,
                 start_row: int = 0
                 ):
        self.file = file
        self.file_content: Optional[bytes] = None
        self.file_stream: Optional[BytesIO] = None
        self.skip_rows = max(start_row - 1, 0)

    def process_file(self) -> Union[pd.DataFrame, None]:
        self._extract_content()
        return self._process_content()

    def _extract_content(self) -> None:
        
        self.file.seek(0, 2)
        file_size = self.file.tell()
        self.file.seek(0)
        
        max_size = current_app.config.get("MAX_FILE_SIZE", 10 * 1024 * 1024)
        
        if file_size > max_size:
            raise RequestEntityTooLarge(
                f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)"
            )
        
        try:
            self.file_content = self.file.read()
            self.file_stream = BytesIO(self.file_content)
            self.file_stream.seek(0)
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            raise

    @abstractmethod
    def _process_content(self) -> Union[pd.DataFrame, None]:
        pass

class TransactionCsvFile(TransactionFile):
    def _process_content(self) -> Union[pd.DataFrame, None]:
        encodings = ['utf-8', 'Windows-1252', 'latin-1']
        for encoding in encodings:
            self.file_stream.seek(0)
            try:
                df = pd.read_csv(
                    self.file_stream,
                    skiprows=self.skip_rows,
                    header=0,
                    encoding=encoding
                )
                logger.info(
                    f"CSV file processed successfully with {len(df)} rows using "
                    f"{encoding} encoding."
                    )
                return df
            except UnicodeDecodeError:
                logger.info(f"{encoding} decode failed, trying next encoding.")
                continue
            except pd.errors.EmptyDataError:
                logger.error("CSV file is empty.")
                raise BadRequest("CSV file is empty.")
            except pd.errors.ParserError as e:
                logger.error(f"CSV parsing error with {encoding} encoding: {e}")
                raise BadRequest(f"CSV parsing error: {e}")
        logger.error("Could not decode CSV with any supported encoding")
        raise BadRequest("Could not decode CSV with any supported encoding")
    
class TransactionExcelFile(TransactionFile):
    def _process_content(self) -> Union[pd.DataFrame, None]:
        self.file_stream.seek(0)
        try:
            df = pd.read_excel(
                self.file_stream,
                skiprows=self.skip_rows,
                header=0,
                engine='openpyxl'
                )
        except InvalidFileException as e:
            self.file_stream.seek(0)
            logger.info("openpyxl engine failed, trying xlrd engine")
            try:
                df = pd.read_excel(
                    self.file_stream,
                    skiprows=self.skip_rows,
                    header=0,
                    engine='xlrd'
                    )
            except ImportError:
                logger.error(
                    f"Error processing Excel content with xlrd engine: {e}"
                    )
                raise BadRequest(
                    "xlrd engine is not installed. Please install it to "
                    "process .xls files or convert file to .xlsx."
                    )
            except Exception as xlrd_e:
                logger.error(
                    f"Error processing Excel content with xlrd engine: {xlrd_e}"
                    )
                raise BadRequest(f"Error processing Excel content: {xlrd_e}")
        except Exception as e:
            logger.error(f"Error processing Excel content: {e}")
            raise BadRequest(f"Error processing Excel content: {e}")
        logger.info(f"Excel file processed successfully with {len(df)} rows.")
        return df
    
def get_transaction_file_processor(
    file: FileStorage,
    start_row: int = 0
    ) -> TransactionFile:
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower()
    
    if file_ext == 'csv':
        return TransactionCsvFile(file, start_row)
    elif file_ext in ['xls', 'xlsx']:
        return TransactionExcelFile(file, start_row)
    else:
        logger.error(f"Unsupported file extension: {file_ext}")
        raise BadRequest(f"Unsupported file extension: {file_ext}")
        
