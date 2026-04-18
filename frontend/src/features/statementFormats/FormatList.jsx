/**
 * @file FormatList.jsx
 * One titled section of the formats page (either "Your formats" or
 * "Built-in formats"), rendering a row per format with the actions
 * appropriate to that section.
 */

import Button from '@/components/Button';

/**
 * @component
 * @param {Object} props
 * @param {string} props.title
 * @param {import('./api').FormatSummary[]} props.formats
 * @param {string} props.emptyText
 * @param {string} [props.readOnlyHint] - Shown under the title for the built-in section.
 * @param {(f) => void} [props.onEdit]   - Omit to hide the Edit action.
 * @param {(f) => void} [props.onClone]
 * @param {(f) => void} [props.onDelete] - Omit to hide the Delete action.
 */
export default function FormatList({
  title,
  formats,
  emptyText,
  readOnlyHint,
  onEdit,
  onClone,
  onDelete,
}) {
  return (
    <section className="mb-9">
      <div>
        <h2 className="m-0 mb-1 text-lg">{title}</h2>
        {readOnlyHint && <p className="m-0 mb-3 text-[13px] text-[#6c757d]">{readOnlyHint}</p>}
      </div>

      {formats.length === 0 ? (
        <p className="p-5 text-center text-[#868e96] bg-[#f8f9fa] border border-dashed border-[#dee2e6] rounded">{emptyText}</p>
      ) : (
        <ul className="list-none m-0 p-0 border border-[#dee2e6] rounded overflow-hidden">
          {formats.map((f, idx) => (
            <li
              key={f.identifier}
              className={`flex justify-between items-center gap-4 px-4 py-3.5 ${
                idx < formats.length - 1 ? 'border-b border-[#f1f3f5]' : ''
              }`}
            >
              <div>
                <div className="font-semibold flex items-center gap-2">
                  {f.display_name}
                  {f.has_custom_processor && (
                    <span
                      className="text-[11px] font-medium uppercase tracking-[0.03em] bg-[#fff3cd] text-[#856404] px-1.5 py-0.5 rounded-[3px]"
                      title="This format uses custom parsing logic and can't be fully replicated by cloning."
                    >
                      custom logic
                    </span>
                  )}
                </div>
                <div className="text-[13px] text-[#6c757d] mt-0.5">
                  {f.bank_name} · {f.account_type}
                </div>
              </div>
              <div className="flex gap-1.5 shrink-0">
                {onEdit && f.editable && (
                  <Button variant="secondary" onClick={() => onEdit(f)}>Edit</Button>
                )}
                {onClone && (
                  <Button variant="ghost" onClick={() => onClone(f)}>Clone</Button>
                )}
                {onDelete && f.editable && (
                  <Button variant="ghost" onClick={() => onDelete(f)}>Delete</Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
