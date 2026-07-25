/**
 * @file BulkEditModal.jsx
 * Modal for applying the same category/party/flags to a batch of
 * selected transactions.
 *
 * The user can drill down through the taxonomy (category → subcat →
 * type → party) with cascading dropdowns. Only `party_id`, `is_kids`,
 * and `is_one_off` are actually written to the transactions — higher
 * taxonomy levels are used purely to filter the party list.
 */

import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import Checkbox from '@/components/Checkbox';
import CreateCategoryModal from './CreateCategoryModal';
//    ⚠️ See migration notes — the generic modal classes in that file may be
//    shared with other modals. Grep before deleting.
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('BulkEditModal');
/* ── Reused class strings ──────────────────────────────────────────── */
const FORM_FIELD = 'flex flex-col gap-2';
const FIELD_LABEL = 'text-[0.9em] font-medium';
const SECTION_H3 = 'text-[1.1em] font-bold text-[#646cff]';
/**
 * Footer buttons. `.cancel-button`/`.save-button` previously declared only
 * padding + border-color, inheriting the rest from Vite's global `button`
 * rule — which no longer exists. Both needed real styling.
 */
const BTN_BASE =
  'cursor-pointer rounded-lg px-[1.5em] py-[0.6em] transition-colors ' +
  'disabled:cursor-not-allowed disabled:opacity-50';
const BTN_CANCEL = `${BTN_BASE} border border-[#666] bg-transparent hover:border-[#888]`;
const BTN_SAVE = `${BTN_BASE} border border-transparent bg-[#646cff] text-white hover:bg-[#535bf2]`;
const CLEAR_BTN =
  'cursor-pointer rounded border-none bg-[#e0e0e0] px-2 py-1 text-xs ' +
  'hover:bg-[#d0d0d0] disabled:cursor-not-allowed disabled:opacity-50';
/**
 * Modal dialog for bulk-editing selected transactions.
 * (full docblock unchanged)
 */
export default function BulkEditModal({
  isOpen,
  onClose,
  onSave,
  transactionCount,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  /** Local draft of selected values. */
  const [updates, setUpdates] = useState({
    category_id: null,
    sub_category_id: null,
    type_id: null,
    party_id: null,
    party_name: '',
    is_kids: null,
    is_one_off: null,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null,
  });
  // ── Derived option lists (sorted & filtered) ──────────────────────
  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );
  const filteredSubCategories = useMemo(() => {
    let filtered = [...subCategories];
    if (updates.category_id) {
      filtered = filtered.filter((sc) => sc.category_id === updates.category_id);
    }
    return filtered.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, updates.category_id]);
  const filteredTypes = useMemo(() => {
    let filtered = [...types];
    if (updates.sub_category_id) {
      filtered = filtered.filter((t) => t.sub_category_id === updates.sub_category_id);
    } else if (updates.category_id) {
      const subCatIds = subCategories
        .filter((sc) => sc.category_id === updates.category_id)
        .map((sc) => sc.id);
      filtered = filtered.filter((t) => subCatIds.includes(t.sub_category_id));
    }
    return filtered.sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategories, updates.sub_category_id, updates.category_id]);
  const filteredParties = useMemo(() => {
    let filtered = [...parties];
    if (updates.type_id) {
      filtered = filtered.filter((p) => p.type_id === updates.type_id);
    } else if (updates.sub_category_id) {
      const typeIds = types
        .filter((t) => t.sub_category_id === updates.sub_category_id)
        .map((t) => t.id);
      filtered = filtered.filter((p) => typeIds.includes(p.type_id));
    } else if (updates.category_id) {
      const subCatIds = subCategories
        .filter((sc) => sc.category_id === updates.category_id)
        .map((sc) => sc.id);
      const typeIds = types
        .filter((t) => subCatIds.includes(t.sub_category_id))
        .map((t) => t.id);
      filtered = filtered.filter((p) => typeIds.includes(p.type_id));
    }
    return filtered.sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, types, subCategories, updates.type_id, updates.sub_category_id, updates.category_id]);
  // ── Reset state each time the modal opens ─────────────────────────
  useEffect(() => {
    if (isOpen) {
      setUpdates({
        category_id: null,
        sub_category_id: null,
        type_id: null,
        party_id: null,
        party_name: '',
        is_kids: null,
        is_one_off: null,
      });
      setValidationError(null);
      setIsSaving(false);
    }
  }, [isOpen]);
  // ── Taxonomy change handlers ──────────────────────────────────────
  const handleCategoryChange = (categoryId) => {
    setUpdates((prev) => ({
      ...prev,
      category_id: categoryId ? parseInt(categoryId) : null,
      sub_category_id: null,
      type_id: null,
      party_id: null,
      party_name: '',
    }));
  };
  const handleSubCategoryChange = (subCategoryId) => {
    if (subCategoryId) {
      const subCategory = subCategories.find((sc) => sc.id === parseInt(subCategoryId));
      if (subCategory) {
        setUpdates((prev) => ({
          ...prev,
          category_id: subCategory.category_id,
          sub_category_id: parseInt(subCategoryId),
          type_id: null,
          party_id: null,
          party_name: '',
        }));
      }
    } else {
      setUpdates((prev) => ({
        ...prev,
        sub_category_id: null,
        type_id: null,
        party_id: null,
        party_name: '',
      }));
    }
  };
  const handleTypeChange = (typeId) => {
    if (typeId) {
      const type = types.find((t) => t.id === parseInt(typeId));
      if (type) {
        const subCategory = subCategories.find((sc) => sc.id === type.sub_category_id);
        setUpdates((prev) => ({
          ...prev,
          category_id: subCategory ? subCategory.category_id : prev.category_id,
          sub_category_id: type.sub_category_id,
          type_id: parseInt(typeId),
          party_id: null,
          party_name: '',
        }));
      }
    } else {
      setUpdates((prev) => ({ ...prev, type_id: null, party_id: null, party_name: '' }));
    }
  };
  const handlePartyChange = (partyId) => {
    if (partyId) {
      const party = parties.find((p) => p.id === parseInt(partyId));
      if (party) {
        const type = types.find((t) => t.id === party.type_id);
        const subCategory = type ? subCategories.find((sc) => sc.id === type.sub_category_id) : null;
        setUpdates((prev) => ({
          ...prev,
          category_id: subCategory ? subCategory.category_id : prev.category_id,
          sub_category_id: type ? type.sub_category_id : prev.sub_category_id,
          type_id: party.type_id,
          party_id: parseInt(partyId),
          party_name: party.name,
        }));
      }
    } else {
      setUpdates((prev) => ({ ...prev, party_id: null, party_name: '' }));
    }
  };
  const handleCheckboxChange = (field, value) => {
    setUpdates((prev) => ({ ...prev, [field]: value }));
  };
  // ── Create-modal launchers ────────────────────────────────────────
  const handleCreateCategory = () => {
    setCreateModalState({ isOpen: true, type: 'category', parentName: '', parentId: null });
  };
  const handleCreateSubCategory = () => {
    const category = categories.find((c) => c.id === updates.category_id);
    setCreateModalState({
      isOpen: true,
      type: 'sub_category',
      parentName: category.category,
      parentId: category.id,
    });
  };
  const handleCreateType = () => {
    const subCategory = subCategories.find((sc) => sc.id === updates.sub_category_id);
    setCreateModalState({
      isOpen: true,
      type: 'type',
      parentName: subCategory.sub_category,
      parentId: subCategory.id,
    });
  };
  const handleCreateParty = () => {
    const type = types.find((t) => t.id === updates.type_id);
    setCreateModalState({
      isOpen: true,
      type: 'party',
      parentName: type.type,
      parentId: type.id,
    });
  };
  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
    try {
      let newItem;
      switch (type) {
        case 'category':
          newItem = await onCategoryCreated(name, description);
          if (newItem?.id) {
            setUpdates((prev) => ({
              ...prev,
              category_id: newItem.id,
              sub_category_id: null,
              type_id: null,
              party_id: null,
              party_name: '',
            }));
          }
          break;
        case 'sub_category':
          newItem = await onSubCategoryCreated(name, parentId, description);
          if (newItem?.id) {
            setUpdates((prev) => ({
              ...prev,
              sub_category_id: newItem.id,
              type_id: null,
              party_id: null,
              party_name: '',
            }));
          }
          break;
        case 'type':
          newItem = await onTypeCreated(name, parentId, description);
          if (newItem?.id) {
            setUpdates((prev) => ({
              ...prev,
              type_id: newItem.id,
              party_id: null,
              party_name: '',
            }));
          }
          break;
        case 'party':
          newItem = await onPartyCreated(name, parentId, description);
          if (newItem?.id) {
            setUpdates((prev) => ({
              ...prev,
              party_id: newItem.id,
              party_name: newItem.name || name,
            }));
          }
          break;
      }
      setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
      return newItem;
    } catch (err) {
      logger.error('Error creating item:', err);
      throw err;
    }
  };
  // ── Save ──────────────────────────────────────────────────────────
  const handleSave = async () => {
    logger.debug('BulkEditModal: handleSave called');
    setValidationError(null);
    setIsSaving(true);
    try {
      const finalUpdates = {};
      if (updates.party_id) finalUpdates.party_id = updates.party_id;
      if (updates.is_kids !== null) finalUpdates.is_kids = updates.is_kids;
      if (updates.is_one_off !== null) finalUpdates.is_one_off = updates.is_one_off;
      logger.debug('BulkEditModal: Prepared updates:', finalUpdates);
      if (Object.keys(finalUpdates).length === 0) {
        setValidationError('No changes to save');
        setIsSaving(false);
        return;
      }
      logger.debug('BulkEditModal: Calling onSave...');
      await onSave(finalUpdates);
      logger.debug('BulkEditModal: onSave completed successfully');
    } catch (err) {
      logger.error('BulkEditModal: Save failed:', err);
      setIsSaving(false);
    }
  };
  // ── Close / cancel ────────────────────────────────────────────────
  const resetAndClose = () => {
    setUpdates({
      category_id: null,
      sub_category_id: null,
      type_id: null,
      party_id: null,
      party_name: '',
      is_kids: null,
      is_one_off: null,
    });
    setValidationError(null);
    setIsSaving(false);
    onClose();
  };
  const handleCancel = () => {
    if (isSaving) return;
    resetAndClose();
  };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSaving) {
      resetAndClose();
    }
  };
  const handleCloseCreateModal = () => {
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
  };
  if (!isOpen) return null;
  const canSave =
    !isSaving && (updates.party_id || updates.is_kids !== null || updates.is_one_off !== null);
  return (
    <>
      <div
        className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70"
        onClick={handleBackdropClick}
      >
        <div
          className="max-h-[90vh] w-[90%] max-w-[600px] overflow-y-auto rounded-lg bg-white p-8 shadow-[0_4px_6px_rgba(0,0,0,0.3)]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-4 flex items-center justify-between border-b border-gray-200 pb-4">
            <h2 className="text-2xl font-bold">
              Bulk Edit {transactionCount} Transactions
            </h2>
            <button
              className="cursor-pointer text-2xl leading-none text-gray-500 hover:text-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleCancel}
              disabled={isSaving}
              aria-label="Close modal"
            >
              ×
            </button>
          </div>
          {validationError && (
            <div className="mb-4 flex items-center justify-between rounded border border-danger-border bg-danger-bg px-4 py-3 text-danger-text">
              {validationError}
              <button
                onClick={() => setValidationError(null)}
                aria-label="Dismiss error"
                className="ml-3 cursor-pointer text-lg leading-none"
              >
                ×
              </button>
            </div>
          )}
          <div className="flex flex-col gap-8">
            <div className="flex flex-col gap-4">
              <h3 className={SECTION_H3}>Category Hierarchy</h3>
              <p className="text-[0.85em] italic text-[#888]">
                Select at any level - parent levels will be set automatically. Lower levels will be
                cleared when you change a higher level.
              </p>
              <div className={FORM_FIELD}>
                <label className={FIELD_LABEL}>Category</label>
                <DropdownWithCreate
                  value={updates.category_id}
                  onChange={handleCategoryChange}
                  options={sortedCategories}
                  valueKey="id"
                  labelKey="category"
                  includeEmpty
                  emptyLabel="-- No Change --"
                  onCreateNew={handleCreateCategory}
                  createLabel="➕ Create New Category..."
                  disabled={isSaving}
                />
              </div>
              <div className={FORM_FIELD}>
                <label className={FIELD_LABEL}>Sub-Category</label>
                <DropdownWithCreate
                  value={updates.sub_category_id}
                  onChange={handleSubCategoryChange}
                  options={filteredSubCategories}
                  valueKey="id"
                  labelKey="sub_category"
                  includeEmpty
                  emptyLabel="-- No Change --"
                  onCreateNew={updates.category_id ? handleCreateSubCategory : null}
                  createLabel="➕ Create New Sub-Category..."
                  disabled={isSaving}
                />
              </div>
              <div className={FORM_FIELD}>
                <label className={FIELD_LABEL}>Type</label>
                <DropdownWithCreate
                  value={updates.type_id}
                  onChange={handleTypeChange}
                  options={filteredTypes}
                  valueKey="id"
                  labelKey="type"
                  includeEmpty
                  emptyLabel="-- No Change --"
                  onCreateNew={updates.sub_category_id ? handleCreateType : null}
                  createLabel="➕ Create New Type..."
                  disabled={isSaving}
                />
              </div>
              <div className={FORM_FIELD}>
                <label className={FIELD_LABEL}>Party</label>
                <DropdownWithCreate
                  value={updates.party_id}
                  onChange={handlePartyChange}
                  options={filteredParties}
                  valueKey="id"
                  labelKey="name"
                  includeEmpty
                  emptyLabel="-- No Change --"
                  onCreateNew={updates.type_id ? handleCreateParty : null}
                  createLabel="➕ Create New Party..."
                  disabled={isSaving}
                />
              </div>
            </div>
            <div className="flex flex-col gap-4">
              <h3 className={SECTION_H3}>Flags</h3>
              {/* flex-row: `.checkbox-field` set align-items/gap but never
                  reset flex-direction, so these stacked vertically. */}
              <div className="flex flex-row items-center gap-3">
                <Checkbox
                  checked={updates.is_kids === true}
                  onChange={(checked) => handleCheckboxChange('is_kids', checked ? true : null)}
                  label="Mark as Kid's"
                  disabled={isSaving}
                />
                {updates.is_kids === true && (
                  <button
                    className={CLEAR_BTN}
                    onClick={() => handleCheckboxChange('is_kids', null)}
                    disabled={isSaving}
                    type="button"
                  >
                    Clear
                  </button>
                )}
              </div>
              <div className="flex flex-row items-center gap-3">
                <Checkbox
                  checked={updates.is_one_off === true}
                  onChange={(checked) => handleCheckboxChange('is_one_off', checked ? true : null)}
                  label="Mark as One-Off"
                  disabled={isSaving}
                />
                {updates.is_one_off === true && (
                  <button
                    className={CLEAR_BTN}
                    onClick={() => handleCheckboxChange('is_one_off', null)}
                    disabled={isSaving}
                    type="button"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>
          <div className="mt-8 flex justify-end gap-4 border-t border-gray-200 pt-6">
            <button onClick={handleCancel} className={BTN_CANCEL} disabled={isSaving} type="button">
              Cancel
            </button>
            <button onClick={handleSave} disabled={!canSave} className={BTN_SAVE} type="button">
              {isSaving ? 'Updating...' : `Update ${transactionCount} Transactions`}
            </button>
          </div>
        </div>
      </div>
      <CreateCategoryModal
        isOpen={createModalState.isOpen}
        onClose={handleCloseCreateModal}
        onSave={handleSaveNewItem}
        type={createModalState.type}
        parentName={createModalState.parentName}
        parentId={createModalState.parentId}
      />
    </>
  );
}