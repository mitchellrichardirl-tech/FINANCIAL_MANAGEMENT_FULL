import { useState, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import Checkbox from '@/components/Checkbox';
import RemapPartyPrompt from './RemapPartyPrompt';
import './TransactionRow.css';

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
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);

  // Pending conflict state.
  // Shape: {
  //   oldDraft,        ← full draft before the change, for "Cancel"
  //   oldPartyId,      ← party that was selected before the change
  //   oldPartyName,    ← its display name
  //   newDraftAfter,   ← what the draft should become if user proceeds
  // }
  const [conflict, setConflict] = useState(null);

  // If the user chose "this transaction only" we remember the old party name
  // and new type so we can find-or-create at save time.
  // Shape: { partyName, typeId } | null
  const [reuseParty, setReuseParty] = useState(null);

  // ── Edit lifecycle ──

  const startEditing = () => {
    setDraft({
      category_id:
        allCategories.find(
          (c) => c.category === transaction.category_name
        )?.id ?? null,
      sub_category_id:
        allSubCategories.find(
          (sc) => sc.sub_category === transaction.sub_category_name
        )?.id ?? null,
      type_id:
        allTypes.find((t) => t.type === transaction.type_name)?.id ?? null,
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

  // ── Helpers for building a new draft after a hierarchy change ──

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
      party_id: null,   // cleared — party belongs to old type
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

  // ── Generic helper: intercept a hierarchy change if a party is selected ──

  /**
   * @param {object} currentDraft
   * @param {object} newDraftAfter  - what draft should be if user proceeds
   * @param {function} applyImmediately - called with newDraftAfter if no conflict
   */
  const maybeShowConflict = (currentDraft, newDraftAfter, applyImmediately) => {
    if (!currentDraft.party_id) {
      // No party selected — no conflict, just apply
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

  // ── Change handlers ──

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

  const handlePartyChange = (partyId) => {
    // Selecting a party never causes a conflict — it syncs upward instead
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
    // Choosing a new party clears any pending reuseParty instruction
    setReuseParty(null);
  };

  // ── Conflict prompt handlers ──

  const handleRemapAll = () => {
    if (!conflict) return;
    const { oldPartyId, newDraftAfter } = conflict;
    setConflict(null);
    setReuseParty(null);
    // Apply the draft change so the UI updates
    setDraft(newDraftAfter);
    // Open the remap modal for the whole party — parent handles it
    onRemapParty(oldPartyId);
    // Exit edit mode; table will reload after remap
    cancelEditing();
  };

  const handleThisOnly = () => {
    if (!conflict) return;
    const { oldPartyName, newDraftAfter } = conflict;
    setConflict(null);
    // Remember we need to find-or-create at save time
    // The type will be whatever ends up in the final draft — but we capture
    // newDraftAfter.type_id as the starting point (the user may refine further)
    setReuseParty({ partyName: oldPartyName, typeId: newDraftAfter.type_id });
    setDraft(newDraftAfter);
  };

  const handleCancelConflict = () => {
    if (!conflict) return;
    // Restore draft to before the change
    setDraft(conflict.oldDraft);
    setConflict(null);
  };

  // ── Save ──

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
    } catch (err) {
      console.error('Failed to save:', err);
      setError('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  const saveChanges = async () => {
    if (!draft) return;

    // If the user chose "this transaction only" earlier, resolve the party now.
    // Use draft.type_id in case they further refined the type after dismissing
    // the prompt.
    if (reuseParty) {
      const targetTypeId = draft.type_id ?? reuseParty.typeId;
      if (!targetTypeId) {
        // Nowhere to put the party — just save without one
        await persistSave(null);
        return;
      }
      setIsSaving(true);
      try {
        const targetPartyId = await onFindOrCreateParty(
          reuseParty.partyName,
          targetTypeId
        );
        await persistSave(targetPartyId);
      } catch (err) {
        console.error('Failed to find/create party:', err);
        setError('Failed to reassign party');
        setIsSaving(false);
      }
      return;
    }

    await persistSave(draft.party_id);
  };

  // ── Filtered options ──

  const filteredSubCategories = useMemo(() => {
    if (!isEditing || !draft?.category_id) return allSubCategories;
    return allSubCategories.filter(
      (sc) => sc.category_id === draft.category_id
    );
  }, [isEditing, draft?.category_id, allSubCategories]);

  const filteredTypes = useMemo(() => {
    if (!isEditing) return allTypes;
    if (draft?.sub_category_id) {
      return allTypes.filter(
        (t) => t.sub_category_id === draft.sub_category_id
      );
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

  // ── Create handlers ──

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
    const category = allCategories.find((c) => c.id === draft?.category_id);
    if (!category) { setError('Please select a category first'); return; }
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
    const subCategory = allSubCategories.find(
      (sc) => sc.id === draft?.sub_category_id
    );
    if (!subCategory) { setError('Please select a sub-category first'); return; }
    onOpenCreateModal('type', subCategory.id, subCategory.sub_category, (newType) => {
      if (newType?.id) {
        setDraft((prev) => ({ ...prev, type_id: newType.id, party_id: null }));
      }
    });
  };

  const handleCreateParty = () => {
    const type = allTypes.find((t) => t.id === draft?.type_id);
    if (!type) { setError('Please select a type first'); return; }
    onOpenCreateModal('party', type.id, type.type, (newParty) => {
      if (newParty?.id) {
        setDraft((prev) => ({ ...prev, party_id: newParty.id }));
        setReuseParty(null); // explicit new party chosen — clear reuse intent
      }
    });
  };

  // ── Display helpers ──

  const formatDate = (ds) =>
    ds ? new Date(ds).toISOString().split('T')[0] : '';

  const formatAmount = (a) =>
    a == null ? '' : parseFloat(a).toFixed(2);

  const renderViewCell = (value) => (
    <span className="view-value">{value || '-'}</span>
  );

  const renderCheckboxCell = (value) => (
    <span className={`check-indicator ${value ? 'checked' : ''}`}>
      {value ? '✓' : ''}
    </span>
  );

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

      <tr
        className={`transaction-row ${isEditing ? 'editing' : ''} ${
          isSelected ? 'selected' : ''
        } ${error ? 'has-error' : ''}`}
      >
        {/* Selection checkbox */}
        <td className="select-cell">
          <Checkbox
            checked={isSelected}
            onChange={onSelectionChange}
            disabled={isEditing}
          />
        </td>

        {/* Description */}
        <td className="description-cell" title={transaction.description}>
          {transaction.description}
        </td>

        {/* Cleaned Description */}
        <td className="cleaned-description-cell">
          {isEditing ? (
            <input
              type="text"
              className="edit-input"
              value={draft.cleaned_description}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  cleaned_description: e.target.value,
                }))
              }
              placeholder="Cleaned description"
            />
          ) : (
            renderViewCell(transaction.cleaned_description)
          )}
        </td>

        {/* Date */}
        <td className="date-cell">{formatDate(transaction.transaction_date)}</td>

        {/* Amount */}
        <td className="amount-cell">{formatAmount(transaction.amount)}</td>

        {/* Is Credit */}
        <td className="lodgment-cell">
          {isEditing ? (
            <Checkbox
              checked={draft.is_credit}
              onChange={(value) =>
                setDraft((prev) => ({ ...prev, is_credit: value }))
              }
            />
          ) : (
            renderCheckboxCell(transaction.is_credit)
          )}
        </td>

        {/* Account */}
        <td className="account-cell" title={transaction.account_name || ''}>
          {transaction.account_name || '-'}
        </td>

        {/* Party */}
        <td
          className="party-cell"
          title={isEditing ? '' : transaction.party_name || ''}
        >
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
                  className="remap-party-btn"
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
        <td
          className="type-cell"
          title={isEditing ? '' : transaction.type_name || ''}
        >
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
          className="sub-category-cell"
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
          className="category-cell"
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
        <td className="kids-cell">
          {isEditing ? (
            <Checkbox
              checked={draft.is_kids}
              onChange={(value) =>
                setDraft((prev) => ({ ...prev, is_kids: value }))
              }
            />
          ) : (
            renderCheckboxCell(transaction.is_kids)
          )}
        </td>

        {/* Is One-Off */}
        <td className="one-off-cell">
          {isEditing ? (
            <Checkbox
              checked={draft.is_one_off}
              onChange={(value) =>
                setDraft((prev) => ({ ...prev, is_one_off: value }))
              }
            />
          ) : (
            renderCheckboxCell(transaction.is_one_off)
          )}
        </td>

        {/* Actions */}
        <td className="actions-cell">
          {error && (
            <span className="row-error" title={error}>
              ⚠
            </span>
          )}
          {isEditing ? (
            <div className="edit-actions">
              <button
                onClick={saveChanges}
                disabled={isSaving}
                className="btn-save"
                title="Save changes"
              >
                {isSaving ? '...' : '✓'}
              </button>
              <button
                onClick={cancelEditing}
                disabled={isSaving}
                className="btn-cancel"
                title="Cancel"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={startEditing}
              className="btn-edit"
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