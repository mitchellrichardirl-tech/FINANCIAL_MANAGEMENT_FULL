/**
 * @file editor/steps/StepDefaults.jsx
 * Step 4 — config-level defaults applied to every imported row.
 *
 * Driven by `fetchFormatSchema().allowed_defaults` so adding a field to
 * `StatementConfig.ALLOWED_DEFAULT_FIELDS` on the backend shows up here
 * without a frontend change. Only `bool` is rendered today; other types
 * fall through to a visible "unsupported" notice rather than silently
 * disappearing.
 */

import Checkbox from '@/components/Checkbox';

/** Human labels for known default fields. Unknown names fall back to a prettified key. */
const LABELS = {
  is_kids: 'Mark all transactions as kids-related',
  is_one_off: 'Mark all transactions as one-off',
};

/**
 * @component
 * @param {Object} props
 * @param {ReturnType<import('../useFormatEditor').useFormatEditor>} props.editor
 * @param {import('../../api').FormatSchema} props.schema
 */
export default function StepDefaults({ editor, schema }) {
  const { draft, updateDraft } = editor;
  const fields = schema?.allowed_defaults ?? [];

  return (
    <div className="fe-step">
      <h2 className="m-0 mb-1.5 text-xl">Defaults</h2>
      <p className="m-0 mb-5 text-[#6c757d] text-sm">
        Optional. Values set here are applied to <em>every</em> transaction imported with
        this format. Use this for accounts that are always one category — e.g. a
        kids&apos; savings account.
      </p>

      {fields.length === 0 ? (
        <p className="p-10 text-center text-[#868e96] bg-[#f8f9fa] border border-dashed border-[#dee2e6] rounded-[6px]">
          No defaultable fields are configured.
        </p>
      ) : (
        <div className="flex flex-col gap-3.5 p-4 border border-[#e9ecef] rounded-[6px] bg-[#fcfcfd]">
          {fields.map(({ name, type }) => {
            if (type === 'bool') {
              return (
                <Checkbox
                  key={name}
                  checked={draft.defaults?.[name] === true}
                  onChange={(v) => updateDraft(`defaults.${name}`, v)}
                  label={LABELS[name] ?? prettify(name)}
                />
              );
            }
            // Future-proofing: surface unsupported types instead of hiding them.
            return (
              <div key={name} className="text-[13px] text-[#856404] bg-[#fff3cd] px-2.5 py-2 rounded">
                <code>{name}</code> ({type}) — control not implemented yet.
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function prettify(key) {
  return key.replace(/^is_/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
