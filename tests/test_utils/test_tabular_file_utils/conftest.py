import pytest
import tempfile
import pandas as pd
from pathlib import Path
import shutil
import os


@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """Create a temporary directory for test files that persists for the session."""
    test_dir = tmp_path_factory.mktemp("test_files")
    return test_dir


@pytest.fixture(scope="session")
def sample_csv_file(test_data_dir):
    """Create a sample CSV file for testing."""
    file_path = test_data_dir / "sample.csv"
    
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'age': [25, 30, 35, 40, 45],
        'salary': [50000.50, 60000.75, 70000.00, 80000.25, 90000.99],
        'is_active': [True, True, False, True, False],
        'join_date': ['2020-01-15', '2019-06-20', '2018-03-10', '2021-11-05', '2017-09-30']
    })
    
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture(scope="session")
def sample_tsv_file(test_data_dir):
    """Create a sample TSV file for testing."""
    file_path = test_data_dir / "sample.tsv"
    
    df = pd.DataFrame({
        'product': ['Widget', 'Gadget', 'Doohickey'],
        'quantity': [10, 20, 30],
        'price': [9.99, 19.99, 29.99]
    })
    
    df.to_csv(file_path, sep='\t', index=False)
    return file_path


@pytest.fixture(scope="session")
def sample_txt_file(test_data_dir):
    """Create a sample pipe-delimited TXT file for testing."""
    file_path = test_data_dir / "sample.txt"
    
    content = """name|city|country
John|New York|USA
Jane|London|UK
Jack|Tokyo|Japan"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path


@pytest.fixture(scope="session")
def sample_xlsx_file(test_data_dir):
    """Create a sample modern Excel (.xlsx) file for testing."""
    file_path = test_data_dir / "sample.xlsx"
    
    df = pd.DataFrame({
        'department': ['Sales', 'Engineering', 'Marketing', 'HR'],
        'headcount': [15, 50, 10, 8],
        'budget': [100000, 500000, 75000, 50000]
    })
    
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Sheet1', index=False)
        
        return file_path
        
    except ImportError as e:
        pytest.skip(f"openpyxl not available: {e}")
    except Exception as e:
        pytest.skip(f"Could not create .xlsx test file: {e}")


@pytest.fixture(scope="session")
def sample_xls_file(test_data_dir):
    """Create a sample legacy Excel (.xls) file for testing using xlwt directly."""
    file_path = test_data_dir / "sample.xls"
    
    try:
        import xlwt
        
        # Create workbook and sheet
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Sheet1')
        
        # Define data
        headers = ['item', 'value', 'description']
        data = [
            ['A', 1, 'First'],
            ['B', 2, 'Second'],
            ['C', 3, 'Third'],
        ]
        
        # Write headers
        for col_idx, header in enumerate(headers):
            sheet.write(0, col_idx, header)
        
        # Write data
        for row_idx, row_data in enumerate(data, start=1):
            for col_idx, value in enumerate(row_data):
                sheet.write(row_idx, col_idx, value)
        
        # Save
        workbook.save(str(file_path))
        
        # Verify it's readable with xlrd
        test_df = pd.read_excel(file_path, engine='xlrd')
        assert len(test_df) == 3, "XLS file verification failed"
        
        return file_path
        
    except ImportError as e:
        pytest.skip(f"xlwt not available for creating .xls files: {e}")
    except Exception as e:
        pytest.skip(f"Could not create .xls test file: {e}")

@pytest.fixture(scope="session")
def multi_sheet_xls(test_data_dir):
    """Create a multi-sheet .xls file for testing."""
    file_path = test_data_dir / "multi_sheet.xls"
    
    try:
        import xlwt
        
        workbook = xlwt.Workbook()
        
        # Sheet 1
        sheet1 = workbook.add_sheet('Sheet1')
        sheet1.write(0, 0, 'col1')
        sheet1.write(0, 1, 'col2')
        sheet1.write(1, 0, 1)
        sheet1.write(1, 1, 'a')
        sheet1.write(2, 0, 2)
        sheet1.write(2, 1, 'b')
        
        # Sheet 2 - Data
        sheet2 = workbook.add_sheet('Data')
        sheet2.write(0, 0, 'x')
        sheet2.write(0, 1, 'y')
        sheet2.write(1, 0, 10)
        sheet2.write(1, 1, 30)
        sheet2.write(2, 0, 20)
        sheet2.write(2, 1, 40)
        
        # Sheet 3 - People
        sheet3 = workbook.add_sheet('People')
        sheet3.write(0, 0, 'name')
        sheet3.write(0, 1, 'age')
        sheet3.write(1, 0, 'Alice')
        sheet3.write(1, 1, 25)
        sheet3.write(2, 0, 'Bob')
        sheet3.write(2, 1, 30)
        
        workbook.save(str(file_path))
        
        return file_path
        
    except ImportError:
        pytest.skip("xlwt not available")
    except Exception as e:
        pytest.skip(f"Could not create multi-sheet .xls file: {e}")


@pytest.fixture(scope="session")
def multi_format_excel_files(test_data_dir):
    """Create both .xls and .xlsx files with the same data for comparison."""
    files = {}
    
    # Data to use
    headers = ['id', 'name', 'score']
    data = [
        [1, 'Alice', 95.5],
        [2, 'Bob', 87.0],
        [3, 'Charlie', 92.3],
        [4, 'David', 78.9],
        [5, 'Eve', 99.1],
    ]
    
    # Create .xlsx using pandas/openpyxl
    xlsx_path = test_data_dir / "comparison.xlsx"
    try:
        df = pd.DataFrame(data, columns=headers)
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        files['xlsx'] = xlsx_path
    except Exception as e:
        print(f"Could not create .xlsx: {e}")
    
    # Create .xls using xlwt directly
    xls_path = test_data_dir / "comparison.xls"
    try:
        import xlwt
        
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Sheet1')
        
        # Write headers
        for col_idx, header in enumerate(headers):
            sheet.write(0, col_idx, header)
        
        # Write data
        for row_idx, row_data in enumerate(data, start=1):
            for col_idx, value in enumerate(row_data):
                sheet.write(row_idx, col_idx, value)
        
        workbook.save(str(xls_path))
        files['xls'] = xls_path
    except Exception as e:
        print(f"Could not create .xls: {e}")
    
    return files

@pytest.fixture(scope="session")
def empty_csv_file(test_data_dir):
    """Create an empty CSV file for testing."""
    file_path = test_data_dir / "empty.csv"
    file_path.touch()
    return file_path


@pytest.fixture(scope="session")
def malformed_csv_file(test_data_dir):
    """Create a malformed CSV file with inconsistent columns."""
    file_path = test_data_dir / "malformed.csv"
    
    content = """col1,col2,col3
value1,value2,value3
value4,value5
value6,value7,value8,value9
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path


@pytest.fixture(scope="session")
def utf8_csv_file(test_data_dir):
    """Create a UTF-8 CSV file with special characters."""
    file_path = test_data_dir / "utf8.csv"
    
    df = pd.DataFrame({
        'name': ['José', 'François', '北京', '东京', 'Zürich'],
        'emoji': ['😀', '🎉', '🚀', '❤️', '🌟'],
        'description': ['Café', 'Naïve', '你好', 'こんにちは', 'Schön']
    })
    
    df.to_csv(file_path, index=False, encoding='utf-8')
    return file_path


@pytest.fixture(scope="session")
def latin1_csv_file(test_data_dir):
    """Create a Latin-1 encoded CSV file."""
    file_path = test_data_dir / "latin1.csv"
    
    content = """name,city
José,São Paulo
François,Montréal
María,México"""
    
    with open(file_path, 'w', encoding='latin-1') as f:
        f.write(content)
    
    return file_path


@pytest.fixture(scope="session")
def csv_with_nulls(test_data_dir):
    """Create a CSV file with null/missing values."""
    file_path = test_data_dir / "nulls.csv"
    
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'value1': [10, None, 30, None, 50],
        'value2': ['a', 'b', None, 'd', None],
        'value3': [1.1, 2.2, 3.3, None, 5.5]
    })
    
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture(scope="session")
def csv_with_duplicates(test_data_dir):
    """Create a CSV file with duplicate column names."""
    file_path = test_data_dir / "duplicates.csv"
    
    content = """id,name,value,name,value
1,Alice,100,Bob,200
2,Charlie,300,David,400"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path


@pytest.fixture(scope="session")
def csv_mixed_types(test_data_dir):
    """Create a CSV file with mixed data types in columns."""
    file_path = test_data_dir / "mixed_types.csv"
    
    content = """id,mixed_column,date_column
1,123,2023-01-01
2,abc,2023-02-15
3,456.78,not-a-date
4,xyz,2023-03-30"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path


@pytest.fixture(scope="session")
def multi_sheet_excel(test_data_dir):
    """Create an Excel file with multiple sheets."""
    file_path = test_data_dir / "multi_sheet.xlsx"
    
    df1 = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
    df2 = pd.DataFrame({'x': [10, 20], 'y': [30, 40]})
    df3 = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
    
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Sheet1', index=False)
        df2.to_excel(writer, sheet_name='Data', index=False)
        df3.to_excel(writer, sheet_name='People', index=False)
    
    return file_path


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file path for testing."""
    return tmp_path / "temp_test_file.csv"


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing."""
    return pd.DataFrame({
        'int_col': [1, 2, 3, 4, 5],
        'float_col': [1.1, 2.2, 3.3, 4.4, 5.5],
        'str_col': ['a', 'b', 'c', 'd', 'e'],
        'bool_col': [True, False, True, False, True],
        'date_col': pd.date_range('2023-01-01', periods=5),
        'null_col': [1, None, 3, None, 5]
    })


@pytest.fixture
def sample_series_integer():
    """Create a sample integer Series."""
    return pd.Series([1, 2, 3, 4, 5])


@pytest.fixture
def sample_series_float():
    """Create a sample float Series."""
    return pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])


@pytest.fixture
def sample_series_string():
    """Create a sample string Series."""
    return pd.Series(['apple', 'banana', 'cherry', 'date', 'elderberry'])


@pytest.fixture
def sample_series_boolean():
    """Create a sample boolean Series."""
    return pd.Series([True, False, True, False, True])


@pytest.fixture
def sample_series_datetime():
    """Create a sample datetime Series."""
    return pd.Series(pd.date_range('2023-01-01', periods=5))


@pytest.fixture
def sample_series_mixed():
    """Create a Series with mixed/string content."""
    return pd.Series(['123', 'abc', '456', 'xyz', '789'])


@pytest.fixture
def sample_series_date_strings():
    """Create a Series with date-like strings."""
    return pd.Series(['2023-01-01', '2023-02-15', '2023-03-30', '2023-04-20', '2023-05-10'])

@pytest.fixture(scope="session")
def csv_no_header(test_data_dir):
    """Create a CSV file without header."""
    file_path = test_data_dir / "no_header.csv"
    content = "1,Alice,25\n2,Bob,30\n3,Charlie,35"
    file_path.write_text(content)
    return file_path


@pytest.fixture(scope="session")
def json_file(test_data_dir):
    """Create a sample JSON file."""
    import json
    file_path = test_data_dir / "sample.json"
    data = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"}
    ]
    with open(file_path, 'w') as f:
        json.dump(data, f)
    return file_path


@pytest.fixture(scope="session")
def parquet_file(test_data_dir):
    """Create a sample Parquet file."""
    file_path = test_data_dir / "sample.parquet"
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['Alice', 'Bob', 'Charlie'],
        'value': [10.5, 20.5, 30.5]
    })
    df.to_parquet(file_path)
    return file_path


@pytest.fixture(scope="session")
def csv_with_duplicates(test_data_dir):
    """Create a CSV file with duplicate column names."""
    file_path = test_data_dir / "duplicates.csv"
    content = "id,name,value,name,value\n1,Alice,100,Bob,200\n2,Charlie,300,David,400"
    file_path.write_text(content)
    return file_path


@pytest.fixture(scope="session")
def large_csv_file(test_data_dir):
    """Create a larger CSV file for performance testing."""
    file_path = test_data_dir / "large.csv"
    rows = ["id,name,value,category,score"]
    for i in range(1000):
        rows.append(f"{i},name_{i},{i * 1.5},cat_{i % 10},{i % 100}")
    file_path.write_text("\n".join(rows))
    return file_path

@pytest.fixture(scope="session")
def csv_no_header(test_data_dir):
    """Create a CSV file without header."""
    file_path = test_data_dir / "no_header.csv"
    content = "1,Alice,25\n2,Bob,30\n3,Charlie,35"
    file_path.write_text(content)
    return file_path


@pytest.fixture(scope="session")
def csv_with_duplicates(test_data_dir):
    """Create a CSV file with duplicate column names."""
    file_path = test_data_dir / "duplicates.csv"
    content = "id,name,value,name,value\n1,Alice,100,Bob,200\n2,Charlie,300,David,400"
    file_path.write_text(content)
    return file_path


@pytest.fixture(scope="session")
def csv_with_nulls(test_data_dir):
    """Create a CSV file with null values."""
    file_path = test_data_dir / "nulls.csv"
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'value1': [10, None, 30, None, 50],
        'value2': ['a', 'b', None, 'd', None]
    })
    df.to_csv(file_path, index=False)
    return file_path


@pytest.fixture(scope="session")
def large_csv_file(test_data_dir):
    """Create a larger CSV file for testing."""
    file_path = test_data_dir / "large.csv"
    rows = ["id,name,value,category,score"]
    for i in range(1000):
        rows.append(f"{i},name_{i},{i * 1.5},cat_{i % 10},{i % 100}")
    file_path.write_text("\n".join(rows))
    return file_path


@pytest.fixture(scope="session")
def multi_sheet_excel(test_data_dir):
    """Create an Excel file with multiple sheets."""
    file_path = test_data_dir / "multi_sheet.xlsx"
    
    df1 = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
    df2 = pd.DataFrame({'x': [10, 20], 'y': [30, 40]})
    df3 = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [25, 30]})
    
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df1.to_excel(writer, sheet_name='Sheet1', index=False)
        df2.to_excel(writer, sheet_name='Data', index=False)
        df3.to_excel(writer, sheet_name='People', index=False)
    
    return file_path