/**
 * @file editor/steps/StepSampleFile.jsx
 * Step 1 — upload a sample export so the editor can offer real column
 * names in Step 3 and run a live preview in Step 5.
 */

import Button from '@/components/Button';
import FileDropzone from '@/components/FileDropzone';
import FormField from '@/components/FormField';
import NumberInput from '@/components/NumberInput';
import PreviewTable from '@/features/statements/PreviewTable';

/* Reused class strings */
const infoBanner =
  'rounded border-l-4 border-l-info-border bg-info-bg text-[13px] text-info-text';

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepSampleFile({ editor }) {
  const { mode, draft, updateDraft, sample, loadSampleFile, clearSampleFile } = editor;
  const { file, previewData, loading, error } = sample;

  const hasFile = !!file;
  const hasData = !!previewData;

  const startRow = sample.headerRow;

  const handleSkipChange = (field) => (n) => {
    updateDraft(field, n ?? 0);
  };

  return (
    <div>
      <h2 className="text-xl mb-1.5">Sample file</h2>
      <p className="mb-5 text-sm text-muted">
        Upload a real export from this bank so we can read its column headers and
        test the format against actual rows. The file is only used for preview —
        nothing is imported.
      </p>

      {/* ── No file yet ── */}
      {!hasFile && (
        <>
          {mode !== 'create' && (
            <div className={`${infoBanner} mb-4 px-3.5 py-2.5`}>
              <strong>Optional.</strong> You can skip this and type column names
              manually in Step 3, but you won&apos;t be able to preview the result.
            </div>
          )}
          <FileDropzone onFileSelect={loadSampleFile} disabled={loading} />
        </>
      )}

      {/* ── File loaded bar ── */}
      {hasFile && (
        <div className="mb-4 flex flex-col items-stretch gap-4 rounded-md border border-gray-300 bg-gray-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="break-all font-semibold">{file.name}</div>
            <div className="mt-0.5 text-xs text-gray-500">
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

      {/* ── Loading ── */}
      {loading && (
        <p className="py-6 text-center text-gray-500">Reading file…</p>
      )}

      {/* ── Error ── */}
      {error && (
        <div
          className="mb-4 flex items-center justify-between gap-4 rounded border border-danger-border bg-danger-bg px-4 py-3.5 text-danger-text"
          role="alert"
        >
          <p className="m-0">{error}</p>
          <Button variant="secondary" onClick={clearSampleFile}>
            Try a different file
          </Button>
        </div>
      )}

      {/* ── Preview controls + table ── */}
      {hasData && (
        <>
          <div className="grid max-w-[720px] grid-cols-1 gap-4 sm:grid-cols-3">
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
            <div className={`${infoBanner} mt-1 mb-3 border-l-[3px] rounded-[3px] px-3 py-2 break-words`}>
              <strong>Columns detected from row {sample.headerRow}:</strong>{' '}
              {editor.sampleColumns.length > 0
                ? editor.sampleColumns.join(', ')
                : '(none — check the row number)'}
            </div>
          )}

          {/*
           * PreviewTable flex-fills its parent, so it needs an explicit
           * height. 50vh keeps the wizard footer visible without scrolling
           * the whole page on typical laptop screens.
           */}
          <div className="mt-1 h-[50vh] min-h-[320px] overflow-hidden rounded-md border border-gray-300">
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