import { useEffect } from 'react';
import Button from '@/components/Button';
import ColumnMismatchPanel from '@/features/statements/ColumnMismatchPanel';
import ProcessingWarningsPanel from '@/features/statements/ProcessingWarningsPanel';
import { STEP } from '../../constants';
import ParsedPreviewTable from '../ParsedPreviewTable';

export default function StepPreview({ editor }) {
  const { sampleRows, preview, runPreview, goToStep } = editor;
  const hasSample = sampleRows.length > 0;

  useEffect(() => {
    if (hasSample) runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div className="flex justify-between items-start gap-4 mb-4">
        <div>
          <h2 className="m-0 mb-1.5 text-xl">Preview &amp; save</h2>
          <p className="m-0 mb-5 text-[#6c757d] text-sm">
            This is what the import pipeline would produce from your sample file. Check
            dates, signs and descriptions, then save.
          </p>
        </div>
        {hasSample && (
          <Button variant="secondary" onClick={runPreview} loading={preview.loading}>
            Re-run preview
          </Button>
        )}
      </div>

      {!hasSample && (
        <div className="py-5 px-5 bg-[#e7f3ff] border-l-4 border-[#4a90e2] rounded flex justify-between items-center gap-4">
          <p className="m-0 text-sm text-[#1c4d7a]">
            No sample file loaded — preview isn&apos;t available. You can still save the
            format, or go back and upload a sample to test it first.
          </p>
          <Button variant="secondary" onClick={() => goToStep(STEP.SAMPLE)}>
            Go to Step 1
          </Button>
        </div>
      )}

      {hasSample && preview.loading && (
        <p className="text-[#6c757d] py-6 text-center">Running preview…</p>
      )}

      {preview.mismatch && (
        <ColumnMismatchPanel
          error={preview.mismatch}
          onDismiss={() => goToStep(STEP.COLUMNS)}
          actions={[
            { label: 'Back to column mapping', onClick: () => goToStep(STEP.COLUMNS) },
          ]}
        />
      )}

      {preview.error && !preview.mismatch && (
        <div
          role="alert"
          className="py-3.5 px-4 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] flex justify-between items-center gap-4 mb-4"
        >
          <p className="m-0">{preview.error}</p>
          <Button variant="secondary" onClick={runPreview}>Retry</Button>
        </div>
      )}

      {preview.result && (
        <>
          <ProcessingWarningsPanel
            warnings={preview.result.warnings}
            heading="⚠️ Preview completed with warnings"
            context="preview"
          />
          <div className="mt-4">
            <ParsedPreviewTable
              rows={preview.result.preview_rows}
              total={preview.result.total_parsed}
            />
          </div>
        </>
      )}
    </div>
  );
}
