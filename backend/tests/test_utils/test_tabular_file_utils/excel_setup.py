import pandas as pd
from pathlib import Path


def check_library(name):
    """Check if a library is available."""
    try:
        __import__(name)
        print(f"✓ {name} is installed")
        return True
    except ImportError:
        print(f"✗ {name} is NOT installed")
        return False


def test_excel_engines():
    """Test Excel reading engines."""
    print("\n=== Checking Libraries ===")
    has_openpyxl = check_library('openpyxl')
    has_xlrd = check_library('xlrd')
    has_xlwt = check_library('xlwt')
    
    print(f"\n=== Pandas Version: {pd.__version__} ===")
    print("Note: pandas 2.0+ dropped xlwt support for writing. Use xlwt directly.\n")
    
    print("=== Testing Excel File Creation and Reading ===")
    
    # Test data
    headers = ['id', 'name', 'value']
    data = [
        [1, 'Alice', 10.5],
        [2, 'Bob', 20.5],
        [3, 'Charlie', 30.5],
    ]
    
    # Test .xlsx with pandas
    if has_openpyxl:
        try:
            xlsx_path = Path('test_temp.xlsx')
            df = pd.DataFrame(data, columns=headers)
            with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            df_read = pd.read_excel(xlsx_path, engine='openpyxl')
            print(f"✓ .xlsx: Write (pandas) and read successful ({len(df_read)} rows)")
            xlsx_path.unlink()
        except Exception as e:
            print(f"✗ .xlsx: Failed - {e}")
    
    # Test .xls with xlwt directly (not pandas)
    if has_xlwt and has_xlrd:
        try:
            import xlwt
            
            xls_path = Path('test_temp.xls')
            
            # Write using xlwt directly
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
            
            # Read using pandas/xlrd
            df_read = pd.read_excel(xls_path, engine='xlrd')
            print(f"✓ .xls: Write (xlwt direct) and read (xlrd) successful ({len(df_read)} rows)")
            print(f"  Data: {df_read.to_dict('records')}")
            xls_path.unlink()
        except Exception as e:
            print(f"✗ .xls: Failed - {e}")
    
    print("\n=== Summary ===")
    if has_openpyxl and has_xlrd and has_xlwt:
        print("✓ Full Excel support available:")
        print("  - .xlsx: read/write with openpyxl (via pandas)")
        print("  - .xls:  write with xlwt (direct), read with xlrd (via pandas)")
    elif has_openpyxl:
        print("⚠ Only .xlsx support (install xlrd and xlwt for .xls)")
    else:
        print("✗ No Excel support")


if __name__ == '__main__':
    test_excel_engines()