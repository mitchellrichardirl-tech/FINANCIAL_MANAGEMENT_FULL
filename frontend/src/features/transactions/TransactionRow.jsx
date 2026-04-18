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
import { createLogger } from '@/lib/logger';
import { useToast } from '@/stores/toastStore';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('TransactionRow');

/**
 * Editable transaction table row.
 *
 * @component
 * @param {Object} props
 *
 * @param {Object} props.transaction
 *        The transaction record. Expected to have `id`, denormalized
 *        `*_name` strings for display, and `*_id` foreign keys.
 * @param {Array<Object>} props.accounts - All accounts (unused in edit but kept for parity).
 * @param {Array<Object>} props.allCategories
 * @param {Array<Object>} props.allSubCategories
 * @param {Array<Object>} props.allTypes
 * @param {Array<Object>} props.allParties
 *
 * @param {(txnId: number, updates: Object) => Promise<void>} props.onUpdate
 *        Persist edits. Should throw on failure (the row catches it and
 *        marks itself in error).
 * @param {(type: string, parentId: ?number, parentName: string, onSuccess: Function) => void} props.onOpenCreateModal
 *        Open the table's shared create-taxonomy modal.
 *
 * @param {boolean} props.isSelected - Row checkbox state.
 * @param {(checked: boolean) => void} props.onSelectionChange
 *
 * @param {(partyId: number) => void} props.onRemapParty
 *        Open the global remap modal for a party.
 * @param {(partyName: string, typeId: number) => Promise<number>} props.onFindOrCreateParty
 *        Find or create a party under a type; returns the new/found id.
 *
 * @returns {JSX.Element}
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
}) {
  const { addToast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  /** `true` when the last save attempt failed. Renders a ⚠ indicator. */
  const [error, setError] = useState(null);
  /**
   * Working copy of editable fields while in edit mode.
   * Committed to the server only on explicit Save.
   */
  const [draft, setDraft] = useState(null);

  // ── Conflict state ────────────────────────────────────────────────
  /**
   * When the user changes a parent (category/subcat/type) while a party
   * is selected, we pause and ask what to do.
   *
   * @typedef {Object} Conflict
   * @property {Object} oldDraft      - Draft snapshot before the change.
   * @property {number} oldPartyId    - Party that was selected.
   * @property {string} oldPartyName  - Display name.
   * @property {Object} newDraftAfter - Draft that would result if user proceeds.
   */
  const [conflict, setConflict] = useState(null);

  /**
   * When the user chooses "this transaction only" we defer party
   * creation until save time. Store the name + target type here.
   * @type {?{partyName: string, typeId: number}}
   */
  const [reuseParty, setReuseParty] = useState(null);

  // ── Edit lifecycle ────────────────────────────────────────────────

  /** Enter edit mode: snapshot current values into `draft`. */
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

  /** Exit edit mode, discarding unsaved changes. */
  const cancelEditing = () => {
    setDraft(null);
    setConflict(null);
    setReuseParty(null);
    setError(null);
    setIsEditing(false);
  };

  // ── Draft builders for hierarchy changes ──────────────────────────

  /**
   * Produce a new draft after the user selects a different type.
   * Auto-fills category + subcat; clears party (belongs to old type).
   */
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

  /** New draft after sub-category change; clears type & party. */
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

  /** New draft after category change; clears subcat/type/party. */
  const buildDraftAfterCategoryChange = (currentDraft, newCategoryId) => ({
    ...currentDraft,
    category_id: newCategoryId,
    sub_category_id: null,
    type_id: null,
    party_id: null,
  });

  // ── Conflict detection ────────────────────────────────────────────

  /**
   * If a party is already selected and the user changes a parent level,
   * show the conflict prompt instead of applying the change immediately.
   */
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

  // ── Change handlers (category → subcat → type → party) ───────────

  const handleCategoryChange = (categoryId) => {
    const id = categoryId ? parseInt(categoryId) : null;
    const newDraftAfter = buildDraftAfterCategoryChange(draft, id);
    maybeShowConflict(draft, newDraftAfter, setDraft);
  };

  const handleSubCategoryChange = (subCategoryId) => {
    const id = subCategoryId ? parseInt(subCategoryId) : null;
    const newDraftAfter = buildDraftAfterSubCategoryChange(draft, id);
    maybeShowConflict(draft, newDraftAfter, setDraft);
  };

  const handleTypeChange = (typeId) => {
    const id = typeId ? parseInt(typeId) : null;
    const newDraftAfter = buildDraftAfterTypeChange(draft, id);
    maybeShowConflict(draft, newDraftAfter, setDraft);
  };

  /**
   * Selecting a party syncs **upward** (fills type/subcat/cat) — no
   * conflict, because the party drives the hierarchy.
   */
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

  // ── Conflict prompt handlers ──────────────────────────────────────

  /** User chose "Remap all transactions" — delegate to parent modal. */
  const handleRemapAll = () => {
    if (!conflict) return;
    const { oldPartyId, newDraftAfter } = conflict;
    setConflict(null);
    setReuseParty(null);
    setDraft(newDraftAfter);
    onRemapParty(oldPartyId);
    cancelEditing();
  };

  /** User chose "This transaction only" — defer party find/create to save. */
  const handleThisOnly = () => {
    if (!conflict) return;
    const { oldPartyName, newDraftAfter } = conflict;
    setConflict(null);
    setReuseParty({ partyName: oldPartyName, typeId: newDraftAfter.type_id });
    setDraft(newDraftAfter);
  };

  /** User cancelled the conflict prompt — restore draft. */
  const handleCancelConflict = () => {
    if (!conflict) return;
    setDraft(conflict.oldDraft);
    setConflict(null);
  };

  // ── Persist ───────────────────────────────────────────────────────

  /**
   * Actually call `onUpdate` with the final payload.
   * @param {?number} partyId - Resolved party id (may differ from `draft.party_id`).
   */
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
      // Parent already toasted the API error.
      setError(true);
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Public save entry point. Resolves deferred party creation if
   * `reuseParty` is set, then calls {@link persistSave}.
   */
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

  // ── Create handlers (open modal, apply id on success) ─────────────

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

  /** Format an ISO date string as `YYYY-MM-DD`. */
  const formatDate = (ds) => (ds ? new Date(ds).toISOString().split('T')[0] : '');

  /** Format a numeric amount to two decimals. */
  const formatAmount = (a) => (a == null ? '' : parseFloat(a).toFixed(2));

  const renderViewCell = (value) => <span className="block py-[4px]">{value || '-'}</span>;

  const renderCheckboxCell = (value) => (
    <span className={`block text-center font-bold text-[16px] ${value ? 'text-[#4caf50]' : ''}`}>{value ? '✓' : ''}</span>
  );

  // Row class computation
  const rowClasses = [
    'transition-colors duration-200',
    isEditing ? 'bg-[#fff9e6] shadow-[inset_0_0_0_2px_#f0c36d]' : '',
    isSelected && !isEditing ? 'bg-[#e7f3ff]' : '',
    error ? 'shadow-[inset_0_0_0_2px_#f44336]' : '',
  ].filter(Boolean).join(' ');

  // Common cell classes for truncation
  const truncCell = 'txn-truncate-cell';

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

      <tr className={rowClasses}>
        {/* Selection checkbox */}
        <td className="w-[40px] text-center! p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">
          <Checkbox checked={isSelected} onChange={onSelectionChange} disabled={isEditing} />
        </td>

        {/* Description (read-only) */}
        <td className={`${truncCell} txn-desc-cell w-[20%] min-w-[200px] p-[8px] border-b border-[#e9ecef] align-middle text-[14px] whitespace-normal leading-[1.4]`} title={transaction.description}>
          {transaction.description}
        </td>

        {/* Cleaned Description (editable) */}
        <td className={`${truncCell} txn-cleaned-desc-cell w-[15%] min-w-[150px] p-[8px] border-b border-[#e9ecef] align-middle text-[14px]`}>
          {isEditing ? (
            <input
              type="text"
              className="w-full py-[6px] px-[8px] border border-border rounded-[4px] text-[14px] font-[inherit] text-left"
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
        <td className="w-[10%] whitespace-nowrap tabular-nums p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">{formatDate(transaction.transaction_date)}</td>

        {/* Amount (read-only) */}
        <td className="w-[10%] text-right! p-[8px] border-b border-[#e9ecef] align-middle text-[14px] text-[#212529]">{formatAmount(transaction.amount)}</td>

        {/* Is Credit */}
        <td className="w-[80px] text-center! p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">
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
        <td className={`${truncCell} w-[10%] p-[8px] border-b border-[#e9ecef] align-middle text-[14px]`} title={transaction.account_name || ''}>
          {transaction.account_name || '-'}
        </td>

        {/* Party */}
        <td className={`txn-party-cell w-[10%] p-[8px] border-b border-[#e9ecef] align-middle text-[14px] flex items-center gap-[0.4rem] max-w-0 overflow-hidden text-ellipsis whitespace-nowrap`} title={isEditing ? '' : transaction.party_name || ''}>
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
            <>
              {renderViewCell(transaction.party_name)}
              {transaction.party_id && onRemapParty && (
                <button
                  className="txn-remap-party-btn"
                  onClick={() => onRemapParty(transaction.party_id)}
                  title={`Remap party: ${transaction.party_name}`}
                  type="button"
                >
                  ✎
                </button>
              )}
            </>
          )}
        </td>

        {/* Type */}
        <td className={`${truncCell} w-[10%] p-[8px] border-b border-[#e9ecef] align-middle text-[14px]`} title={isEditing ? '' : transaction.type_name || ''}>
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
        <td className={`${truncCell} w-[10%] p-[8px] border-b border-[#e9ecef] align-middle text-[14px]`} title={isEditing ? '' : transaction.sub_category_name || ''}>
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
        <td className={`${truncCell} w-[10%] p-[8px] border-b border-[#e9ecef] align-middle text-[14px]`} title={isEditing ? '' : transaction.category_name || ''}>
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
        <td className="w-[80px] text-center! p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">
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
        <td className="w-[80px] text-center! p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">
          {isEditing ? (
            <Checkbox
              checked={draft.is_one_off}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_one_off: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_one_off)
          )}
        </td>

        {/* Actions */}
        <td className="w-[60px] text-center! p-[8px] border-b border-[#e9ecef] align-middle text-[14px]">
          {error && (
            <span className="text-[#f44336] mr-[8px] cursor-help" title="Save failed — see notification">
              ⚠
            </span>
          )}
          {isEditing ? (
            <div className="flex gap-[4px] justify-center">
              <button
                onClick={saveChanges}
                disabled={isSaving}
                className="py-[6px] px-[10px] border-none rounded-[4px] cursor-pointer text-[14px] transition-[background-color,opacity] duration-200 bg-[#4caf50] text-white hover:bg-[#388e3c] disabled:opacity-50 disabled:cursor-not-allowed"
                title="Save changes"
              >
                {isSaving ? '...' : '✓'}
              </button>
              <button
                onClick={cancelEditing}
                disabled={isSaving}
                className="py-[6px] px-[10px] border-none rounded-[4px] cursor-pointer text-[14px] transition-[background-color,opacity] duration-200 bg-[#f44336] text-white hover:bg-[#d32f2f] disabled:opacity-50 disabled:cursor-not-allowed"
                title="Cancel"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className="py-[6px] px-[10px] border-none rounded-[4px] cursor-pointer text-[14px] transition-[background-color,opacity] duration-200 bg-[#2196f3] text-white hover:bg-[#1976d2]"
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
