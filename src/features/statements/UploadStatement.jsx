import { useState } from 'react';
import { useToast } from '@/components/ToastContext';
import { ErrorCode } from '@/lib/apiErrors';
import { previewFile, importFile, fetchStatementFormats, getAccounts } from './api';
import FileDropzone from '@/components/FileDropzone';
import PreviewTable from './PreviewTable';
import ImportResult from './ImportResult';
import AccountSelector from './AccountSelector';
import './UploadStatement.css';

export default function UploadStatement() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [statementFormats, setStatementFormats] = useState([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [startRow, setStartRow] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importWarnings, setImportWarnings] = useState(null);

  // Rich error state for column-mismatch failures.
  // Null = no error. Otherwise holds the parsed ApiError plus details.
  const [importError, setImportError] = useState(null);

  const { addToast } = useToast();

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

  const handleAccountCreated = (newAccount) => {
    setAccounts([...accounts, newAccount]);
  };

  const handleAccountChange = (accountId) => {
    setSelectedAccountId(accountId);
    // Clear column-mismatch error if user switches account — maybe the
    // new account's format matches this file.
    setImportError(null);
  };

  const handleImport = async () => {
    setIsLoading(true);
    setImportError(null);
    setImportWarnings([]);   // reset before each attempt

    try {
      const result = await importFile(selectedFile, startRow, selectedAccountId);

      // Destructure from the response — don't read from state you just set
      const {
        rows_in_file,
        rows_imported,
        warnings = [],
      } = result.data;

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
      if (
        err.code === ErrorCode.INVALID_FORMAT &&
        err.details?.missing_columns
      ) {
        setImportError({
          message: err.userMessage,
          formatName: err.details.statement_format,
          missing: err.details.missing_columns || [],
          required: err.details.required_columns || [],
          found: err.details.found_columns || [],
        });
        // Also toast so they notice if scrolled away
        addToast({
          message: 'Import failed — column mismatch',
          type: 'error',
          duration: 3000,
        });
      } else if (err.code === ErrorCode.NOT_FOUND && err.entity === 'Account') {
        // Account was deleted between selection and import
        addToast({
          message: 'Selected account no longer exists. Refreshing…',
          type: 'error',
        });
        setSelectedAccountId('');
        getAccounts().then(setAccounts);
      } else {
        // Everything else → toast
        addToast({
          message: err.userMessage || err.message || 'Failed to import file',
          type: 'error',
        });
      }
    } finally {
      setIsLoading(false);
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
  const canImport =
    !isLoading &&
    !!selectedAccountId &&
    !showFormatWarning &&
    !importError; // must dismiss/fix before retrying

  return (
    <div className="upload-statement">
      <h1>Upload Bank Statement</h1>

      {isLoading && <div className="upload-loading">Loading...</div>}

      {importResult ? (
        <div className="import-result-section">
          <ImportWarningsPanel warnings={importResult.warnings} />
          <ImportResult
            result={importResult}
            onUploadAnother={reset}
            showHeader={true}
          />
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
              {/* File Info Table */}
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

              {/* Column-mismatch error panel */}
              {importError && (
                <ColumnMismatchPanel
                  error={importError}
                  onDismiss={() => setImportError(null)}
                  onChangeAccount={() => {
                    setImportError(null);
                    // user will pick a different account below
                  }}
                  onRemoveFile={reset}
                />
              )}

              {/* Import Controls */}
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
                      ⚠️ This account has no statement format configured.
                      Import will not be available until a format is set.
                    </div>
                  )}
                </div>

                <div className="control-group btn-group">
                  <button
                    className="btn-import"
                    onClick={handleImport}
                    disabled={!canImport}
                  >
                    {isLoading ? 'Importing...' : 'Import Transactions'}
                  </button>
                </div>
              </div>

              {/* Preview Table */}
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
                  compact={true}
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

function ColumnMismatchPanel({ error, onDismiss, onChangeAccount, onRemoveFile }) {
  const { message, formatName, missing, required, found } = error;

  // Flag each found column as required/missing/extra for colour-coding
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
              <li
                key={col}
                className={
                  missingSet.has(col) ? 'cmp-missing' : 'cmp-present'
                }
              >
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
              <li
                key={col}
                className={requiredSet.has(col) ? 'cmp-present' : 'cmp-extra'}
              >
                {requiredSet.has(col) ? '✓' : '·'} {col}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="cmp-hint">
        {missing.length === 1 && found.some((f) =>
          f.toLowerCase().includes(missing[0].toLowerCase()) ||
          missing[0].toLowerCase().includes(f.toLowerCase())
        ) && (
          <p>
            💡 The file has a column that looks similar —
            check if the header spelling matches exactly.
          </p>
        )}
        <p>
          This usually means either the wrong account was selected,
          or the file was exported in a different format than expected.
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

function WarningItem({ warning }) {
  const [expanded, setExpanded] = useState(true); // default open — users should see this
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

function WarningDetails({ code, details }) {
  switch (code) {
    case 'DATES_UNPARSEABLE':
      return (
        <>
          <dl className="iwp-dl">
            <div>
              <dt>Column</dt>
              <dd><code>{details.column}</code></dd>
            </div>
            <div>
              <dt>Rows dropped</dt>
              <dd>{details.dropped} of {details.total}</dd>
            </div>
            <div>
              <dt>Parser used</dt>
              <dd><code>{details.format_used}</code></dd>
            </div>
          </dl>

          {details.sample_values?.length > 0 && (
            <div className="iwp-samples">
              <p className="iwp-samples-label">
                Sample values that couldn't be parsed:
              </p>
              <ul>
                {[...new Set(details.sample_values)].slice(0, 5).map((v, i) => (
                  <li key={i}><code>{v}</code></li>
                ))}
              </ul>
              <p className="iwp-hint">
                💡 If these look like valid dates, the statement format for
                this account may need a different date format string.
              </p>
            </div>
          )}
        </>
      );

    // Add more codes here as your backend emits them:
    // case 'AMOUNT_UNPARSEABLE': ...
    // case 'DUPLICATE_ROWS': ...

    default:
      // Generic fallback — still show *something* useful
      if (!details || Object.keys(details).length === 0) return null;
      return (
        <pre className="iwp-raw-details">
          {JSON.stringify(details, null, 2)}
        </pre>
      );
  }
}

// Defensive normalizer — handles objects, and (temporarily) the
// Python-repr strings until the backend is fixed.
function normalizeWarning(w) {
  if (w && typeof w === 'object') return w;

  if (typeof w === 'string') {
    // Try straight JSON first (in case backend is already fixed)
    try { return JSON.parse(w); } catch { /* fall through */ }

    // Last-ditch: Python repr → JSON. Brittle; remove once backend is fixed.
    try {
      const jsonish = w
        .replace(/\bNone\b/g, 'null')
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
        // Convert '…' to "…" only when not inside an existing "…"
        .replace(/'((?:[^'\\]|\\.)*)'/g, (_, inner) => `"${inner.replace(/"/g, '\\"')}"`);
      return JSON.parse(jsonish);
    } catch {
      return { code: 'UNKNOWN', message: w, details: {} };
    }
  }

  return { code: 'UNKNOWN', message: String(w), details: {} };
}