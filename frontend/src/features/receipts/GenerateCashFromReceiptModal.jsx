/**
 * @file GenerateCashFromReceiptModal.jsx
 * Modal for creating a Cash-account transaction from a receipt.
 *
 * Shown from {@link ProcessReceipts} as the third disposition option
 * alongside "Save" and "Link to existing transaction". Used when the
 * purchase was paid for in cash so there is no bank transaction to
 * link to.
 *
 * Thin wrapper over {@link CashTransactionModal} supplying a read-only
 * receipt summary as the details section, plus the vendor→party
 * suggestion as the cascade's initial selection.
 */
import CashTransactionModal from '@/components/cashTransactions/CashTransactionModal';
import * as M from '@/styles/modalClasses';
/* ── Summary row styling ───────────────────────────────────────────── */
const SUMMARY_ROW = 'mb-2 flex items-baseline gap-2 last:mb-0';
const SUMMARY_LABEL = 'w-20 shrink-0 text-sm font-medium text-gray-600';
const SUMMARY_VALUE = 'text-sm text-gray-800';
/**
 * @component
 * @param {Object} props
 *
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(opts: {
 *   partyId: number,
 *   isWithdrawal: boolean,
 *   isCredit: boolean,
 *   isKids: boolean,
 *   isOneOff: boolean,
 * }) => Promise<void>} props.onConfirm
 *        Async callback that performs the generation. Should throw on
 *        failure; the parent handles toasting.
 *
 * @param {{vendor:string, date:string, amount:string}} props.receiptData
 *        The (possibly edited) OCR fields for display.
 *
 * @param {?number} props.suggestedPartyId
 *        Party id returned by `/parties/match`, or null. When set the
 *        cascade is pre-filled so the user can accept with one click.
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
export default function GenerateCashFromReceiptModal({
  isOpen,
  onClose,
  onConfirm,
  receiptData = {},
  suggestedPartyId,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  const amountNum = parseFloat(receiptData.amount);
  const amountDisplay = Number.isFinite(amountNum) ? amountNum.toFixed(2) : '—';
  return (
    <CashTransactionModal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Generate Cash Transaction"
      confirmLabel="Generate Transaction"
      savingLabel="Generating…"
      partyHint={
        suggestedPartyId
          ? 'A party has been suggested from the vendor name. Change it if needed.'
          : 'Select the party for this transaction. You can create a new one at any level.'
      }
      initialPartyId={suggestedPartyId ?? null}
      categories={categories}
      subCategories={subCategories}
      types={types}
      parties={parties}
      onCategoryCreated={onCategoryCreated}
      onSubCategoryCreated={onSubCategoryCreated}
      onTypeCreated={onTypeCreated}
      onPartyCreated={onPartyCreated}
    >
      <div className={M.SECTION}>
        <h3 className={M.SECTION_TITLE}>Receipt</h3>
        <p className={M.HINT}>
          A new transaction will be created on the <strong>Cash</strong>{' '}
          account using these details.
        </p>
        <div className={M.READONLY_VALUE}>
          <div className={SUMMARY_ROW}>
            <span className={SUMMARY_LABEL}>Vendor:</span>
            <span className={SUMMARY_VALUE}>{receiptData.vendor || '—'}</span>
          </div>
          <div className={SUMMARY_ROW}>
            <span className={SUMMARY_LABEL}>Date:</span>
            <span className={SUMMARY_VALUE}>{receiptData.date || '—'}</span>
          </div>
          <div className={SUMMARY_ROW}>
            <span className={SUMMARY_LABEL}>Amount:</span>
            <span className={SUMMARY_VALUE}>{amountDisplay}</span>
          </div>
        </div>
      </div>
    </CashTransactionModal>
  );
}