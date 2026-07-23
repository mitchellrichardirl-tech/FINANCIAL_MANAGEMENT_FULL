/**
 * @file StatementFormatsPage.jsx
 * Route: `/statement-formats`. Lists built-in and user-defined formats
 * and links into the editor for create / edit / clone.
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import Button from '@/components/Button';
import { useToast } from '@/components/ToastContext';

import { useStatementFormats } from './useStatementFormats';
import FormatList from './FormatList';
import DeleteFormatDialog from './DeleteFormatDialog';
// ❌ removed: import './StatementFormatsPage.css'

export default function StatementFormatsPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { formats, loading, error, refetch } = useStatementFormats();

  const [deleting, setDeleting] = useState(null);

  const { userFormats, builtinFormats } = useMemo(() => {
    const userFormats = formats.filter((f) => f.source === 'user');
    const builtinFormats = formats.filter((f) => f.source === 'builtin');
    return { userFormats, builtinFormats };
  }, [formats]);

  const handleClone = (format) => {
    navigate('/statement-formats/new', { state: { cloneFrom: format.identifier } });
  };

  const handleEdit = (format) => {
    navigate(`/statement-formats/${format.identifier}`);
  };

  const handleDeleted = () => {
    setDeleting(null);
    addToast({ type: 'success', message: 'Format deleted.' });
    refetch();
  };

  return (

    <div className="mx-auto h-full w-full max-w-[960px] overflow-y-auto px-5 pt-6 pb-15">

      {/* .sfp__header */}
      <header className="mb-7 flex items-start justify-between gap-5">
        <div>
          {/* .sfp__header h1 — preflight already zeroes margins */}
          <h1 className="mb-1">Statement Formats</h1>
          {/* .sfp__sub */}
          <p className="m-0 text-sm text-gray-500">
            Define how each bank&apos;s CSV/Excel export maps to transactions.
          </p>
        </div>
        <Button onClick={() => navigate('/statement-formats/new')}>
          + New format
        </Button>
      </header>

      {/* .sfp__status */}
      {loading && <p className="text-gray-500">Loading formats…</p>}

      {/* .sfp__error */}
      {error && (
        <div
          className="flex items-center justify-between gap-4 rounded border border-danger-border bg-danger-bg px-4 py-3.5 text-danger-text"
          role="alert"
        >
          <p>{error.userMessage || error.message || 'Failed to load formats.'}</p>
          <Button variant="secondary" onClick={refetch}>Retry</Button>
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