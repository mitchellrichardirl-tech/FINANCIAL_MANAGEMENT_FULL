import { useState, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import Checkbox from '@/components/Checkbox';
import RemapPartyPrompt from './RemapPartyPrompt';
import { createLogger } from '@/lib/logger';
import { useToast } from '@/components/ToastContext';

const logger = createLogger('TransactionRow');

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
  const [error, setError] = useState(null);
  const [draft, setDraft] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [reuseParty, setReuseParty] = useState(null);

  const startEditing = () => {
    setDraft({
      category_id:
        allCategories.find((c) => c.category === transaction.category_name)?.id ?? null,
      sub_category_id:
        allSubCategories.find((sc) => sc.sub_category === transaction.sub_category_name)?.id ?? null,
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

  const formatDate = (ds) => (ds ? new Date(ds).toISOString().split('T')[0] : '');
  const formatAmount = (a) => (a == null ? '' : parseFloat(a).toFixed(2));

  const renderViewCell = (value) => (
    <span className="block py-1 px-0">{value || '-'}</span>
  );
  const renderCheckboxCell = (value) => (
    <span className="block text-center text-[#4caf50] font-bold text-base">
      {value ? '✓' : ''}
    </span>
  );

  const baseCellCls = 'p-2 border-b border-[#e9ecef] text-left align-middle text-sm';
  const truncCellCls = `${baseCellCls} max-w-0 overflow-hidden text-ellipsis whitespace-nowrap`;
  const editInputCls =
    'w-full py-1.5 px-2 border border-[#ddd] rounded text-sm font-inherit text-left';

  let rowCls = 'transition-colors duration-200';
  if (isEditing) rowCls += ' bg-[#fff9e6] shadow-[inset_0_0_0_2px_#f0c36d]';
  else if (isSelected) rowCls += ' bg-[#e7f3ff]';
  else rowCls += ' even:bg-[#f8f9fa] hover:bg-[#e9ecef]';
  if (error) rowCls += ' shadow-[inset_0_0_0_2px_#f44336]';

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

      <tr className={rowCls}>
        <td className={`${baseCellCls} w-10 text-center`}>
          <Checkbox checked={isSelected} onChange={onSelectionChange} disabled={isEditing} />
        </td>
        <td
          className={`${truncCellCls} w-[20%] min-w-[200px] hover:overflow-visible hover:whitespace-normal hover:break-words`}
          title={transaction.description}
        >
          {transaction.description}
        </td>
        <td className={`${truncCellCls} w-[15%] min-w-[150px] hover:overflow-visible hover:whitespace-normal hover:break-words`}>
          {isEditing ? (
            <input
              type="text"
              className={editInputCls}
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
        <td className={`${baseCellCls} w-[10%] whitespace-nowrap tabular-nums`}>
          {formatDate(transaction.transaction_date)}
        </td>
        <td className={`${baseCellCls} w-[10%] !text-right text-[#212529]`}>
          {formatAmount(transaction.amount)}
        </td>
        <td className={`${baseCellCls} w-20 !text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_credit}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_credit: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_credit)
          )}
        </td>
        <td className={`${truncCellCls} w-[10%]`} title={transaction.account_name || ''}>
          {transaction.account_name || '-'}
        </td>
        <td className={`${truncCellCls} w-[10%] !flex items-center gap-[0.4rem] group`} title={isEditing ? '' : transaction.party_name || ''}>
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
                  type="button"
                  onClick={() => onRemapParty(transaction.party_id)}
                  title={`Remap party: ${transaction.party_name}`}
                  className="shrink-0 bg-none border border-transparent rounded text-[#6b7280] text-[0.8rem] leading-none py-px px-1 cursor-pointer opacity-0 group-hover:opacity-100 hover:text-[#2563eb] hover:border-[#93c5fd] hover:bg-[#eff6ff]"
                >
                  ✎
                </button>
              )}
            </>
          )}
        </td>
        <td className={`${truncCellCls} w-[10%]`} title={isEditing ? '' : transaction.type_name || ''}>
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
        <td className={`${truncCellCls} w-[10%]`} title={isEditing ? '' : transaction.sub_category_name || ''}>
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
        <td className={`${truncCellCls} w-[10%]`} title={isEditing ? '' : transaction.category_name || ''}>
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
        <td className={`${baseCellCls} w-20 !text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_kids}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_kids: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_kids)
          )}
        </td>
        <td className={`${baseCellCls} w-20 !text-center`}>
          {isEditing ? (
            <Checkbox
              checked={draft.is_one_off}
              onChange={(value) => setDraft((prev) => ({ ...prev, is_one_off: value }))}
            />
          ) : (
            renderCheckboxCell(transaction.is_one_off)
          )}
        </td>
        <td className={`${baseCellCls} w-[60px] !text-center`}>
          {error && (
            <span className="text-[#f44336] mr-2 cursor-help" title="Save failed — see notification">
              ⚠
            </span>
          )}
          {isEditing ? (
            <div className="flex gap-1 justify-center">
              <button
                type="button"
                onClick={saveChanges}
                disabled={isSaving}
                title="Save changes"
                className="py-1.5 px-2.5 border-0 rounded cursor-pointer text-sm bg-[#4caf50] text-white hover:enabled:bg-[#388e3c] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? '...' : '✓'}
              </button>
              <button
                type="button"
                onClick={cancelEditing}
                disabled={isSaving}
                title="Cancel"
                className="py-1.5 px-2.5 border-0 rounded cursor-pointer text-sm bg-[#f44336] text-white hover:enabled:bg-[#d32f2f] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={startEditing}
              title="Edit transaction"
              className="py-1.5 px-2.5 border-0 rounded cursor-pointer text-sm bg-[#2196f3] text-white hover:bg-[#1976d2]"
            >
              ✎
            </button>
          )}
        </td>
      </tr>
    </>
  );
}
