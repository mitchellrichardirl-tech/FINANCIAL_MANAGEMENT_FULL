import Button from '@/components/Button';
import FileDropzone from '@/components/FileDropzone';
import FormField from '@/components/FormField';
import NumberInput from '@/components/NumberInput';
import PreviewTable from '@/features/statements/PreviewTable';

export default function StepSampleFile({ editor }) {
  const { mode, draft, updateDraft, sample, loadSampleFile, clearSampleFile } = editor;
  const { file, previewData, loading, error } = sample;

  const hasFile = !!file;
  const hasData = !!previewData;
  const startRow = sample.headerRow;

  const handleSkipChange = (field) => (n) => updateDraft(field, n ?? 0);

  return (
    <div>
      <h2 className="m-0 mb-1.5 text-xl">Sample file</h2>
      <p className="m-0 mb-5 text-[#6c757d] text-sm">
        Upload a real export from this bank so we can read its column headers and
        test the format against actual rows. The file is only used for preview —
        nothing is imported.
      </p>

      {!hasFile && (
        <>
          {mode !== 'create' && (
            <div className="py-2.5 px-3.5 mb-4 bg-[#e7f3ff] border-l-4 border-[#4a90e2] rounded text-[13px] text-[#1c4d7a]">
              <strong>Optional.</strong> You can skip this and type column names
              manually in Step 3, but you won&apos;t be able to preview the result.
            </div>
          )}
          <FileDropzone onFileSelect={loadSampleFile} disabled={loading} />
        </>
      )}

      {hasFile && (
        <div className="flex justify-between items-center gap-4 py-3 px-4 mb-4 bg-[#f8f9fa] border border-[#dee2e6] rounded-md max-[640px]:flex-col max-[640px]:items-stretch">
          <div>
            <div className="font-semibold break-all">{file.name}</div>
            <div className="text-xs text-[#6c757d] mt-0.5">
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

      {loading && <p className="text-[#6c757d] py-6 text-center">Reading file…</p>}

      {error && (
        <div
          role="alert"
          className="py-3.5 px-4 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] flex justify-between items-center gap-4 mb-4"
        >
          <p className="m-0">{error}</p>
          <Button variant="secondary" onClick={clearSampleFile}>Try a different file</Button>
        </div>
      )}

      {hasData && (
        <>
          <div className="grid grid-cols-3 gap-4 max-w-[720px] max-[640px]:grid-cols-1">
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
            <div className="my-3 py-2 px-3 text-[13px] bg-[#e7f3ff] border-l-[3px] border-[#4a90e2] rounded text-[#1c4d7a] break-words">
              <strong>Columns detected from row {sample.headerRow}:</strong>{' '}
              {editor.sampleColumns.length > 0
                ? editor.sampleColumns.join(', ')
                : '(none — check the row number)'}
            </div>
          )}

          <div className="h-[50vh] min-h-[320px] border border-[#dee2e6] rounded-md overflow-hidden mt-1">
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

function formatBytes(n) {
  if (!Number.isFinite(n)) return '';
  if (n < 1024) return `${n} B`;
  const kb = n / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
}
