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
    <section>
      <div className="mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        {readOnlyHint && (
          <p className="mt-1 text-sm text-gray-500">{readOnlyHint}</p>
        )}
      </div>
      {formats.length === 0 ? (
        <p className="py-8 text-center text-gray-500">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded-md border border-gray-200">
          {formats.map((f) => (
            <li
              key={f.identifier}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
              <div className="min-w-0">
                <div className="font-medium">
                  {f.display_name}
                  {f.has_custom_processor && (
                    <span
                      className="ml-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 align-middle text-xs font-medium text-amber-800"
                      title="This format uses custom parsing logic and can't be fully replicated by cloning."
                    >
                      custom logic
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-sm text-gray-500">
                  {f.bank_name} · {f.account_type}
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
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