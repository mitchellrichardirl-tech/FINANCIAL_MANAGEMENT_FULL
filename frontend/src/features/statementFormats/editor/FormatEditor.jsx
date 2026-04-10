/**
 * @file editor/FormatEditor.jsx
 * Wizard container: stepper + current step body + Back / Next / Save
 * footer. All state lives in `useFormatEditor`; this component only
 * wires navigation, toasts and routing.
 */

import { useNavigate } from 'react-router-dom';

import Button from '@/components/Button';
import { useToast } from '@/components/ToastContext';

import { STEP, STEP_LABELS } from '../constants';
import { useFormatEditor } from './useFormatEditor';
import Stepper from './Stepper';

import StepSampleFile from './steps/StepSampleFile';
import StepIdentity from './steps/StepIdentity';
import StepColumns from './steps/StepColumns';
import StepDefaults from './steps/StepDefaults';
import StepPreview from './steps/StepPreview';

import './FormatEditor.css';

/**
 * @component
 * @param {Object} props
 * @param {'create'|'edit'} props.mode
 * @param {Object} [props.initialDraft] - Draft-shape config (already run through `fromApiShape`).
 * @param {number} [props.numericId]    - Required when `mode === 'edit'`.
 * @param {import('../api').FormatSchema} props.schema
 */
export default function FormatEditor({ mode, initialDraft, numericId, schema }) {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const editor = useFormatEditor({ mode, initialDraft, numericId });
  const { step, canGoNext, nextStep, prevStep, goToStep, maxStepReached, saving } = editor;

  const isLast = step === STEP.PREVIEW;

  const handleSave = async () => {
    const outcome = await editor.save();
    if (outcome.ok) {
      addToast({
        type: 'success',
        message: mode === 'edit' ? 'Format updated.' : 'Format created.',
      });
      navigate('/statement-formats');
    } else if (!outcome.handled) {
      addToast({ message: outcome.message });
    }
    // outcome.handled === true → hook already jumped to the right step
  };

  return (
    <div className="format-editor">
      <Stepper
        labels={STEP_LABELS}
        current={step}
        maxReachable={maxStepReached}
        onStepClick={goToStep}
      />

      <div className="format-editor__body">
        {step === STEP.SAMPLE && <StepSampleFile editor={editor} />}
        {step === STEP.IDENTITY && <StepIdentity editor={editor} />}
        {step === STEP.COLUMNS && <StepColumns editor={editor} />}
        {step === STEP.DEFAULTS && <StepDefaults editor={editor} schema={schema} />}
        {step === STEP.PREVIEW && <StepPreview editor={editor} />}
      </div>

      <div className="format-editor__footer">
        <div className="format-editor__footer-left">
          <Button variant="ghost" onClick={() => navigate('/statement-formats')}>
            Cancel
          </Button>
        </div>
        <div className="format-editor__footer-right">
          {step > STEP.SAMPLE && (
            <Button variant="secondary" onClick={prevStep} disabled={saving}>
              Back
            </Button>
          )}
          {!isLast && (
            <Button onClick={nextStep} disabled={!canGoNext}>
              Next
            </Button>
          )}
          {isLast && (
            <Button
              onClick={handleSave}
              loading={saving}
              disabled={!editor.validation.ok}
            >
              {mode === 'edit' ? 'Save changes' : 'Create format'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}