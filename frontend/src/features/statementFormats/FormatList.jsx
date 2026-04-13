/**
 * @file FormatList.jsx
 * One titled section of the formats page (either "Your formats" or
 * "Built-in formats"), rendering a row per format with the actions
 * appropriate to that section.
 */

import Button from '@/components/Button';
import './FormatList.css';

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
    <section className="format-list">
      <div className="format-list__heading">
        <h2>{title}</h2>
        {readOnlyHint && <p className="format-list__hint">{readOnlyHint}</p>}
      </div>

      {formats.length === 0 ? (
        <p className="format-list__empty">{emptyText}</p>
      ) : (
        <ul className="format-list__items">
          {formats.map((f) => (
            <li key={f.identifier} className="format-list__item">
              <div className="format-list__main">
                <div className="format-list__name">
                  {f.display_name}
                  {f.has_custom_processor && (
                    <span
                      className="format-list__badge"
                      title="This format uses custom parsing logic and can't be fully replicated by cloning."
                    >
                      custom logic
                    </span>
                  )}
                </div>
                <div className="format-list__meta">
                  {f.bank_name} · {f.account_type}
                </div>
              </div>
              <div className="format-list__actions">
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