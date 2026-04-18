import Button from '@/components/Button';

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
        <h2 className="m-0 mb-1 text-lg font-semibold">{title}</h2>
        {readOnlyHint && (
          <p className="m-0 mb-3 text-[13px] text-[#6c757d]">{readOnlyHint}</p>
        )}
      </div>

      {formats.length === 0 ? (
        <p className="p-5 text-center text-[#868e96] bg-[#f8f9fa] border border-dashed border-[#dee2e6] rounded">
          {emptyText}
        </p>
      ) : (
        <ul className="list-none m-0 p-0 border border-[#dee2e6] rounded overflow-hidden">
          {formats.map((f) => (
            <li
              key={f.identifier}
              className="flex justify-between items-center gap-4 py-3.5 px-4 border-b border-[#f1f3f5] last:border-b-0"
            >
              <div>
                <div className="font-semibold flex items-center gap-2">
                  {f.display_name}
                  {f.has_custom_processor && (
                    <span
                      title="This format uses custom parsing logic and can't be fully replicated by cloning."
                      className="text-[11px] font-medium uppercase tracking-wide bg-[#fff3cd] text-[#856404] py-0.5 px-1.5 rounded"
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
