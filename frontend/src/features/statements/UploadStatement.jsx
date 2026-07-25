/**
 * @file UploadStatement.jsx
 * Page for uploading and importing bank statement files.
 *
 * Workflow:
 *  1. User drops a file (CSV/XLSX) onto the dropzone.
 *  2. Backend parses and returns a preview of the first N rows.
 *  3. User selects/creates a target account and picks the start row
 *     (rows before this are skipped — useful for bank headers).
 *  4. On "Import", backend parses the full file using the account's
 *     configured statement format and creates transactions.
 *  5. On success, {@link ImportResult} renders a summary + table of
 *     imported transactions.
 *
 * Error handling distinguishes:
 *  - **Column mismatch** (`INVALID_FORMAT` with `missing_columns`) —
 *    rendered inline as a detailed comparison panel.
 *  - **Account deleted** (`NOT_FOUND` for Account) — refreshes the
 *    account list and prompts re-selection.
 *  - **Everything else** — toast.
 */
import { useState } from 'react';
import { useToast } from '@/components/ToastContext';
import { ErrorCode } from '@/lib/apiErrors';
import { previewFile, importFile, fetchStatementFormats, getAccounts } from './api';
import FileDropzone from '@/components/FileDropzone';
import ColumnMismatchPanel from './ColumnMismatchPanel';
import ProcessingWarningsPanel from './ProcessingWarningsPanel';
import PreviewTable from './PreviewTable';
import ImportResult from './ImportResult';
import AccountSelector from './AccountSelector';
import { createLogger } from '@/lib/logger';
const logger = createLogger('UploadStatement');
 /* ── Shared control height for visual alignment ─────────────────────── */
 const CONTROL_H = 'h-[42px]';
/* ── Page body height ────────────────────────────────────────────────
 * Both the preview and import-result branches own an internal scroll
 * region, so both need a definite height to anchor it. 200px accounts
 * for app chrome + page padding + the h1.                             */
const PAGE_BODY_H = 'h-[calc(100vh-200px)]';
/* ── File-info table cells (mobile-first) ────────────────────────────
 * Mobile: tds are display:block (stacked).
 * md+:    tds return to table-cell layout.                            */
const TD      = 'block px-2 py-1 md:table-cell md:align-middle md:px-3 md:py-2';
const TD_LBL  = `${TD} font-semibold text-gray-600 whitespace-nowrap md:pr-2`;
const TD_VAL  = `${TD} text-gray-800 md:pr-5`;
const TD_ACT  = `${TD} md:text-right md:w-[150px]`;
/**
 * Bank statement upload and import page.
 *
 * @component
 * @returns {JSX.Element}
 */
export default function UploadStatement() {
  /** Staged file (not yet imported). */
  const [selectedFile, setSelectedFile] = useState(null);
  /** Preview response from `/tabular/preview`. */
  const [previewData, setPreviewData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [statementFormats, setStatementFormats] = useState([]);
  /** Selected account id (empty string = none). */
  const [selectedAccountId, setSelectedAccountId] = useState('');
  /** 1-based row index where data starts. */
  const [startRow, setStartRow] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  /** Import response (set on success). */
  const [importResult, setImportResult] = useState(null);
  /** Warnings array from a successful import (may be non-empty). */
  const [importWarnings, setImportWarnings] = useState(null);
  /**
   * Rich error state for column-mismatch failures.
   * `null` = no error. Otherwise holds message + column lists.
   * @type {?{message: string, formatName: string, missing: string[], required: string[], found: string[]}}
   */
  const [importError, setImportError] = useState(null);
  const { addToast } = useToast();
  /** Derived: full account object for the selected id. */
  const selectedAccount = accounts.find((a) => a.id === selectedAccountId) || null;
  /** Reset to initial state (new file upload). */
  const reset = () => {
    setSelectedFile(null);
    setPreviewData(null);
    setSelectedAccountId('');
    setStartRow(1);
    setImportResult(null);
    setImportError(null);
  };
  // ── File selection ────────────────────────────────────────────────
  const handleFileSelect = async (file) => {
    setSelectedFile(file);
    setPreviewData(null);
    setImportResult(null);
    setImportError(null);
    setIsLoading(true);
    try {
      const preview = await previewFile(file);
      setPreviewData(preview);
      const [accountsData, formatsData] = await Promise.all([
        getAccounts(),
        fetchStatementFormats(),
      ]);
      setAccounts(accountsData);
      setStatementFormats(formatsData);
      logger.info('Fetched accounts:', accountsData);
      logger.info('Fetched statement formats:', formatsData);
    } catch (err) {
      addToast({
        message: err.userMessage || err.message || 'Failed to preview file',
        type: 'error',
      });
      setSelectedFile(null);
    } finally {
      setIsLoading(false);
    }
  };
  const handleAccountCreated = (newAccount) => {
    setAccounts([...accounts, newAccount]);
  };
  const handleAccountChange = (accountId) => {
    setSelectedAccountId(accountId);
    setImportError(null);
  };
  // ── Import ────────────────────────────────────────────────────────
  const handleImport = async () => {
    setIsLoading(true);
    setImportError(null);
    setImportWarnings([]);
    try {
      const result = await importFile(selectedFile, startRow, selectedAccountId);
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
        addToast({ message: 'Selected account no longer exists. Refreshing…', type: 'error' });
        setSelectedAccountId('');
        getAccounts().then(setAccounts);
      } else {
        addToast({
          message: err.userMessage || err.message || 'Failed to import file',
          type: 'error',
        });
      }
    } finally {
      setIsLoading(false);
    }
  };
  // ── Helpers ───────────────────────────────────────────────────────
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
  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-[1400px] p-5">
      <h1 className="mb-5 text-2xl font-bold">Upload Bank Statement</h1>
      {isLoading && (
        <div className="p-10 text-center text-lg text-gray-500">Loading...</div>
      )}
      {importResult ? (
        <div className={`mt-5 flex flex-col ${PAGE_BODY_H}`}>
          {/* shrink-0 wrapper: panel keeps its natural height, ImportResult
              absorbs the remainder. Renders empty when there are no warnings. */}
          <div className="shrink-0">
            <ProcessingWarningsPanel
              warnings={importResult.warnings}
              heading="⚠️ Import completed with warnings"
              context="import"
            />
          </div>
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
            <div className={`mt-5 flex flex-col ${PAGE_BODY_H}`}>
              {/* ── File info summary ── */}
              <div className="shrink-0 mb-4 rounded-lg bg-gray-50 p-4">
                <table className="w-full text-sm xl:text-base">
                  <tbody>
                    <tr>
                      <td className={TD_LBL}>File Name:</td>
                      <td className={TD_VAL}>{selectedFile.name}</td>
                      <td className={TD_LBL}>Type:</td>
                      <td className={TD_VAL}>{getFileExtension(selectedFile.name)}</td>
                      <td className={TD_LBL}>Size:</td>
                      <td className={TD_VAL}>{formatFileSize(selectedFile.size)}</td>
                      <td className={TD_LBL}>Total Rows:</td>
                      <td className={TD_VAL}>{previewData.total_rows}</td>
                      <td className={TD_ACT}>
                        <button
                          className={`${CONTROL_H} cursor-pointer rounded bg-[#dc3545] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#c82333]`}
                          onClick={reset}
                        >
                          Remove File
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {/* ── Column mismatch error ── */}
              {importError && (
                <div className="shrink-0">
                  <ColumnMismatchPanel
                    error={importError}
                    onDismiss={() => setImportError(null)}
                    actions={[
                      { label: 'Try a different account', onClick: () => setImportError(null) },
                      { label: 'Choose a different file', onClick: reset },
                    ]}
                  />
                </div>
              )}
              {/* ── Import controls ── */}
              <div className="shrink-0 mb-4 flex flex-wrap items-center gap-5 rounded-lg border border-gray-300 bg-white p-4">
                {/* Start row */}
                <div className="flex w-full items-center gap-2.5 md:w-auto">
                  <label
                    htmlFor="start-row"
                    className="whitespace-nowrap font-semibold text-gray-800"
                  >
                    Start Row:
                  </label>
                  <input
                    id="start-row"
                    type="number"
                    min="1"
                    max={previewData.total_rows}
                    value={startRow}
                    onChange={(e) => setStartRow(parseInt(e.target.value) || 1)}
                    className={`${CONTROL_H} w-full rounded border border-gray-300 px-3 py-2.5 text-sm focus:border-[#4a90e2] focus:shadow-[0_0_0_3px_rgba(74,144,226,0.1)] focus:outline-none md:w-20`}
                  />
                </div>
                {/* Account selector */}
                <div className="flex w-full flex-col gap-1.5 lg:min-w-[300px] lg:flex-1 [&_select]:h-[42px] [&_select]:px-3 [&_select]:py-2.5">
                  <AccountSelector
                    accounts={accounts}
                    selectedAccountId={selectedAccountId}
                    onAccountChange={handleAccountChange}
                    onAccountCreated={handleAccountCreated}
                    disabled={isLoading}
                    statementFormats={statementFormats}
                  />
                  {showFormatWarning && (
                    <div className="rounded border border-[#ffc107] bg-[#fff3cd] px-3 py-2 text-[13px] text-[#856404]">
                      ⚠️ This account has no statement format configured. Import will not be
                      available until a format is set.
                    </div>
                  )}
                </div>
                {/* Import button */}
                <div className="w-full lg:ml-auto lg:w-auto">
                  <button
                    className={`${CONTROL_H} w-full cursor-pointer whitespace-nowrap rounded bg-[#28a745] px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#218838] disabled:cursor-not-allowed disabled:bg-[#6c757d] disabled:opacity-60 lg:w-auto`}
                    onClick={handleImport}
                    disabled={!canImport}
                  >
                    {isLoading ? 'Importing...' : 'Import Transactions'}
                  </button>
                </div>
              </div>
              {/* Preview table */}
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-gray-300 bg-white">
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