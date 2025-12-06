import pytest
import json
import io


class TestValidateEndpoint:
    """Tests for POST /api/tabular/validate endpoint."""
    
    def test_validate_csv_success(self, client, sample_csv_bytes):
        """Test successful CSV validation."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'is_valid' in data
        assert data['is_valid'] is True
        assert data['file_type'] == 'csv'
        assert data['row_count'] == 5
        assert data['column_count'] == 5
    
    def test_validate_xlsx_success(self, client, sample_xlsx_bytes):
        """Test successful XLSX validation."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(sample_xlsx_bytes), 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['is_valid'] is True
        assert data['file_type'] == 'xlsx'
        assert data['row_count'] == 4
        assert data['column_count'] == 3
    
    def test_validate_tsv_success(self, client, sample_tsv_bytes):
        """Test successful TSV validation."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(sample_tsv_bytes), 'test.tsv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['is_valid'] is True
        assert data['file_type'] == 'tsv'
    
    def test_validate_no_file(self, client):
        """Test validation without file."""
        response = client.post(
            '/api/tabular/validate',
            data={},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'no file' in data['error'].lower()
    
    def test_validate_empty_filename(self, client):
        """Test validation with empty filename."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(b'test'), '')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_validate_with_min_rows(self, client, sample_csv_bytes):
        """Test validation with min_rows parameter."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'min_rows': '3'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_validate_min_rows_fail(self, client, sample_csv_bytes):
        """Test validation fails with insufficient rows."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'min_rows': '100'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is False
        assert len(data['errors']) > 0
    
    def test_validate_with_min_columns(self, client, sample_csv_bytes):
        """Test validation with min_columns parameter."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'min_columns': '3'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_validate_with_required_columns(self, client, sample_csv_bytes):
        """Test validation with required columns."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'required_columns': 'id,name,email'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_validate_required_columns_missing(self, client, sample_csv_bytes):
        """Test validation fails with missing required columns."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'required_columns': 'id,nonexistent_column'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is False
        assert any('missing' in e.lower() for e in data['errors'])
    
    def test_validate_excel_sheet_by_name(self, client, multi_sheet_xlsx_bytes):
        """Test validation of specific Excel sheet by name."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(multi_sheet_xlsx_bytes), 'test.xlsx'),
                'sheet_name': 'Data'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_validate_excel_sheet_by_index(self, client, multi_sheet_xlsx_bytes):
        """Test validation of specific Excel sheet by index."""
        response = client.post(
            '/api/tabular/validate',
            data={
                'file': (io.BytesIO(multi_sheet_xlsx_bytes), 'test.xlsx'),
                'sheet_name': '1'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_validate_returns_column_info(self, client, sample_csv_bytes):
        """Test that validation returns column information."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'columns' in data
        assert len(data['columns']) > 0
        
        # Check column structure
        col = data['columns'][0]
        assert 'name' in col
        assert 'data_type' in col
        assert 'nullable' in col
    
    def test_validate_returns_metadata(self, client, sample_csv_bytes):
        """Test that validation returns file metadata."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'file_name' in data
        assert 'file_path' in data
        assert 'file_size_bytes' in data
        assert 'detected_encoding' in data
        assert 'validated_at' in data


class TestPreviewEndpoint:
    """Tests for POST /api/tabular/preview endpoint."""
    
    def test_preview_csv_success(self, client, sample_csv_bytes):
        """Test successful CSV preview."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'success' in data
        assert data['success'] is True
        assert 'total_rows' in data
        assert 'columns' in data
        assert 'data' in data
    
    def test_preview_default_num_rows(self, client, sample_csv_bytes):
        """Test preview returns default number of rows."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        # Default is 10 rows, but file only has 5
        assert data['preview_row_count'] <= 10
        assert data['preview_row_count'] == min(data['total_rows'], 10)
    
    def test_preview_custom_num_rows(self, client, sample_csv_bytes):
        """Test preview with custom number of rows."""
        response = client.post(
            '/api/tabular/preview',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'num_rows': '3'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['preview_row_count'] <= 3
        assert len(data['data']) <= 3
    
    def test_preview_with_types(self, client, sample_csv_bytes):
        """Test preview includes column types."""
        response = client.post(
            '/api/tabular/preview',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'include_types': 'true'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'column_types' in data
        assert len(data['column_types']) > 0
    
    def test_preview_without_types(self, client, sample_csv_bytes):
        """Test preview without column types."""
        response = client.post(
            '/api/tabular/preview',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'include_types': 'false'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['column_types'] == {}
    
    def test_preview_xlsx_specific_sheet(self, client, multi_sheet_xlsx_bytes):
        """Test preview of specific Excel sheet."""
        response = client.post(
            '/api/tabular/preview',
            data={
                'file': (io.BytesIO(multi_sheet_xlsx_bytes), 'test.xlsx'),
                'sheet_name': 'People'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert 'name' in data['columns']
    
    def test_preview_no_file(self, client):
        """Test preview without file."""
        response = client.post(
            '/api/tabular/preview',
            data={},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
    
    def test_preview_data_structure(self, client, sample_csv_bytes):
        """Test preview data has correct structure."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert isinstance(data['data'], list)
        
        if data['data']:
            first_record = data['data'][0]
            assert isinstance(first_record, dict)
            # Keys should match column names
            assert set(first_record.keys()).issubset(set(data['columns']))
    
    def test_preview_returns_metadata(self, client, sample_csv_bytes):
        """Test preview returns metadata."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'file_name' in data
        assert 'file_type' in data
        assert 'total_rows' in data
        assert 'total_columns' in data
        assert 'generated_at' in data


class TestImportEndpoint:
    """Tests for POST /api/tabular/import endpoint."""
    
    def test_import_csv_success(self, client, sample_csv_bytes):
        """Test successful CSV import."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'success' in data
        assert data['success'] is True
        assert 'rows_imported' in data
        assert 'columns_imported' in data
        assert 'data' in data
    
    def test_import_all_data_by_default(self, client, sample_csv_bytes):
        """Test import returns all data by default."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['rows_imported'] == 5
        assert len(data['data']) == 5
    
    def test_import_with_start_row(self, client, sample_csv_bytes):
        """Test import with start_row parameter."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'start_row': '2'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert data['start_row'] == 2
        assert data['rows_imported'] < 5
    
    def test_import_with_columns_by_index(self, client, sample_csv_bytes):
        """Test import with column selection by index."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'columns': '0,1,2'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert len(data['columns_imported']) == 3
        assert data['columns_requested'] == [0, 1, 2]
    
    def test_import_with_columns_by_name(self, client, sample_csv_bytes):
        """Test import with column selection by name."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'columns': 'id,name,email'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert len(data['columns_imported']) == 3
    
    def test_import_with_custom_column_names(self, client, sample_csv_bytes):
        """Test import with custom column names."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'column_names': 'user_id,user_name,user_email,user_age,user_score'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert 'user_id' in data['columns_imported']
        assert 'column_mapping' in data
    
    def test_import_without_header(self, client):
        """Test import without header."""
        csv_bytes = b"1,Alice,25\n2,Bob,30\n3,Charlie,35"
        
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(csv_bytes), 'test.csv'),
                'has_header': 'false'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert data['rows_imported'] == 3
    
    def test_import_with_max_rows(self, client, sample_csv_bytes):
        """Test import with max_rows limit."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'max_rows': '3'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['rows_imported'] <= 3
    
    def test_import_skip_empty_rows(self, client):
        """Test import skips empty rows."""
        csv_bytes = b"a,b,c\n1,2,3\n,,\n4,5,6\n,,"
        
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(csv_bytes), 'test.csv'),
                'skip_empty_rows': 'true'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert data['rows_skipped'] > 0
    
    def test_import_strip_whitespace(self, client):
        """Test import strips whitespace."""
        csv_bytes = b"name,code\n  Alice  ,  ABC123  \n  Bob  ,  XYZ789  "
        
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(csv_bytes), 'test.csv'),
                'strip_whitespace': 'true'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert data['data'][0]['name'] == 'Alice'
    
    def test_import_xlsx_specific_sheet(self, client, multi_sheet_xlsx_bytes):
        """Test import from specific Excel sheet."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(multi_sheet_xlsx_bytes), 'test.xlsx'),
                'sheet_name': 'Data'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert 'x' in data['columns_imported']
    
    def test_import_no_file(self, client):
        """Test import without file."""
        response = client.post(
            '/api/tabular/import',
            data={},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
    
    def test_import_combined_options(self, client, sample_csv_bytes):
        """Test import with multiple options."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(sample_csv_bytes), 'test.csv'),
                'start_row': '1',
                'columns': '0,1,2',
                'column_names': 'user_id,user_name,user_email',
                'max_rows': '3',
                'skip_empty_rows': 'true',
                'strip_whitespace': 'true'
            },
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        assert len(data['columns_imported']) == 3
        assert data['rows_imported'] <= 3
    
    def test_import_returns_metadata(self, client, sample_csv_bytes):
        """Test import returns metadata."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'file_name' in data
        assert 'file_type' in data
        assert 'imported_at' in data
    
    def test_import_data_is_json_serializable(self, client, sample_csv_bytes):
        """Test that imported data is JSON serializable."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        # Response should be valid JSON
        assert response.content_type == 'application/json'
        data = response.get_json()
        
        # Should be able to serialize again
        json_str = json.dumps(data)
        assert isinstance(json_str, str)


class TestGetSheetsEndpoint:
    """Tests for POST /api/tabular/sheets endpoint."""
    
    def test_get_sheets_xlsx(self, client, multi_sheet_xlsx_bytes):
        """Test getting sheets from XLSX file."""
        response = client.post(
            '/api/tabular/sheets',
            data={'file': (io.BytesIO(multi_sheet_xlsx_bytes), 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'sheet_names' in data
        assert 'sheet_count' in data
        assert data['sheet_count'] == 3
        assert 'Sheet1' in data['sheet_names']
        assert 'Data' in data['sheet_names']
        assert 'People' in data['sheet_names']
    
    def test_get_sheets_single_sheet(self, client, sample_xlsx_bytes):
        """Test getting sheets from single-sheet file."""
        response = client.post(
            '/api/tabular/sheets',
            data={'file': (io.BytesIO(sample_xlsx_bytes), 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['sheet_count'] == 1
        assert len(data['sheet_names']) == 1
    
    def test_get_sheets_csv_file(self, client, sample_csv_bytes):
        """Test getting sheets from non-Excel file."""
        response = client.post(
            '/api/tabular/sheets',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['sheet_count'] == 0
        assert data['sheet_names'] == []
    
    def test_get_sheets_no_file(self, client):
        """Test sheets endpoint without file."""
        response = client.post(
            '/api/tabular/sheets',
            data={},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
    
    def test_get_sheets_returns_filename(self, client, sample_xlsx_bytes):
        """Test sheets endpoint returns temp filename."""
        response = client.post(
            '/api/tabular/sheets',
            data={'file': (io.BytesIO(sample_xlsx_bytes), 'myfile.xlsx')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'file_name' in data
        assert '.xlsx' in data['file_name']


class TestCheckTabularEndpoint:
    """Tests for POST /api/tabular/check endpoint."""
    
    def test_check_csv_valid(self, client, sample_csv_bytes):
        """Test checking valid CSV file."""
        response = client.post(
            '/api/tabular/check',
            data={'file': (io.BytesIO(sample_csv_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert 'is_tabular' in data
        assert data['is_tabular'] is True
        assert 'file_name' in data
    
    def test_check_xlsx_valid(self, client, sample_xlsx_bytes):
        """Test checking valid XLSX file."""
        response = client.post(
            '/api/tabular/check',
            data={'file': (io.BytesIO(sample_xlsx_bytes), 'test.xlsx')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['is_tabular'] is True
    
    def test_check_invalid_file(self, client):
        """Test checking invalid file."""
        invalid_bytes = b"This is not a tabular file"
        
        response = client.post(
            '/api/tabular/check',
            data={'file': (io.BytesIO(invalid_bytes), 'test.txt')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'is_tabular' in data
    
    def test_check_no_file(self, client):
        """Test check endpoint without file."""
        response = client.post(
            '/api/tabular/check',
            data={},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
    
    def test_check_returns_filename(self, client, sample_csv_bytes):
        """Test check returns secure filename."""
        response = client.post(
            '/api/tabular/check',
            data={'file': (io.BytesIO(sample_csv_bytes), 'my test file.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert 'file_name' in data
        # Should be sanitized
        assert ' ' not in data['file_name'] or '_' in data['file_name']


class TestErrorHandling:
    """Tests for error handling across endpoints."""
    
    def test_validate_handles_read_error(self, client):
        """Test validate handles file read errors gracefully."""
        corrupted_bytes = b'\x00\x01\x02\x03\x04'
        
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(corrupted_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        # Should return error response, not crash
        assert response.status_code in [200, 400, 500]
        data = response.get_json()
        assert 'error' in data or 'is_valid' in data
    
    def test_preview_handles_encoding_error(self, client):
        """Test preview handles encoding errors."""
        # Binary data that might cause encoding issues
        binary_bytes = bytes(range(256))
        
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(binary_bytes), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400, 500]
    
    def test_import_handles_large_file_gracefully(self, client, large_csv_bytes):
        """Test import handles larger files."""
        response = client.post(
            '/api/tabular/import',
            data={
                'file': (io.BytesIO(large_csv_bytes), 'large.csv'),
                'max_rows': '100'
            },
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['rows_imported'] <= 100


class TestUnicodeHandling:
    """Tests for Unicode content handling."""
    
    def test_validate_unicode_content(self, client, csv_with_unicode_bytes):
        """Test validate handles unicode content."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(csv_with_unicode_bytes), 'unicode.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_preview_unicode_content(self, client, csv_with_unicode_bytes):
        """Test preview handles unicode content."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(csv_with_unicode_bytes), 'unicode.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Should preserve unicode characters
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
    
    def test_import_unicode_content(self, client, csv_with_unicode_bytes):
        """Test import handles unicode content."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(csv_with_unicode_bytes), 'unicode.csv')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Data should be JSON serializable with unicode
        json_str = json.dumps(data)
        assert isinstance(json_str, str)


class TestNullValueHandling:
    """Tests for null/missing value handling."""
    
    def test_validate_with_nulls(self, client, csv_with_nulls_bytes):
        """Test validate handles null values."""
        response = client.post(
            '/api/tabular/validate',
            data={'file': (io.BytesIO(csv_with_nulls_bytes), 'nulls.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['is_valid'] is True
    
    def test_preview_with_nulls(self, client, csv_with_nulls_bytes):
        """Test preview handles null values."""
        response = client.post(
            '/api/tabular/preview',
            data={'file': (io.BytesIO(csv_with_nulls_bytes), 'nulls.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        
        # Nulls should be None in JSON
        if data['data']:
            has_null = any(v is None for record in data['data'] for v in record.values())
            assert has_null
    
    def test_import_with_nulls(self, client, csv_with_nulls_bytes):
        """Test import handles null values."""
        response = client.post(
            '/api/tabular/import',
            data={'file': (io.BytesIO(csv_with_nulls_bytes), 'nulls.csv')},
            content_type='multipart/form-data'
        )
        
        data = response.get_json()
        assert data['success'] is True
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])