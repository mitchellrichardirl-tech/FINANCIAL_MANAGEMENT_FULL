/**
 * @file editor/useFormatEditor.js
 * All editor state + actions in one hook so step components stay dumb.
 *
 * Owns four slices:
 *   - `draft`   — the StatementConfig-in-progress (editor shape, see configModel)
 *   - `step`    — wizard position + furthest step reached
 *   - `sample`  — uploaded sample file + its `/tabular/preview` result
 *   - `preview` — result of `previewFormat()` against the draft + sample rows
 *
 * Side-effecting actions (`loadSampleFile`, `runPreview`, `save`) call the
 * API directly. `save` returns a discriminated result so the component
 * layer can own toasts + navigation without the hook depending on
 * `useToast` / `useNavigate`.
 */

import { useCallback, useMemo, useState } from 'react';

import { previewFile } from '@/features/statements/api';
import {
  parseApiError,
  getUserMessage,
  isErrorCode,
  isDuplicate,
  ErrorCode,
} from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

import { previewFormat, createFormat, updateFormat } from '../api';
import { STEP } from '../constants';
import {
  emptyDraft,
  toApiShape,
  validate,
  mismatchFromParsedError,
} from '../configModel';

const logger = createLogger('statementFormats:useFormatEditor');

/** How many rows of the sample file to pull for column detection / preview. */
const SAMPLE_PREVIEW_ROWS = 50;

/**
 * @param {Object} opts
 * @param {'create'|'edit'} opts.mode
 * @param {Object} [opts.initialDraft] - Draft-shaped config (from `fromApiShape`). Defaults to `emptyDraft()`.
 * @param {number} [opts.numericId]    - DB id for `updateFormat()` when `mode === 'edit'`.
 */
export function useFormatEditor({ mode, initialDraft, numericId }) {
  // ── Draft ──────────────────────────────────────────────────────────
  const [draft, setDraft] = useState(() => initialDraft || emptyDraft());

  /**
   * Set a single (possibly nested) field on the draft by dot-path,
   * e.g. `updateDraft('date_config.column', 'Posted Date')`.
   * Shallow-clones along the path so reference equality still works
   * for memoization on untouched branches.
   */
  const updateDraft = useCallback((path, value) => {
    setDraft((prev) => setPath(prev, path, value));
  }, []);

  // ── Wizard position ────────────────────────────────────────────────
  const [step, setStep] = useState(STEP.SAMPLE);
  const [maxStepReached, setMaxStepReached] = useState(STEP.SAMPLE);

  const goToStep = useCallback((n) => {
    setStep(n);
    setMaxStepReached((m) => Math.max(m, n));
  }, []);

  const validation = useMemo(() => validate(draft), [draft]);

  /** Whether "Next" should be enabled for the *current* step. */
  const canGoNext = useMemo(() => {
    const errs = validation.errorsByStep[step] || [];
    return errs.length === 0;
  }, [validation, step]);

  const nextStep = useCallback(() => {
    if (step < STEP.PREVIEW) goToStep(step + 1);
  }, [step, goToStep]);

  const prevStep = useCallback(() => {
    if (step > STEP.SAMPLE) goToStep(step - 1);
  }, [step, goToStep]);

  // ── Sample file ────────────────────────────────────────────────────
  const [sample, setSample] = useState({
    file: null,
    previewData: null, // shape consumed by <PreviewTable> — { columns, data, column_types, total_rows }
    loading: false,
    error: null,
  });

  const loadSampleFile = useCallback(async (file) => {
    logger.info('Loading sample file', { name: file?.name, size: file?.size });
    setSample({ file, previewData: null, loading: true, error: null });
    // Stale preview no longer reflects the new file's rows.
    setPreview(EMPTY_PREVIEW);
    try {
      const previewData = await previewFile(file, SAMPLE_PREVIEW_ROWS);
      setSample({ file, previewData, loading: false, error: null });
    } catch (err) {
      const parsed = await parseApiError(err);
      logger.error('Sample file preview failed', parsed);
      setSample({
        file,
        previewData: null,
        loading: false,
        error: getUserMessage(parsed, 'Reading file'),
      });
    }
  }, []);

  const clearSampleFile = useCallback(() => {
    setSample({ file: null, previewData: null, loading: false, error: null });
    setPreview(EMPTY_PREVIEW);
  }, []);

  /** Column names available for <ColumnSelect>; empty when no sample loaded. */
  const sampleColumns = sample.previewData?.columns || [];
  const sampleColumnTypes = sample.previewData?.column_types || {};

  // ── Format preview (Step 5) ────────────────────────────────────────
  const [preview, setPreview] = useState(EMPTY_PREVIEW);

  const runPreview = useCallback(async () => {
    const rows = sample.previewData?.data;
    if (!rows?.length) {
      setPreview({
        ...EMPTY_PREVIEW,
        error: 'Upload a sample file in Step 1 to preview this format.',
      });
      return;
    }

    setPreview({ ...EMPTY_PREVIEW, loading: true });
    try {
      const result = await previewFormat(toApiShape(draft), rows);
      setPreview({ ...EMPTY_PREVIEW, result });
    } catch (err) {
      const parsed = await parseApiError(err);
      const mismatch =
        isErrorCode(parsed, ErrorCode.INVALID_FORMAT) &&
        mismatchFromParsedError(parsed);

      if (mismatch) {
        logger.warn('Preview column mismatch', parsed.details);
        setPreview({ ...EMPTY_PREVIEW, mismatch });
      } else {
        logger.error('Preview failed', parsed);
        setPreview({
          ...EMPTY_PREVIEW,
          error: getUserMessage(parsed, 'Previewing format'),
        });
      }
    }
  }, [draft, sample.previewData]);

  // ── Save ───────────────────────────────────────────────────────────
  const [saving, setSaving] = useState(false);
  /** Field-level error surfaced on Step 2 after a 409 name collision. */
  const [duplicateNameError, setDuplicateNameError] = useState(null);

  /**
   * Persist the draft.
   *
   * @returns {Promise<
   *   | { ok: true, result: Object }
   *   | { ok: false, handled: true }                          // hook dealt with it (e.g. 409 → jump to step 2)
   *   | { ok: false, handled: false, message: string }        // caller should toast
   * >}
   */
  const save = useCallback(async () => {
    setSaving(true);
    setDuplicateNameError(null);
    try {
      const config = toApiShape(draft);
      const result =
        mode === 'edit'
          ? await updateFormat(numericId, config)
          : await createFormat(config);
      logger.info('Format saved', { mode, id: result?.id ?? numericId });
      return { ok: true, result };
    } catch (err) {
      const parsed = await parseApiError(err);

      if (isDuplicate(parsed)) {
        // Name collision — bounce the user to the identity step with an
        // inline error; nothing for the caller to toast.
        setDuplicateNameError(
          getUserMessage(parsed) ||
            'A format with this bank name and account type already exists.',
        );
        goToStep(STEP.IDENTITY);
        return { ok: false, handled: true };
      }

      logger.error('Save failed', parsed);
      return {
        ok: false,
        handled: false,
        message: getUserMessage(parsed, 'Saving format'),
      };
    } finally {
      setSaving(false);
    }
  }, [draft, mode, numericId, goToStep]);

  // ── Public surface ─────────────────────────────────────────────────
  return {
    mode,

    draft,
    updateDraft,
    setDraft,
    validation,
    duplicateNameError,

    step,
    maxStepReached,
    canGoNext,
    goToStep,
    nextStep,
    prevStep,

    sample,
    sampleColumns,
    sampleColumnTypes,
    loadSampleFile,
    clearSampleFile,

    preview,
    runPreview,

    saving,
    save,
  };
}

// ---------------------------------------------------------------------
// internals
// ---------------------------------------------------------------------

const EMPTY_PREVIEW = Object.freeze({
  result: null,
  mismatch: null,
  error: null,
  loading: false,
});

/**
 * Immutably set `value` at `path` (dot-separated) on `obj`.
 * Only handles plain-object nesting, which is all the draft uses.
 */
function setPath(obj, path, value) {
  const keys = path.split('.');
  const next = { ...obj };
  let cur = next;
  for (let i = 0; i < keys.length - 1; i++) {
    cur[keys[i]] = { ...cur[keys[i]] };
    cur = cur[keys[i]];
  }
  cur[keys.at(-1)] = value;
  return next;
}