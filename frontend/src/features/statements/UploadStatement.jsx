import { useState } from 'react';
import { useToast } from '@/components/ToastContext';
import { ErrorCode } from '@/lib/apiErrors';
import {
  useAccounts,
  useStatementFormats,
  usePreviewFile,
  useImportFile,
} from './hooks';
import FileDropzone from '@/components/FileDropzone';
import ColumnMismatchPanel from './ColumnMismatchPanel';
import ProcessingWarningsPanel from './ProcessingWarningsPanel';
import PreviewTable from './PreviewTable';
import ImportResult from './ImportResult';
import AccountSelector from './AccountSelector';
import { createLogger } from '@/lib/logger';

const logger = createLogger('UploadStatement');

export default function UploadStatement() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [startRow, setStartRow] = useState(1);
  const [importResult, setImportResult] = useState(null);
  const [importWarnings, setImportWarnings] = useState(null);
  const [importError, setImportError] = useState(null);

  const { addToast } = useToast();
  const accountsQuery = useAccounts();
  const formatsQuery = useStatementFormats();
  const previewMutation = usePreviewFile();
  const importMutation = useImportFile();

  const accounts = accountsQuery.data || [];
  const statementFormats = formatsQuery.data || [];
  const isLoading = previewMutation.isPending || importMutation.isPending;
  const selectedAccount = accounts.find((a) => a.id === selectedAccountId) || null;

  const reset = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setSelectedAccountId('');
    setStartRow(1);
    setImportResult(null);
    setImportError(null);
  };

  const handleFileSelect = async (file) => {
    setSelectedFile(file);
    setPreviewData(null);
    setImportResult(null);
    setImportError(null);
    try {
      const preview = await previewMutation.mutateAsync({ file });
      setPreviewData(preview);
      logger.info('Fetched preview');
    } catch (err) {
      addToast({
        message: err.userMessage || err.message || 'Failed to preview file',
        type: 'error',
      });
      setSelectedFile(null);
    }
  };

  const handleAccountChange = (accountId) => {
    setSelectedAccountId(accountId);
    setImportError(null);
  };

  const handleImport = async () => {
    setImportError(null);
    setImportWarnings([]);
    try {
      const result = await importMutation.mutateAsync({
        file: selectedFile,
        startRow,
        accountId: selectedAccountId,
      });
      const { rows_in_file, rows_imported, warnings = [] } = result.data;
      setImportResult(result.data);
      setImportWarnings(warnings);

      if (warnings.length === 0 && rows_imported === rows_in_file) {
        addToast({ message: `Imported ${rows_imported} transactions`, type: 'success' });
      } else {
        addToast({
          message: `Imported ${rows_imported} of ${rows_in_file} rows — see details below`,
          type: 'warning',
        });
      }
    } catch (err) {
      if (err.code === ErrorCode.INVALID_FORMAT && err.details?.missing_columns) {
        setImportError({
          message: err.userMessage,
          formatName: err.details.statement_format,
          missing: err.details.missing_columns || [],
          required: err.details.required_columns || [],
          found: err.details.found_columns || [],
        });
        addToast({ message: 'Import failed — column mismatch', type: 'error', duration: 3000 });
      } else if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Account') {
        addToast({
          message: 'Selected account no longer exists. Refreshing…',
          type: 'error',
        });
        setSelectedAccountId('');
        accountsQuery.refetch();
      } else {
        addToast({
          message: err.userMessage || err.message || 'Failed to import file',
          type: 'error',
        });
      }
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };
  const getFileExtension = (filename) => filename.split('.').pop().toUpperCase();

  const showFormatWarning = selectedAccount && !selectedAccount.statement_format;
  const canImport = !isLoading && !!selectedAccountId && !showFormatWarning && !importError;

  return (
    <div className="p-5 max-w-[1400px] mx-auto">
      <h1 className="text-3xl font-semibold mb-4">Upload Bank Statement</h1>

      {isLoading && (
        <div className="text-center py-10 text-[#666] text-lg">Loading...</div>
      )}

      {importResult ? (
        <div className="mt-5">
          <ProcessingWarningsPanel
            warnings={importResult.warnings}
            heading="⚠️ Import completed with warnings"
            context="import"
          />
          <ImportResult result={importResult} onUploadAnother={reset} showHeader />
        </div>
      ) : (
        <>
          {!previewData && !isLoading && (
            <div className="mt-5">
              <FileDropzone onFileSelect={handleFileSelect} disabled={isLoading} />
            </div>
          )}

          {selectedFile && previewData && (
            <div className="mt-5 flex flex-col h-[calc(100vh-200px)]">
              <div className="bg-[#f8f9fa] rounded-lg p-4 mb-4 shrink-0">
                <table className="w-full border-collapse">
                  <tbody>
                    <tr>
                      <td className="py-2 px-3 font-semibold text-[#555] whitespace-nowrap pr-2">File Name:</td>
                      <td className="py-2 px-3 text-[#333] pr-5">{selectedFile.name}</td>
                      <td className="py-2 px-3 font-semibold text-[#555] whitespace-nowrap pr-2">Type:</td>
                      <td className="py-2 px-3 text-[#333] pr-5">{getFileExtension(selectedFile.name)}</td>
                      <td className="py-2 px-3 font-semibold text-[#555] whitespace-nowrap pr-2">Size:</td>
                      <td className="py-2 px-3 text-[#333] pr-5">{formatFileSize(selectedFile.size)}</td>
                      <td className="py-2 px-3 font-semibold text-[#555] whitespace-nowrap pr-2">Total Rows:</td>
                      <td className="py-2 px-3 text-[#333] pr-5">{previewData.total_rows}</td>
                      <td className="text-right w-[150px]">
                        <button
                          type="button"
                          onClick={reset}
                          className="py-2 px-4 bg-[#dc3545] text-white border-0 rounded text-sm font-medium cursor-pointer h-9 hover:bg-[#c82333]"
                        >
                          Remove File
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {importError && (
                <ColumnMismatchPanel
                  error={importError}
                  onDismiss={() => setImportError(null)}
                  actions={[
                    { label: 'Try a different account', onClick: () => setImportError(null) },
                    { label: 'Choose a different file', onClick: reset },
                  ]}
                />
              )}

              <div className="flex items-center gap-5 p-4 bg-white border border-[#dee2e6] rounded-lg mb-4 shrink-0 flex-wrap">
                <div className="flex items-center gap-[10px]">
                  <label htmlFor="start-row" className="font-semibold text-[#333] whitespace-nowrap">
                    Start Row:
                  </label>
                  <input
                    id="start-row"
                    type="number"
                    min="1"
                    max={previewData.total_rows}
                    value={startRow}
                    onChange={(e) => setStartRow(parseInt(e.target.value) || 1)}
                    className="w-20 py-[10px] px-3 border border-[#ced4da] rounded text-sm h-[42px] box-border focus:outline-none focus:border-[#4a90e2] focus:shadow-[0_0_0_3px_rgba(74,144,226,0.1)]"
                  />
                </div>

                <div className="flex items-center gap-[10px] flex-1 min-w-[300px]">
                  <AccountSelector
                    accounts={accounts}
                    selectedAccountId={selectedAccountId}
                    onAccountChange={handleAccountChange}
                    disabled={isLoading}
                    statementFormats={statementFormats}
                  />
                  {showFormatWarning && (
                    <div className="mt-[6px] py-2 px-3 bg-[#fff3cd] border border-[#ffc107] rounded text-[#856404] text-[13px]">
                      ⚠️ This account has no statement format configured. Import will not be available until a format is set.
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-[10px] ml-auto">
                  <button
                    type="button"
                    onClick={handleImport}
                    disabled={!canImport}
                    className="py-[10px] px-6 bg-[#28a745] text-white border-0 rounded text-sm font-semibold cursor-pointer whitespace-nowrap h-[42px] box-border hover:enabled:bg-[#218838] disabled:bg-[#6c757d] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isLoading ? 'Importing...' : 'Import Transactions'}
                  </button>
                </div>
              </div>

              <div className="flex-1 border border-[#dee2e6] rounded-lg bg-white flex flex-col overflow-hidden">
                <PreviewTable
                  previewData={previewData}
                  startRow={startRow}
                  onStartRowChange={setStartRow}
                  compact
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
