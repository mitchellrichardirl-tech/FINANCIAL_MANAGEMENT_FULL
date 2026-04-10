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
import './UploadStatement.css';

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

  /**
   * Handle file selection: preview the file and load reference data.
   * @param {File} file
   */
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

  /**
   * Append a newly created account to the list.
   * @param {Object} newAccount
   */
  const handleAccountCreated = (newAccount) => {
    setAccounts([...accounts, newAccount]);
  };

  /**
   * Handle account dropdown change; clears any column-mismatch error
   * (maybe the new account's format matches).
   * @param {number|string} accountId
   */
  const handleAccountChange = (accountId) => {
    setSelectedAccountId(accountId);
    setImportError(null);
  };

  // ── Import ────────────────────────────────────────────────────────

  /**
   * Submit the file for import into the selected account.
   */
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
        addToast({
          message: `Imported ${rows_imported} transactions`,
          type: 'success',
        });
      } else {
        addToast({
          message: `Imported ${rows_imported} of ${rows_in_file} rows — see details below`,
          type: 'warning',
        });
      }
    } catch (err) {
      if (err.code === ErrorCode.INVALID_FORMAT && err.details?.missing_columns) {
        // Column mismatch — show detailed inline panel
        setImportError({
          message: err.userMessage,
          formatName: err.details.statement_format,
          missing: err.details.missing_columns || [],
          required: err.details.required_columns || [],
          found: err.details.found_columns || [],
        });
        addToast({
          message: 'Import failed — column mismatch',
          type: 'error',
          duration: 3000,
        });
      } else if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Account') {
        // Account deleted between selection and import
        addToast({
          message: 'Selected account no longer exists. Refreshing…',
          type: 'error',
        });
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

  /**
   * Format bytes as human-readable string.
   * @param {number} bytes
   */
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  /**
   * Extract uppercase file extension.
   * @param {string} filename
   */
  const getFileExtension = (filename) => filename.split('.').pop().toUpperCase();

  /** Warn when the selected account has no statement format. */
  const showFormatWarning = selectedAccount && !selectedAccount.statement_format;

  /** Import button enabled only when ready and no blocking errors. */
  const canImport = !isLoading && !!selectedAccountId && !showFormatWarning && !importError;

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div className="upload-statement">
      <h1>Upload Bank Statement</h1>

      {isLoading && <div className="upload-loading">Loading...</div>}

      {importResult ? (
        <div className="import-result-section">
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
            <div className="dropzone-section">
              <FileDropzone onFileSelect={handleFileSelect} disabled={isLoading} />
            </div>
          )}

          {selectedFile && previewData && (
            <div className="preview-section">
              {/* File info summary */}
              <div className="file-info-table">
                <table>
                  <tbody>
                    <tr>
                      <td className="info-label">File Name:</td>
                      <td className="info-value">{selectedFile.name}</td>
                      <td className="info-label">Type:</td>
                      <td className="info-value">{getFileExtension(selectedFile.name)}</td>
                      <td className="info-label">Size:</td>
                      <td className="info-value">{formatFileSize(selectedFile.size)}</td>
                      <td className="info-label">Total Rows:</td>
                      <td className="info-value">{previewData.total_rows}</td>
                      <td className="info-actions">
                        <button className="btn-remove" onClick={reset}>
                          Remove File
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Column mismatch error (if present) */}
              {importError && (
                <ColumnMismatchPanel
                  error={importError}
                  onDismiss={() => setImportError(null)}
                  actions={([
                    { label: 'Try a different account', onClick: () => setImportError(null)},
                    { label: 'Choose a different file', onClick: reset },
                  ])}
                />
              )}

              {/* Import controls */}
              <div className="import-controls">
                <div className="control-group">
                  <label htmlFor="start-row">Start Row:</label>
                  <input
                    id="start-row"
                    type="number"
                    min="1"
                    max={previewData.total_rows}
                    value={startRow}
                    onChange={(e) => setStartRow(parseInt(e.target.value) || 1)}
                    className="control-input"
                  />
                </div>

                <div className="control-group account-group">
                  <AccountSelector
                    accounts={accounts}
                    selectedAccountId={selectedAccountId}
                    onAccountChange={handleAccountChange}
                    onAccountCreated={handleAccountCreated}
                    disabled={isLoading}
                    statementFormats={statementFormats}
                  />
                  {showFormatWarning && (
                    <div className="format-warning">
                      ⚠️ This account has no statement format configured. Import will not be
                      available until a format is set.
                    </div>
                  )}
                </div>

                <div className="control-group btn-group">
                  <button className="btn-import" onClick={handleImport} disabled={!canImport}>
                    {isLoading ? 'Importing...' : 'Import Transactions'}
                  </button>
                </div>
              </div>

              {/* Preview table */}
              <div
                className="preview-table-wrapper"
                style={{
                  height: 'calc(100vh - 60px)',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden',
                }}
              >
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

