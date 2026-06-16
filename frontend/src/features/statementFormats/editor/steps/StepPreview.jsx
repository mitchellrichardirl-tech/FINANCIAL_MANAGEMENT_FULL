/**
 * @file editor/steps/StepPreview.jsx
 * Step 5 — run the draft config against the sample rows and show what
 * the pipeline would produce. Save button lives in the FormatEditor
 * footer; this step only handles the dry-run.
 */

import { useEffect } from 'react';

import Button from '@/components/Button';
import ColumnMismatchPanel from '@/features/statements/ColumnMismatchPanel';
import ProcessingWarningsPanel from '@/features/statements/ProcessingWarningsPanel';

import { STEP } from '../../constants';
import ParsedPreviewTable from '../ParsedPreviewTable';
// ❌ removed: import './StepPreview.css'

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepPreview({ editor }) {
  const { sampleRows, preview, runPreview, goToStep } = editor;
  const hasSample = sampleRows.length > 0;

  useEffect(() => {
    if (hasSample) runPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="fe-step">
      {/* ── Header ── */}
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2>Preview &amp; save</h2>
          <p className="fe-step__sub">
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

      {/* ── No sample ── */}
      {!hasSample && (
        <div className="flex items-center justify-between gap-4 rounded border-l-4 border-l-[#4a90e2] bg-[#e7f3ff] p-5">
          <p className="m-0 text-sm text-[#1c4d7a]">
            No sample file loaded — preview isn&apos;t available. You can still save the
            format, or go back and upload a sample to test it first.
          </p>
          <Button variant="secondary" onClick={() => goToStep(STEP.SAMPLE)}>
            Go to Step 1
          </Button>
        </div>
      )}

      {/* ── Loading ── */}
      {hasSample && preview.loading && (
        <p className="py-6 text-center text-gray-500">Running preview…</p>
      )}

      {/* ── Column mismatch ── */}
      {preview.mismatch && (
        <ColumnMismatchPanel
          error={preview.mismatch}
          onDismiss={() => goToStep(STEP.COLUMNS)}
          actions={[
            { label: 'Back to column mapping', onClick: () => goToStep(STEP.COLUMNS) },
          ]}
        />
      )}

      {/* ── Other error ── */}
      {preview.error && !preview.mismatch && (
        <div
          className="mb-4 flex items-center justify-between gap-4 rounded border border-danger-border bg-danger-bg px-4 py-3.5 text-danger-text"
          role="alert"
        >
          <p className="m-0">{preview.error}</p>
          <Button variant="secondary" onClick={runPreview}>Retry</Button>
        </div>
      )}

      {/* ── Success ── */}
      {preview.result && (
        <div className="space-y-4">
          <ProcessingWarningsPanel
            warnings={preview.result.warnings}
            heading="⚠️ Preview completed with warnings"
            context="preview"
          />
          <ParsedPreviewTable
            rows={preview.result.preview_rows}
            total={preview.result.total_parsed}
          />
        </div>
      )}
    </div>
  );
}