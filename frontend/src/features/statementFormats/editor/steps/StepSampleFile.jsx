/**
 * @file editor/steps/StepSampleFile.jsx
 * Step 1 — upload a sample export so the editor can offer real column
 * names in Step 3 and run a live preview in Step 5.
 *
 * The file never leaves the preview endpoint; it isn't stored. Skipping
 * is allowed (column pickers fall back to free text, preview disabled).
 */

import Button from '@/components/Button';
import FileDropzone from '@/components/FileDropzone';
import FormField from '@/components/FormField';
import NumberInput from '@/components/NumberInput';
import PreviewTable from '@/features/statements/PreviewTable';

import './StepSampleFile.css';

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepSampleFile({ editor }) {
  const { mode, draft, updateDraft, sample, loadSampleFile, clearSampleFile } = editor;
  const { file, previewData, loading, error } = sample;

  const hasFile = !!file;
  const hasData = !!previewData;

  // PreviewTable's `startRow` highlights the header row (yellow) and shades
  // everything before it (red). The table's <th> still show row 1's values —
  // possibly junk — but the yellow band makes the real header visible.
  const startRow = sample.headerRow;

  const handleSkipChange = (field) => (n) => {
    updateDraft(field, n ?? 0);
  };

  return (
    <div className="fe-step fe-step-sample">
      <h2>Sample file</h2>
      <p className="fe-step__sub">
        Upload a real export from this bank so we can read its column headers and
        test the format against actual rows. The file is only used for preview —
        nothing is imported.
      </p>

      {!hasFile && (
        <>
          {mode !== 'create' && (
            <div className="fe-step-sample__optional">
              <strong>Optional.</strong> You can skip this and type column names
              manually in Step 3, but you won&apos;t be able to preview the result.
            </div>
          )}
          <FileDropzone onFileSelect={loadSampleFile} disabled={loading} />
        </>
      )}

      {hasFile && (
        <div className="fe-step-sample__filebar">
          <div className="fe-step-sample__fileinfo">
            <div className="fe-step-sample__filename">{file.name}</div>
            <div className="fe-step-sample__filemeta">
              {formatBytes(file.size)}
              {hasData && (
                <>
                  {' · '}
                  {previewData.columns?.length ?? '?'} columns
                  {' · '}
                  {previewData.total_rows ?? previewData.data?.length ?? '?'} rows
                </>
              )}
            </div>
          </div>
          <Button variant="secondary" onClick={clearSampleFile} disabled={loading}>
            Remove file
          </Button>
        </div>
      )}

      {loading && (
        <p className="fe-step-sample__status">Reading file…</p>
      )}

      {error && (
        <div className="fe-step-sample__error" role="alert">
          <p>{error}</p>
          <Button variant="secondary" onClick={clearSampleFile}>
            Try a different file
          </Button>
        </div>
      )}

      {hasData && (
        <>
          <div className="fe-step-sample__controls">
            <FormField
              label="Column headers are on row"
              help="Row containing the column names. Rows above are ignored for this preview."
              htmlFor="header-row"
            >
              <NumberInput
                id="header-row"
                value={sample.headerRow}
                onChange={editor.setHeaderRow}
                min={1}
              />
            </FormField>

            <FormField
              label="Skip rows after header"
              help="Junk rows between the header and the first transaction. Part of the saved format."
              htmlFor="skip-start"
            >
              <NumberInput
                id="skip-start"
                value={draft.skip_rows_start}
                onChange={handleSkipChange('skip_rows_start')}
                min={0}
              />
            </FormField>

            <FormField
              label="Skip rows at end"
              help="Trailing rows to drop (totals, disclaimers). Part of the saved format."
              htmlFor="skip-end"
            >
              <NumberInput
                id="skip-end"
                value={draft.skip_rows_end}
                onChange={handleSkipChange('skip_rows_end')}
                min={0}
              />
            </FormField>
          </div>

          {sample.headerRow > 1 && (
            <div className="fe-step-sample__detected">
              <strong>Columns detected from row {sample.headerRow}:</strong>{' '}
              {editor.sampleColumns.length > 0
                ? editor.sampleColumns.join(', ')
                : '(none — check the row number)'}
            </div>
          )}

          <div className="fe-step-sample__table">
            <PreviewTable
              previewData={previewData}
              startRow={startRow}
              onStartRowChange={() => {}}
            />
          </div>
        </>
      )}
    </div>
  );
}

// ── helpers ───────────────────────────────────────────────────────────

function formatBytes(n) {
  if (!Number.isFinite(n)) return '';
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
}