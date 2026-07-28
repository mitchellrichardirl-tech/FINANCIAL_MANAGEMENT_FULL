/**
 * @file CreateCashTransactionModal.jsx
 * Modal for creating a Cash-account transaction from manually entered
 * information — no bank statement row, no receipt.
 *
 * Shown from {@link CategorizeTransactions}. Thin wrapper over
 * {@link CashTransactionModal} supplying editable date / description /
 * amount fields as the details section.
 */
import { useState, useEffect } from 'react';
import CashTransactionModal from '@/components/cashTransactions/CashTransactionModal';
import * as M from '@/styles/modalClasses';
/** Today's date as a YYYY-MM-DD string (local time). */
function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
/**
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(opts: {
 *   transactionDate: string,
 *   description: string,
 *   amount: number,
 *   partyId: number,
 *   isWithdrawal: boolean,
 *   isCredit: boolean,
 *   isKids: boolean,
 *   isOneOff: boolean,
 * }) => Promise<void>} props.onConfirm
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {Array<Object>} props.parties
 * @param {(name:string, desc?:string)=>Promise<Object>} props.onCategoryCreated
 * @param {(name:string, categoryId:number, desc?:string)=>Promise<Object>} props.onSubCategoryCreated
 * @param {(name:string, subCategoryId:number, desc?:string)=>Promise<Object>} props.onTypeCreated
 * @param {(name:string, typeId:number, desc?:string)=>Promise<Object>} props.onPartyCreated
 * @returns {JSX.Element|null}
 */
export default function CreateCashTransactionModal({
  isOpen,
  onClose,
  onConfirm,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  const [transactionDate, setTransactionDate] = useState(todayIso());
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  /** Reset the editable fields each time the modal opens. */
  useEffect(() => {
    if (!isOpen) return;
    setTransactionDate(todayIso());
    setDescription('');
    setAmount('');
  }, [isOpen]);
  const amountNum = parseFloat(amount);
  const detailsValid =
    !!transactionDate &&
    description.trim() !== '' &&
    Number.isFinite(amountNum) &&
    amountNum > 0;
  return (
    <CashTransactionModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="New Cash Transaction"
      confirmLabel="Create Transaction"
      savingLabel="Creating…"
      partyHint="Select the party for this transaction. You can create a new one at any level."
      detailsValid={detailsValid}
      extraPayload={{
        transactionDate,
        description: description.trim(),
        amount: amountNum,
      }}
      categories={categories}
      subCategories={subCategories}
      types={types}
      parties={parties}
      onCategoryCreated={onCategoryCreated}
      onSubCategoryCreated={onSubCategoryCreated}
      onTypeCreated={onTypeCreated}
      onPartyCreated={onPartyCreated}
    >
      {({ saving }) => (
        <div className={M.SECTION}>
          <h3 className={M.SECTION_TITLE}>Details</h3>
          <p className={M.HINT}>
            A new transaction will be created on the <strong>Cash</strong>{' '}
            account using these details.
          </p>
          <div className={M.FORM_GROUP}>
            <label htmlFor="cash-date" className={M.FORM_LABEL}>
              Date
            </label>
            <input
              id="cash-date"
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              disabled={saving}
              className={M.FIELD}
            />
          </div>
          <div className={M.FORM_GROUP}>
            <label htmlFor="cash-description" className={M.FORM_LABEL}>
              Description
            </label>
            <input
              id="cash-description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Coffee at Bewley's"
              disabled={saving}
              className={M.FIELD}
            />
          </div>
          <div className={M.FORM_GROUP}>
            <label htmlFor="cash-amount" className={M.FORM_LABEL}>
              Amount
            </label>
            <input
              id="cash-amount"
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              disabled={saving}
              className={M.FIELD}
            />
          </div>
        </div>
      )}
    </CashTransactionModal>
  );
}