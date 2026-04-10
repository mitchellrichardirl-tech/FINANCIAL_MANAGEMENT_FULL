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
import './StatementFormatsPage.css';

export default function StatementFormatsPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const { formats, loading, error, refetch } = useStatementFormats();

  // Format pending deletion — null when dialog closed.
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
    <div className="sfp">
      <header className="sfp__header">
        <div>
          <h1>Statement Formats</h1>
          <p className="sfp__sub">
            Define how each bank&apos;s CSV/Excel export maps to transactions.
          </p>
        </div>
        <Button onClick={() => navigate('/statement-formats/new')}>
          + New format
        </Button>
      </header>

      {loading && <p className="sfp__status">Loading formats…</p>}

      {error && (
        <div className="sfp__error" role="alert">
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