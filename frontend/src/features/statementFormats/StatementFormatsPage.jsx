import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '@/components/Button';
import { useToast } from '@/components/ToastContext';
import { useFormats } from './hooks';
import FormatList from './FormatList';
import DeleteFormatDialog from './DeleteFormatDialog';

export default function StatementFormatsPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const formatsQuery = useFormats();
  const formats = formatsQuery.data || [];
  const loading = formatsQuery.isLoading;
  const error = formatsQuery.error;

  const [deleting, setDeleting] = useState(null);

  const { userFormats, builtinFormats } = useMemo(() => ({
    userFormats: formats.filter((f) => f.source === 'user'),
    builtinFormats: formats.filter((f) => f.source === 'builtin'),
  }), [formats]);

  const handleClone = (format) =>
    navigate('/statement-formats/new', { state: { cloneFrom: format.identifier } });
  const handleEdit = (format) => navigate(`/statement-formats/${format.identifier}`);
  const handleDeleted = () => {
    setDeleting(null);
    addToast({ type: 'success', message: 'Format deleted.' });
    formatsQuery.refetch();
  };

  return (
    <div className="w-full max-w-[960px] h-full mx-auto pt-6 px-5 pb-[60px] box-border overflow-y-auto">
      <header className="flex justify-between items-start gap-5 mb-7">
        <div>
          <h1 className="m-0 mb-1 text-2xl font-semibold">Statement Formats</h1>
          <p className="m-0 text-[#6c757d] text-sm">
            Define how each bank&apos;s CSV/Excel export maps to transactions.
          </p>
        </div>
        <Button onClick={() => navigate('/statement-formats/new')}>+ New format</Button>
      </header>

      {loading && <p className="text-[#6c757d]">Loading formats…</p>}

      {error && (
        <div
          role="alert"
          className="py-3.5 px-4 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] flex justify-between items-center gap-4"
        >
          <p className="m-0">{error.userMessage || error.message || 'Failed to load formats.'}</p>
          <Button variant="secondary" onClick={() => formatsQuery.refetch()}>Retry</Button>
        </div>
      )}

      {!loading && !error && (
        <>
          <FormatList
            title="Your formats"
            formats={userFormats}
            emptyText="You haven't created any formats yet."
            onEdit={handleEdit}
            onClone={handleClone}
            onDelete={(f) => setDeleting(f)}
          />
          <FormatList
            title="Built-in formats"
            formats={builtinFormats}
            emptyText="No built-in formats available."
            onClone={handleClone}
            readOnlyHint="Built-in formats can't be edited directly — clone one to customise it."
          />
        </>
      )}

      <DeleteFormatDialog
        format={deleting}
        onCancel={() => setDeleting(null)}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
