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
// ❌ removed: import './StepDefaults.css'

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
      <h2>Defaults</h2>
      <p className="fe-step__sub">
        Optional. Values set here are applied to <em>every</em> transaction imported with
        this format. Use this for accounts that are always one category — e.g. a
        kids&apos; savings account.
      </p>

      {fields.length === 0 ? (
        <p className="fe-step__placeholder">No defaultable fields are configured.</p>
      ) : (
        <div className="flex flex-col gap-3.5 rounded-md border border-gray-200 bg-[#fcfcfd] p-4">
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
            return (
              <div
                key={name}
                className="rounded bg-amber-100 px-2.5 py-2 text-[13px] text-amber-800"
              >
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