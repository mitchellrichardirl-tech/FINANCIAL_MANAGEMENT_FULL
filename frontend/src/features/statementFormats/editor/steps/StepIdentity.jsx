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
      <h2 className="m-0 mb-1.5 text-xl">Name</h2>
      <p className="m-0 mb-5 text-[#6c757d] text-sm">
        How this format appears in the format list and the account settings picker.
      </p>

      {duplicateNameError && (
        <div className="px-4 py-3.5 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] flex justify-between items-center gap-4" role="alert">
          <p className="m-0">{duplicateNameError}</p>
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
        <p className="m-0 mb-5 text-[#6c757d] text-sm">
          Will be shown as: <strong>{displayName}</strong>
        </p>
      )}
    </div>
  );
}
