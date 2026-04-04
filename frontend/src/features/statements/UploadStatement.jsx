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
      setPreviewData(preview.data);

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
          <ImportWarningsPanel warnings={importResult.warnings} />
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
                  onChangeAccount={() => setImportError(null)}
                  onRemoveFile={reset}
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

// ─────────────────────────────────────────────────────────────────────────────
// Column mismatch panel
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Inline error panel showing which columns are expected vs. found.
 *
 * Rendered when `importFile` fails with `INVALID_FORMAT` and
 * `missing_columns` in the details.
 *
 * @param {Object} props
 * @param {{message: string, formatName: string, missing: string[], required: string[], found: string[]}} props.error
 * @param {() => void} props.onDismiss - Close the panel (user may retry).
 * @param {() => void} props.onChangeAccount - Clear error and let user pick another account.
 * @param {() => void} props.onRemoveFile - Reset the page to choose a different file.
 */
function ColumnMismatchPanel({ error, onDismiss, onChangeAccount, onRemoveFile }) {
  const { message, formatName, missing, required, found } = error;

  const foundSet = new Set(found);
  const requiredSet = new Set(required);
  const missingSet = new Set(missing);

  return (
    <div className="column-mismatch-panel" role="alert">
      <div className="cmp-header">
        <div>
          <strong>Import failed — column mismatch</strong>
          <p className="cmp-message">{message}</p>
        </div>
        <button className="cmp-close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      </div>

      <div className="cmp-comparison">
        <div className="cmp-column">
          <h4>
            Expected by <em>{formatName || 'this format'}</em>
          </h4>
          <ul>
            {required.map((col) => (
              <li key={col} className={missingSet.has(col) ? 'cmp-missing' : 'cmp-present'}>
                {missingSet.has(col) ? '✗' : '✓'} {col}
              </li>
            ))}
          </ul>
        </div>

        <div className="cmp-column">
          <h4>Found in file</h4>
          <ul>
            {found.length === 0 && <li className="cmp-empty">(no columns)</li>}
            {found.map((col) => (
              <li key={col} className={requiredSet.has(col) ? 'cmp-present' : 'cmp-extra'}>
                {requiredSet.has(col) ? '✓' : '·'} {col}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="cmp-hint">
        {missing.length === 1 &&
          found.some(
            (f) =>
              f.toLowerCase().includes(missing[0].toLowerCase()) ||
              missing[0].toLowerCase().includes(f.toLowerCase())
          ) && (
            <p>
              💡 The file has a column that looks similar — check if the header spelling matches
              exactly.
            </p>
          )}
        <p>
          This usually means either the wrong account was selected, or the file was exported in a
          different format than expected.
        </p>
      </div>

      <div className="cmp-actions">
        <button onClick={onChangeAccount} className="cmp-btn-secondary">
          Try a different account
        </button>
        <button onClick={onRemoveFile} className="cmp-btn-secondary">
          Choose a different file
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Import warnings panel
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Collapsible panel listing warnings from a successful import.
 *
 * Rendered when the import succeeds but some rows were skipped (e.g.
 * unparseable dates).
 *
 * @param {Object} props
 * @param {Array<Object|string>} props.warnings - Raw warnings from the API.
 */
function ImportWarningsPanel({ warnings }) {
  if (!warnings?.length) return null;

  const parsed = warnings.map(normalizeWarning);

  return (
    <div className="import-warnings-panel" role="status">
      <div className="iwp-header">
        <strong>⚠️ Import completed with warnings</strong>
        <p className="iwp-subheader">
          {parsed.length === 1
            ? 'One issue was encountered. The affected rows were skipped.'
            : `${parsed.length} issues were encountered. Affected rows were skipped.`}
        </p>
      </div>

      <div className="iwp-items">
        {parsed.map((w, i) => (
          <WarningItem key={`${w.code}-${i}`} warning={w} />
        ))}
      </div>
    </div>
  );
}

/**
 * Single expandable warning item.
 * @param {{warning: {code: string, message: string, details: Object}}} props
 */
function WarningItem({ warning }) {
  const [expanded, setExpanded] = useState(true);
  const { code, message, details = {} } = warning;

  return (
    <div className={`iwp-item iwp-code-${code?.toLowerCase() || 'unknown'}`}>
      <button
        type="button"
        className="iwp-toggle"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="iwp-chevron">{expanded ? '▾' : '▸'}</span>
        <span className="iwp-message">{message}</span>
      </button>

      {expanded && (
        <div className="iwp-details">
          <WarningDetails code={code} details={details} />
        </div>
      )}
    </div>
  );
}

/**
 * Render details for a specific warning code.
 * Add cases here as the backend emits new warning types.
 *
 * @param {Object} props
 * @param {string} props.code
 * @param {Object} props.details
 */
function WarningDetails({ code, details }) {
  switch (code) {
    case 'DATES_UNPARSEABLE':
      return (
        <>
          <dl className="iwp-dl">
            <div>
              <dt>Column</dt>
              <dd>
                <code>{details.column}</code>
              </dd>
            </div>
            <div>
              <dt>Rows dropped</dt>
              <dd>
                {details.dropped} of {details.total}
              </dd>
            </div>
            <div>
              <dt>Parser used</dt>
              <dd>
                <code>{details.format_used}</code>
              </dd>
            </div>
          </dl>

          {details.sample_values?.length > 0 && (
            <div className="iwp-samples">
              <p className="iwp-samples-label">Sample values that couldn't be parsed:</p>
              <ul>
                {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                  <li key={i}>
                    <code>{v}</code>
                  </li>
                ))}
              </ul>
              <p className="iwp-hint">
                💡 If these look like valid dates, the statement format for this account may need a
                different date format string.
              </p>
            </div>
          )}
        </>
      );

    default:
      if (!details || Object.keys(details).length === 0) return null;
      return <pre className="iwp-raw-details">{JSON.stringify(details, null, 2)}</pre>;
  }
}

/**
 * Normalize a warning to `{ code, message, details }`.
 *
 * Handles objects directly, JSON strings, and (temporarily) Python repr
 * strings if the backend hasn't been fixed yet.
 *
 * @param {Object|string} w
 * @returns {{code: string, message: string, details: Object}}
 */
function normalizeWarning(w) {
  if (w && typeof w === 'object') return w;

  if (typeof w === 'string') {
    try {
      return JSON.parse(w);
    } catch {
      /* fall through */
    }

    // Last-ditch: Python repr → JSON
    try {
      const jsonish = w
        .replace(/\bNone\b/g, 'null')
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
        .replace(/'((?:[^'\\]|\\.)*)'/g, (_, inner) => `"${inner.replace(/"/g, '\\"')}"`);
      return JSON.parse(jsonish);
    } catch {
      return { code: 'UNKNOWN', message: w, details: {} };
    }
  }

  return { code: 'UNKNOWN', message: String(w), details: {} };
}