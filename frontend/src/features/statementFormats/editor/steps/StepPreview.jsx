/**
 * @file editor/steps/StepPreview.jsx
 * Step 5 — run the draft config against the sample rows and show what
 * the pipeline would produce. Save button lives in the FormatEditor
 * footer; this step only handles the dry-run.
 *
 * States:
 *   - no sample        → prompt to go back to Step 1
 *   - loading          → spinner line
 *   - column mismatch  → ColumnMismatchPanel with a jump-back action
 *   - other error      → inline message + retry
 *   - success          → ParsedPreviewTable + ProcessingWarningsPanel
 */

import { useEffect } from 'react';

import Button from '@/components/Button';
import ColumnMismatchPanel from '@/features/statements/ColumnMismatchPanel';
import ProcessingWarningsPanel from '@/features/statements/ProcessingWarningsPanel';

import { STEP } from '../../constants';
import ParsedPreviewTable from '../ParsedPreviewTable';
import './StepPreview.css';

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepPreview({ editor }) {
  const { sampleRows, preview, runPreview, goToStep } = editor;
  const hasSample = sampleRows.length > 0;

  // Auto-run once on entry. The step unmounts when navigating away, so
  // re-entering after edits triggers a fresh run.
  useEffect(() => {
    if (hasSample) runPreview();
    // mount-only by design
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="fe-step fe-step-preview">
      <div className="fe-step-preview__header">
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

      {!hasSample && (
        <div className="fe-step-preview__nosample">
          <p>
            No sample file loaded — preview isn&apos;t available. You can still save the
            format, or go back and upload a sample to test it first.
          </p>
          <Button variant="secondary" onClick={() => goToStep(STEP.SAMPLE)}>
            Go to Step 1
          </Button>
        </div>
      )}

      {hasSample && preview.loading && (
        <p className="fe-step-preview__status">Running preview…</p>
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
        <div className="fe-step-preview__error" role="alert">
          <p>{preview.error}</p>
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
          <ParsedPreviewTable
            rows={preview.result.preview_rows}
            total={preview.result.total_parsed}
          />
        </>
      )}
    </div>
  );
}