import { useEffect, useState } from 'react';
import ConfirmDialog from '@/components/ConfirmDialog';
import { useToast } from '@/components/ToastContext';
import { parseApiError, getUserMessage } from '@/lib/apiErrors';
import { useDeleteFormat } from './hooks';

export default function DeleteFormatDialog({ format, onCancel, onDeleted }) {
  const { addToast } = useToast();
  const deleteMutation = useDeleteFormat();
  const [linkedAccounts, setLinkedAccounts] = useState(null);

  useEffect(() => {
    setLinkedAccounts(null);
  }, [format?.identifier]);

  if (!format) {
    return <ConfirmDialog open={false} title="" onConfirm={() => {}} onCancel={() => {}} />;
  }

  const numericId = Number(String(format.identifier).split(':')[1]);

  const handleConfirm = async () => {
    try {
      await deleteMutation.mutateAsync(numericId);
      onDeleted();
    } catch (err) {
      const parsed = await parseApiError(err);
      if (parsed.details?.linked_accounts) {
        setLinkedAccounts(parsed.details.linked_accounts);
      } else {
        addToast({ message: getUserMessage(parsed, 'Deleting format') });
        onCancel();
      }
    }
  };

  return (
    <ConfirmDialog
      open
      title="Delete statement format?"
      confirmLabel="Delete"
      confirmVariant="danger"
      confirmDisabled={!!linkedAccounts}
      loading={deleteMutation.isPending}
      onConfirm={handleConfirm}
      onCancel={onCancel}
    >
      {linkedAccounts ? (
        <>
          <p>
            <strong>{format.display_name}</strong> is still assigned to{' '}
            {linkedAccounts.length === 1 ? 'an account' : `${linkedAccounts.length} accounts`} and
            can&apos;t be deleted yet.
          </p>
          <p>Reassign these accounts to another format first:</p>
          <ul className="list-disc pl-6">
            {linkedAccounts.map((id) => <li key={id}>Account #{id}</li>)}
          </ul>
        </>
      ) : (
        <>
          <p>
            <strong>{format.display_name}</strong> will be permanently removed.
          </p>
          <p>
            Accounts already using it will keep their past imports, but you&apos;ll need
            to pick a different format for future uploads.
          </p>
        </>
      )}
    </ConfirmDialog>
  );
}
