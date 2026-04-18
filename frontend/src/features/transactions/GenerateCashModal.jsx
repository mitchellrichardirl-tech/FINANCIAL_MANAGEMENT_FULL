import { useState, useEffect } from 'react';
import {
  overlayCls, dialogCls, headerCls, headerTitleCls, closeBtnCls,
  bodyCls, sectionCls, formHintCls, footerCls, cancelBtnCls, saveBtnCls,
} from './_modalShell';

export default function GenerateCashModal({ isOpen, onClose, onConfirm, transactionCount }) {
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) setSaving(false);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setSaving(true);
    try {
      await onConfirm();
    } catch {
      setSaving(false);
    }
  };

  const handleClose = () => { if (!saving) onClose(); };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  const plural = transactionCount === 1 ? '' : 's';

  return (
    <div onClick={handleBackdropClick} className={overlayCls}>
      <div onClick={(e) => e.stopPropagation()} className={dialogCls}>
        <div className={headerCls}>
          <h2 className={headerTitleCls}>Generate Cash Transactions</h2>
          <button type="button" onClick={handleClose} disabled={saving} aria-label="Close modal" className={closeBtnCls}>
            ×
          </button>
        </div>

        <div className={bodyCls}>
          <div className={sectionCls}>
            <p className={formHintCls}>
              This will create{' '}
              <strong>{transactionCount} new transaction{plural}</strong>{' '}
              on the <strong>Cash</strong> account — one for each selected transaction, with the amount negated and the date, description and party copied from the source.
            </p>
            <p className={formHintCls}>
              Transactions that already have a cash counterpart will be skipped. Transactions already on the Cash account will be rejected.
            </p>
          </div>
        </div>

        <div className={footerCls}>
          <button type="button" onClick={handleClose} disabled={saving} className={cancelBtnCls}>
            Cancel
          </button>
          <button type="button" onClick={handleConfirm} disabled={saving || transactionCount === 0} className={saveBtnCls}>
            {saving ? 'Generating…' : `Generate ${transactionCount} Transaction${plural}`}
          </button>
        </div>
      </div>
    </div>
  );
}
