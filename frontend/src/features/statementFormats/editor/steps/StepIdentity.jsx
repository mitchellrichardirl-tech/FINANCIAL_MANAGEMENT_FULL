/**
 * @file editor/steps/StepIdentity.jsx
 * Step 2 — bank name + account type. Combined as `display_name` in the
 * format list and the upload page's account picker.
 */

import FormField from '@/components/FormField';
import TextInput from '@/components/TextInput';

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepIdentity({ editor }) {
  const { draft, updateDraft, validation, duplicateNameError } = editor;
  const errors = validation.errorsByField;

  const displayName =
    draft.bank_name && draft.account_type
      ? `${draft.bank_name} ${draft.account_type}`
      : '';

  return (
    <div className="fe-step">
      <h2>Name</h2>
      <p className="fe-step__sub">
        How this format appears in the format list and the account settings picker.
      </p>

      {duplicateNameError && (
        <div className="fe-step-sample__error" role="alert">
          <p>{duplicateNameError}</p>
        </div>
      )}

      <FormField
        label="Bank name"
        required
        error={errors.bank_name}
        htmlFor="bank-name"
      >
        <TextInput
          id="bank-name"
          value={draft.bank_name}
          onChange={(v) => updateDraft('bank_name', v)}
          placeholder="e.g. AIB"
        />
      </FormField>

      <FormField
        label="Account type"
        required
        error={errors.account_type}
        help="The variant of export — e.g. Current Account, Credit Card."
        htmlFor="account-type"
      >
        <TextInput
          id="account-type"
          value={draft.account_type}
          onChange={(v) => updateDraft('account_type', v)}
          placeholder="e.g. Current Account"
        />
      </FormField>

      {displayName && (
        <p className="fe-step__sub">
          Will be shown as: <strong>{displayName}</strong>
        </p>
      )}
    </div>
  );
}