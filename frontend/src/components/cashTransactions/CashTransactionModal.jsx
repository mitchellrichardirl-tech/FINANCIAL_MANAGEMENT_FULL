/**
 * @file CashTransactionModal.jsx
 * Shared shell for the two "create a Cash-account transaction" modals.
 *
 * Owns the modal chrome, the `saving` lifecycle, the direction/flag
 * controls, and the party cascade. Callers supply the variant-specific
 * details section (via `children`), the labels, any extra payload
 * fields, and a `detailsValid` flag.
 *
 * Consumed by {@link CreateCashTransactionModal} (manual entry) and
 * {@link GenerateCashFromReceiptModal} (from OCR'd receipt data).
 */
import { createPortal } from 'react-dom';
import { useState, useEffect, useId } from 'react';
import PartyCascadeFields from '@/components/cashTransactions/PartyCascadeFields';
import { useTaxonomyCascade } from '@/components/cashTransactions/useTaxonomyCascade';
import * as M from '@/styles/modalClasses';
/**
 * @component
 * @param {Object} props
 *
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(payload: Object) => Promise<void>} props.onConfirm
 *        Receives `{ ...extraPayload, partyId, isWithdrawal, isCredit,
 *        isKids, isOneOff }`. Should throw on failure; the parent
 *        handles toasting and closes on success.
 *
 * @param {string} props.title
 * @param {string} props.confirmLabel
 * @param {string} props.savingLabel
 * @param {string} [props.partyHint]
 *
 * @param {?number} [props.initialPartyId]
 *        Pre-selects the cascade (used for vendor→party suggestions).
 * @param {Object}  [props.extraPayload]
 *        Variant-specific fields merged into the confirm payload.
 * @param {boolean} [props.detailsValid]
 *        Caller-side validity of the details section. Combined with
 *        "a party is selected" to gate the confirm button.
 *
 * @param {React.ReactNode | ((state: {saving: boolean}) => React.ReactNode)} props.children
 *        The details section. Pass a function to read `saving`.
 *
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {Array<Object>} props.parties
 *
 * @param {(name:string, desc?:string)=>Promise<Object>} props.onCategoryCreated
 * @param {(name:string, categoryId:number, desc?:string)=>Promise<Object>} props.onSubCategoryCreated
 * @param {(name:string, subCategoryId:number, desc?:string)=>Promise<Object>} props.onTypeCreated
 * @param {(name:string, typeId:number, desc?:string)=>Promise<Object>} props.onPartyCreated
 *
 * @returns {JSX.Element|null}
 */
export default function CashTransactionModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  confirmLabel,
  savingLabel,
  partyHint,
  initialPartyId = null,
  extraPayload = {},
  detailsValid = true,
  children,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  // ── Flags ─────────────────────────────────────────────────────────
  const [isWithdrawal, setIsWithdrawal] = useState(true);
  const [isCredit, setIsCredit] = useState(false);
  const [isKids, setIsKids] = useState(false);
  const [isOneOff, setIsOneOff] = useState(false);
  const [saving, setSaving] = useState(false);
  /** Unique radio-group name so two instances can't ever interfere. */
  const directionName = useId();
  const cascade = useTaxonomyCascade({
    isOpen,
    categories,
    subCategories,
    types,
    parties,
    initialPartyId,
  });
  /** Reset flags + saving each time the modal opens. */
  useEffect(() => {
    if (!isOpen) return;
    setIsWithdrawal(true);
    setIsCredit(false);
    setIsKids(false);
    setIsOneOff(false);
    setSaving(false);
  }, [isOpen]);
  const canSave = !!cascade.partyId && detailsValid && !saving;
  const handleClose = () => {
    if (saving) return;
    onClose();
  };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };
  /** Close on Escape, unless a save is in flight. */
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e) => {
      if (e.key === 'Escape' && !saving) onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [isOpen, saving, onClose]);
  const handleConfirm = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await onConfirm({
        ...extraPayload,
        partyId: cascade.partyId,
        isWithdrawal,
        isCredit,
        isKids,
        isOneOff,
      });
      // Parent closes on success.
    } catch {
      setSaving(false);
    }
  };
  if (!isOpen) return null;
  return createPortal(
    <div className={M.BACKDROP} onClick={handleBackdropClick}>
      <div
        className={`${M.PANEL} max-w-2xl`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className={M.HEADER}>
          <h2 className={M.TITLE}>{title}</h2>
          <button
            className={M.CLOSE_BTN}
            onClick={handleClose}
            disabled={saving}
            aria-label="Close modal"
            type="button"
          >
            ×
          </button>
        </div>
        <div className={M.BODY}>
          {/* ── Variant-specific details ── */}
          {typeof children === 'function' ? children({ saving }) : children}
          {/* ── Direction + flags ── */}
          <div className={M.SECTION}>
            <h3 className={M.SECTION_TITLE}>Transaction</h3>
            <div className={M.FORM_GROUP}>
              <label className={M.FORM_LABEL}>Direction</label>
              <div className={M.RADIO_ROW}>
                <label className={M.OPTION}>
                  <input
                    type="radio"
                    name={directionName}
                    checked={isWithdrawal}
                    onChange={() => setIsWithdrawal(true)}
                    disabled={saving}
                  />
                  Withdrawal (cash out)
                </label>
                <label className={M.OPTION}>
                  <input
                    type="radio"
                    name={directionName}
                    checked={!isWithdrawal}
                    onChange={() => setIsWithdrawal(false)}
                    disabled={saving}
                  />
                  Lodgement (cash in)
                </label>
              </div>
            </div>
            <div className={M.FORM_GROUP}>
              <label className={M.OPTION}>
                <input
                  type="checkbox"
                  checked={isCredit}
                  onChange={(e) => setIsCredit(e.target.checked)}
                  disabled={saving}
                />
                Mark as income
              </label>
            </div>
            <div className={M.FORM_GROUP}>
              <label className={M.OPTION}>
                <input
                  type="checkbox"
                  checked={isKids}
                  onChange={(e) => setIsKids(e.target.checked)}
                  disabled={saving}
                />
                Kids
              </label>
            </div>
            <div className={M.FORM_GROUP}>
              <label className={M.OPTION}>
                <input
                  type="checkbox"
                  checked={isOneOff}
                  onChange={(e) => setIsOneOff(e.target.checked)}
                  disabled={saving}
                />
                One-off
              </label>
            </div>
          </div>
          {/* ── Party cascade ── */}
          <PartyCascadeFields
            cascade={cascade}
            disabled={saving}
            hint={partyHint}
            categories={categories}
            subCategories={subCategories}
            types={types}
            onCategoryCreated={onCategoryCreated}
            onSubCategoryCreated={onSubCategoryCreated}
            onTypeCreated={onTypeCreated}
            onPartyCreated={onPartyCreated}
          />
        </div>
        <div className={M.FOOTER}>
          <button
            type="button"
            className={M.BTN_SECONDARY}
            onClick={handleClose}
            disabled={saving}
          >
            Cancel
          </button>
          <button
            type="button"
            className={M.BTN_PRIMARY}
            onClick={handleConfirm}
            disabled={!canSave}
          >
            {saving ? savingLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
