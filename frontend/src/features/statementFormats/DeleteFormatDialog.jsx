/**
 * @file DeleteFormatDialog.jsx
 * Confirm-delete wrapper around {@link ConfirmDialog} that also handles
 * the 409 "still linked to accounts" case by re-rendering the body with
 * the offending account ids and disabling the confirm button.
 */

import { useEffect, useState } from 'react';
import ConfirmDialog from '@/components/ConfirmDialog';
import { useToast } from '@/components/ToastContext';
import { deleteFormat } from './api';

/**
 * @component
 * @param {Object} props
 * @param {import('./api').FormatSummary|null} props.format - Null = closed.
 * @param {() => void} props.onCancel
 * @param {() => void} props.onDeleted - Called after a successful delete.
 */
export default function DeleteFormatDialog({ format, onCancel, onDeleted }) {
  const { addToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [linkedAccounts, setLinkedAccounts] = useState(null);

  // Reset transient state whenever a different format (or none) is targeted.
  useEffect(() => {
    setLoading(false);
    setLinkedAccounts(null);
  }, [format?.identifier]);

  if (!format) {
    return <ConfirmDialog open={false} title="" onConfirm={() => {}} onCancel={() => {}} />;
  }

  const numericId = Number(String(format.identifier).split(':')[1]);

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await deleteFormat(numericId);
      onDeleted();
    } catch (err) {
      if (err?.details?.linked_accounts) {
        setLinkedAccounts(err.details.linked_accounts);
      } else {
        addToast({ message: err.userMessage || err.message || 'Delete failed.' });
        onCancel();
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConfirmDialog
      open
      title="Delete statement format?"
      confirmLabel="Delete"
      confirmVariant="danger"
      confirmDisabled={!!linkedAccounts}
      loading={loading}
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
          <ul>
            {linkedAccounts.map((id) => <li key={id}>Account #{id}</li>)}
          </ul>
        </>
      ) : (
        <>
          <p>
            <strong>{format.display_name}</strong> will be permanently removed.
          </p>
          <p>Accounts already using it will keep their past imports, but you&apos;ll need to pick a different format for future uploads.</p>
        </>
      )}
    </ConfirmDialog>
  );
}