import FormField from '@/components/FormField';
import TextInput from '@/components/TextInput';

export default function StepIdentity({ editor }) {
  const { draft, updateDraft, validation, duplicateNameError } = editor;
  const errors = validation.errorsByField;

  const displayName =
    draft.bank_name && draft.account_type
      ? `${draft.bank_name} ${draft.account_type}`
      : '';

  return (
    <div>
      <h2 className="m-0 mb-1.5 text-xl">Name</h2>
      <p className="m-0 mb-5 text-[#6c757d] text-sm">
        How this format appears in the format list and the account settings picker.
      </p>

      {duplicateNameError && (
        <div
          className="py-3.5 px-4 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] mb-4"
          role="alert"
        >
          <p className="m-0">{duplicateNameError}</p>
        </div>
      )}

      <FormField label="Bank name" required error={errors.bank_name} htmlFor="bank-name">
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
