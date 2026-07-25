/**
 * @file TransactionRow.jsx
 * Single row of {@link TransactionTable} with inline edit mode.
 *
 * In **view mode** each cell shows the denormalized value
 * (`transaction.*_name`) with a row-level "Edit" button and an optional
 * "Remap party" quick-action.
 *
 * In **edit mode** the taxonomy columns switch to
 * {@link DropdownWithCreate} selects that:
 *  - Cascade upward: selecting a party auto-fills type → subcat → cat.
 *  - Cascade downward: selecting a higher level clears lower levels.
 *  - Detect conflicts: changing a parent when a party is already
 *    selected triggers a {@link RemapPartyPrompt} asking whether to
 *    remap the party globally or just for this transaction.
 *
 * The row does **not** call the API directly; it invokes callbacks
 * (`onUpdate`, `onFindOrCreateParty`) and lets the parent handle
 * persistence and cache invalidation.
 */

import { useState, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import Checkbox from '@/components/Checkbox';
import RemapPartyPrompt from './RemapPartyPrompt';
import ReceiptIcon from './ReceiptIcon';
import ReceiptViewModal from './ReceiptViewModal';
import ReceiptUploadModal from './ReceiptUploadModal';
import { createLogger } from '@/lib/logger';
import { useToast } from '@/components/ToastContext';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('TransactionRow');
/* ── Cell bases ────────────────────────────────────────────────────── */
const TD = 'border-b border-gray-200 p-2 align-middle text-sm';
/** Cells that clip with an ellipsis. `max-w-0` lets the table algorithm size them. */
const TRUNC = 'max-w-0 truncate';
/** Description cells expand on hover to reveal full text. */
const TRUNC_EXPAND = `${TRUNC} hover:overflow-visible hover:whitespace-normal hover:break-words`;
const VIEW = 'block py-1';
const ACTION_BTN =
  'cursor-pointer rounded border-none px-2.5 py-1.5 text-sm text-white ' +
  'transition-[background-color,opacity] disabled:cursor-not-allowed disabled:opacity-50';
/**
 * Editable transaction table row.
 * (full docblock unchanged)
 */
export default function TransactionRow({
  transaction,
  accounts,
  allCategories,
  allSubCategories,
  allTypes,
  allParties,
  onUpdate,
  onOpenCreateModal,
  isSelected,
  onSelectionChange,
  onRemapParty,
  onFindOrCreateParty,
  onReceiptChange,
}) {
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [reuseParty, setReuseParty] = useState(null);
  const [receiptModalMode, setReceiptModalMode] = useState(null);
  // ── Edit lifecycle ────────────────────────────────────────────────
  const startEditing = () => {
    setDraft({
      category_id:
        allCategories.find((c) => c.category === transaction.category_name)?.id ?? null,
      sub_category_id:
        allSubCategories.find((sc) => sc.sub_category === transaction.sub_category_name)?.id ??
        null,
      type_id: allTypes.find((t) => t.type === transaction.type_name)?.id ?? null,
      party_id: transaction.party_id ?? null,
      is_kids: transaction.is_kids || false,
      is_one_off: transaction.is_one_off || false,
      cleaned_description: transaction.cleaned_description || '',
      is_credit: transaction.is_credit || false,
    });
    setError(null);
    setConflict(null);
    setReuseParty(null);
    setIsEditing(true);
  };
  const cancelEditing = () => {
    setDraft(null);
    setConflict(null);
    setReuseParty(null);
    setError(null);
    setIsEditing(false);
  };
  // ── Draft builders for hierarchy changes ──────────────────────────
  const buildDraftAfterTypeChange = (currentDraft, newTypeId) => {
    const type = newTypeId ? allTypes.find((t) => t.id === newTypeId) : null;
    const subCategory = type
      ? allSubCategories.find((sc) => sc.id === type.sub_category_id)
      : null;
    return {
      ...currentDraft,
      category_id: subCategory?.category_id ?? currentDraft.category_id,
      sub_category_id: type?.sub_category_id ?? currentDraft.sub_category_id,
      type_id: newTypeId,
      party_id: null,
    };
  };
  const buildDraftAfterSubCategoryChange = (currentDraft, newSubCategoryId) => {
    const subCategory = newSubCategoryId
      ? allSubCategories.find((sc) => sc.id === newSubCategoryId)
      : null;
    return {
      ...currentDraft,
      category_id: subCategory?.category_id ?? currentDraft.category_id,
      sub_category_id: newSubCategoryId,
      type_id: null,
      party_id: null,
    };
  };
  const buildDraftAfterCategoryChange = (currentDraft, newCategoryId) => ({
    ...currentDraft,
    category_id: newCategoryId,
    sub_category_id: null,
    type_id: null,
    party_id: null,
  });
  // ── Conflict detection ────────────────────────────────────────────
  const maybeShowConflict = (currentDraft, newDraftAfter, applyImmediately) => {
    if (!currentDraft.party_id) {
      applyImmediately(newDraftAfter);
      return;
    }
    const oldParty = allParties.find((p) => p.id === currentDraft.party_id);
    setConflict({
      oldDraft: currentDraft,
      oldPartyId: currentDraft.party_id,
      oldPartyName: oldParty?.name ?? 'this party',
      newDraftAfter,
    });
  };
  // ── Change handlers ───────────────────────────────────────────────
  const handleCategoryChange = (categoryId) => {
    const id = categoryId ? parseInt(categoryId) : null;
    maybeShowConflict(draft, buildDraftAfterCategoryChange(draft, id), setDraft);
  };
  const handleSubCategoryChange = (subCategoryId) => {
    const id = subCategoryId ? parseInt(subCategoryId) : null;
    maybeShowConflict(draft, buildDraftAfterSubCategoryChange(draft, id), setDraft);
  };
  const handleTypeChange = (typeId) => {
    const id = typeId ? parseInt(typeId) : null;
    maybeShowConflict(draft, buildDraftAfterTypeChange(draft, id), setDraft);
  };
  const handlePartyChange = (partyId) => {
    const id = partyId ? parseInt(partyId) : null;
    const party = allParties.find((p) => p.id === id);
    const type = party ? allTypes.find((t) => t.id === party.type_id) : null;
    const subCategory = type
      ? allSubCategories.find((sc) => sc.id === type.sub_category_id)
      : null;
    setDraft((prev) => ({
      ...prev,
      category_id: subCategory?.category_id ?? prev.category_id,
      sub_category_id: type?.sub_category_id ?? prev.sub_category_id,
      type_id: party?.type_id ?? prev.type_id,
      party_id: id,
    }));
    setReuseParty(null);
  };
  const handleReceiptIconClick = () => {
    if (transaction.receipt_id) {
      setReceiptModalMode('view');
    } else {
      setReceiptModalMode('upload');
    }
  };
  // ── Conflict prompt handlers ──────────────────────────────────────
  const handleRemapAll = () => {
    if (!conflict) return;
    const { oldPartyId, newDraftAfter } = conflict;
    setConflict(null);
    setReuseParty(null);
    setDraft(newDraftAfter);
    onRemapParty(oldPartyId);
    cancelEditing();
  };
  const handleThisOnly = () => {
    if (!conflict) return;
    const { oldPartyName, newDraftAfter } = conflict;
    setConflict(null);
    setReuseParty({ partyName: oldPartyName, typeId: newDraftAfter.type_id });
    setDraft(newDraftAfter);
  };
  const handleCancelConflict = () => {
    if (!conflict) return;
    setDraft(conflict.oldDraft);
    setConflict(null);
  };
  // ── Persist ───────────────────────────────────────────────────────
  const persistSave = async (partyId) => {
    if (!draft) return;
    setIsSaving(true);
    setError(null);
    try {
      await onUpdate(transaction.id, {
        party_id: partyId,
        is_kids: draft.is_kids,
        is_one_off: draft.is_one_off,
        cleaned_description: draft.cleaned_description,
        is_credit: draft.is_credit,
      });
      setIsEditing(false);
      setDraft(null);
      setReuseParty(null);
    } catch {
      setError(true);
    } finally {
      setIsSaving(false);
    }
  };
  const saveChanges = async () => {
    if (!draft) return;
    if (reuseParty) {
      const targetTypeId = draft.type_id ?? reuseParty.typeId;
      if (!targetTypeId) {
        await persistSave(null);
        return;
      }
      setIsSaving(true);
      try {
        const targetPartyId = await onFindOrCreateParty(reuseParty.partyName, targetTypeId);
        await persistSave(targetPartyId);
      } catch (err) {
        logger.error('Failed to find/create party:', err);
        addToast({
          message: `Failed to reassign party: ${err.userMessage || err.message}`,
          type: 'error',
        });
        setError(true);
        setIsSaving(false);
      }
      return;
    }
    await persistSave(draft.party_id);
  };
  // ── Filtered dropdown options ─────────────────────────────────────
  const filteredSubCategories = useMemo(() => {
    if (!isEditing || !draft?.category_id) return allSubCategories;
    return allSubCategories.filter((sc) => sc.category_id === draft.category_id);
  }, [isEditing, draft?.category_id, allSubCategories]);
  const filteredTypes = useMemo(() => {
    if (!isEditing) return allTypes;
    if (draft?.sub_category_id) {
      return allTypes.filter((t) => t.sub_category_id === draft.sub_category_id);
    }
    if (draft?.category_id) {
      const subCatIds = filteredSubCategories.map((sc) => sc.id);
      return allTypes.filter((t) => subCatIds.includes(t.sub_category_id));
    }
    return allTypes;
  }, [isEditing, draft?.category_id, draft?.sub_category_id, filteredSubCategories, allTypes]);
  const filteredParties = useMemo(() => {
    if (!isEditing) return allParties;
    if (draft?.type_id) {
      return allParties.filter((p) => p.type_id === draft.type_id);
    }
    if (draft?.sub_category_id || draft?.category_id) {
      const typeIds = filteredTypes.map((t) => t.id);
      return allParties.filter((p) => typeIds.includes(p.type_id));
    }
    return allParties;
  }, [isEditing, draft?.category_id, draft?.sub_category_id, draft?.type_id, filteredTypes, allParties]);
  // ── Create handlers ───────────────────────────────────────────────
  const handleCreateCategory = () => {
    onOpenCreateModal('category', null, '', (newCategory) => {
      if (newCategory?.id) {
        setDraft((prev) => ({
          ...prev,
          category_id: newCategory.id,
          sub_category_id: null,
          type_id: null,
          party_id: null,
        }));
      }
    });
  };
  const handleCreateSubCategory = () => {
    const category = allCategories.find((c) => c.id === draft.category_id);
    onOpenCreateModal('sub_category', category.id, category.category, (newSC) => {
      if (newSC?.id) {
        setDraft((prev) => ({
          ...prev,
          sub_category_id: newSC.id,
          type_id: null,
          party_id: null,
        }));
      }
    });
  };
  const handleCreateType = () => {
    const subCategory = allSubCategories.find((sc) => sc.id === draft.sub_category_id);
    onOpenCreateModal('type', subCategory.id, subCategory.sub_category, (newType) => {
      if (newType?.id) {
        setDraft((prev) => ({ ...prev, type_id: newType.id, party_id: null }));
      }
    });
  };
  const handleCreateParty = () => {
    const type = allTypes.find((t) => t.id === draft.type_id);
    onOpenCreateModal('party', type.id, type.type, (newParty) => {
      if (newParty?.id) {
        setDraft((prev) => ({ ...prev, party_id: newParty.id }));
        setReuseParty(null);
      }
    });
  };
  // ── Display helpers ───────────────────────────────────────────────
  const formatDate = (ds) => (ds ? new Date(ds).toISOString().split('T')[0] : '');
  const formatAmount = (a) => (a == null ? '' : parseFloat(a).toFixed(2));
  const renderViewCell = (value) => <span className={VIEW}>{value || '-'}</span>;
  const renderCheckboxCell = (value) => (
    <span className="block text-center text-base font-bold text-[#4caf50]">
      {value ? '✓' : ''}
    </span>
  );
  // ── Row styling ───────────────────────────────────────────────────
  /*
   * Backgrounds are computed per-state rather than layered, which fixes a
   * specificity bug: the table's `tbody tr:nth-child(even)` rule (0,2,2)
   * used to override `.transaction-row.selected` / `.editing` (0,2,0),
   * making those highlights invisible on every even row.
   * Hover still wins over state — preserving the original resolved order.
   */
  const rowBg = isEditing
    ? 'bg-[#fff9e6]'
    : isSelected
      ? 'bg-[#e7f3ff]'
      : 'even:bg-gray-50';
  const rowRing = error
    ? 'shadow-[inset_0_0_0_2px_#f44336]'
    : isEditing
      ? 'shadow-[inset_0_0_0_2px_#f0c36d]'
      : '';
  /*
   * Replaces `.transaction-row.editing select, .dropdown-with-create select`.
   * NOTE: only covers selects inside THIS row — the modals that also use
   * DropdownWithCreate lose their select styling when TransactionRow.css
   * is deleted. See the migration notes.
   */
  const editingSelects = isEditing
    ? '[&_select]:w-full [&_select]:rounded [&_select]:border [&_select]:border-gray-300 ' +
      '[&_select]:bg-white [&_select]:px-2 [&_select]:py-1.5 [&_select]:text-left [&_select]:text-sm'
    : '';
  return (
    <>
      {conflict && (
        <RemapPartyPrompt
          partyName={conflict.oldPartyName}
          onRemapAll={handleRemapAll}
          onThisOnly={handleThisOnly}
          onCancel={handleCancelConflict}
        />
      )}
      {receiptModalMode === 'view' && (
        <ReceiptViewModal
          isOpen
          onClose={() => setReceiptModalMode(null)}
          receiptId={transaction.receipt_id}
          receiptFilename={transaction.receipt_filename}
          receiptVendor={transaction.receipt_vendor}
          receiptAmount={transaction.receipt_amount}
          receiptDate={transaction.receipt_date}
          transactionId={transaction.id}
          onReceiptUnlinked={(updated) => onReceiptChange?.(updated)}
        />
      )}
      {receiptModalMode === 'upload' && (
        <ReceiptUploadModal
          isOpen
          onClose={() => setReceiptModalMode(null)}
          transactionId={transaction.id}
          transaction={transaction}
          onReceiptLinked={(updated) => onReceiptChange?.(updated)}
        />
      )}
      {/* `group` enables the remap-button hover reveal */}
      <tr
        className={`group transition-colors duration-200 hover:bg-gray-200 ${rowBg} ${rowRing} ${editingSelects}`}
      >
        {/* Selection checkbox */}
        <td className={`${TD} w-10 text-center`}>
          <Checkbox checked={isSelected} onChange={onSelectionChange} disabled={isEditing} />
        </td>
        {/* Description (read-only) */}
        <td
          className={`${TD} w-[20%] min-w-[200px] ${TRUNC_EXPAND} leading-[1.4]`}
          title={transaction.description}
        >
          {transaction.description}
        </td>
        {/* Cleaned Description (editable) */}
        <td className={`${TD} w-[15%] min-w-[150px] ${TRUNC_EXPAND}`}>
          {isEditing ? (
            <input
              type="text"
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-left text-sm"
              value={draft.cleaned_description}
              onChange={(e) =>
                setDraft((prev) => ({ ...prev, cleaned_description: e.target.value }))
              }
              placeholder="Cleaned description"
            />
          ) : (
            renderViewCell(transaction.cleaned_description)
          )}
        </td>
        {/* Date (read-only) */}
        <td className={`${TD} w-[10%] whitespace-nowrap tabular-nums`}>
          {formatDate(transaction.transaction_date)}
        </td>
        {/* Amount (read-only) */}
        <td className={`${TD} w-[10%] text-right text-gray-800`}>
          {formatAmount(transaction.amount)}
        </td>
        {/* Is Credit */}
        <td className={`${TD} w-20 text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_credit}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_credit: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_credit)
          )}
        </td>
        {/* Account (read-only) */}
        <td className={`${TD} w-[10%] ${TRUNC}`} title={transaction.account_name || ''}>
          {transaction.account_name || '-'}
        </td>
        {/* Party — inner flex wrapper instead of `display:flex` on the <td>,
            so the table layout is preserved and truncation actually works */}
        <td className={`${TD} w-[10%]`} title={isEditing ? '' : transaction.party_name || ''}>
          {isEditing ? (
            <DropdownWithCreate
              value={draft.party_id}
              onChange={handlePartyChange}
              options={filteredParties}
              valueKey="id"
              labelKey="name"
              includeEmpty
              emptyLabel="-"
              placeholder="Select party"
              onCreateNew={draft.type_id ? handleCreateParty : null}
              createLabel="➕ Create New Party..."
            />
          ) : (
            <div className="flex items-center gap-[0.4rem]">
              <span className={`min-w-0 flex-1 truncate ${VIEW}`}>
                {transaction.party_name || '-'}
              </span>
              {transaction.party_id && onRemapParty && (
                <button
                  className="shrink-0 cursor-pointer rounded border border-transparent bg-none px-1 py-px text-[0.8rem] leading-none text-gray-500 opacity-0 transition-[opacity,color,border-color] duration-150 group-hover:opacity-100 hover:border-[#93c5fd] hover:bg-[#eff6ff] hover:text-[#2563eb]"
                  onClick={() => onRemapParty(transaction.party_id)}
                  title={`Remap party: ${transaction.party_name}`}
                  type="button"
                >
                  ✎
                </button>
              )}
            </div>
          )}
        </td>
        {/* Type */}
        <td className={`${TD} w-[10%] ${TRUNC}`} title={isEditing ? '' : transaction.type_name || ''}>
          {isEditing ? (
            <DropdownWithCreate
              value={draft.type_id}
              onChange={handleTypeChange}
              options={filteredTypes}
              valueKey="id"
              labelKey="type"
              includeEmpty
              emptyLabel="-"
              placeholder="Select type"
              onCreateNew={draft.sub_category_id ? handleCreateType : null}
              createLabel="➕ Create New Type..."
            />
          ) : (
            renderViewCell(transaction.type_name)
          )}
        </td>
        {/* Sub-Category */}
        <td
          className={`${TD} w-[10%] ${TRUNC}`}
          title={isEditing ? '' : transaction.sub_category_name || ''}
        >
          {isEditing ? (
            <DropdownWithCreate
              value={draft.sub_category_id}
              onChange={handleSubCategoryChange}
              options={filteredSubCategories}
              valueKey="id"
              labelKey="sub_category"
              includeEmpty
              emptyLabel="-"
              placeholder="Select sub-category"
              onCreateNew={draft.category_id ? handleCreateSubCategory : null}
              createLabel="➕ Create New Sub-Category..."
            />
          ) : (
            renderViewCell(transaction.sub_category_name)
          )}
        </td>
        {/* Category */}
        <td
          className={`${TD} w-[10%] ${TRUNC}`}
          title={isEditing ? '' : transaction.category_name || ''}
        >
          {isEditing ? (
            <DropdownWithCreate
              value={draft.category_id}
              onChange={handleCategoryChange}
              options={allCategories}
              valueKey="id"
              labelKey="category"
              includeEmpty
              emptyLabel="-"
              placeholder="Select category"
              onCreateNew={handleCreateCategory}
              createLabel="➕ Create New Category..."
            />
          ) : (
            renderViewCell(transaction.category_name)
          )}
        </td>
        {/* Is Kids */}
        <td className={`${TD} w-20 text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_kids}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_kids: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_kids)
          )}
        </td>
        {/* Is One-Off */}
        <td className={`${TD} w-20 text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_one_off}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_one_off: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_one_off)
          )}
        </td>
        {/* Receipt */}
        <td className={`${TD} text-center`}>
          <ReceiptIcon
            hasReceipt={!!transaction.receipt_id}
            onClick={handleReceiptIconClick}
          />
        </td>
        {/* Actions */}
        <td className={`${TD} w-[60px] text-center`}>
          {error && (
            <span className="mr-2 cursor-help text-[#f44336]" title="Save failed — see notification">
              ⚠
            </span>
          )}
          {isEditing ? (
            <div className="flex justify-center gap-1">
              <button
                onClick={saveChanges}
                disabled={isSaving}
                className={`${ACTION_BTN} bg-[#4caf50] hover:bg-[#388e3c]`}
                title="Save changes"
              >
                {isSaving ? '...' : '✓'}
              </button>
              <button
                onClick={cancelEditing}
                disabled={isSaving}
                className={`${ACTION_BTN} bg-[#f44336] hover:bg-[#d32f2f]`}
                title="Cancel"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className={`${ACTION_BTN} bg-[#2196f3] hover:bg-[#1976d2]`}
              title="Edit transaction"
            >
              ✎
            </button>
          )}
        </td>
      </tr>
    </>
  );
}