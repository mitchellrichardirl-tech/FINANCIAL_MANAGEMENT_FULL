/**
 * @file RemapPartyModal.jsx
 * Modal for re-parenting a party from one type to another.
 *
 * Use cases:
 *  - A merchant was auto-categorized under "Unknown" on import and the
 *    user wants to assign it properly.
 *  - The user realizes a party belongs to a different type/category and
 *    wants to move **all** its transactions in one action.
 *
 * The UI mirrors {@link BulkEditModal}'s cascading taxonomy selectors
 * but targets a single party rather than a set of transactions.
 */

import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from './CreateCategoryModal';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('RemapPartyModal');

/**
 * Modal for moving a party to a different parent type.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(partyId: number, newTypeId: number) => Promise<void>} props.onSave
 * @param {Array<Object>} props.parties
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {(name: string, desc?: string) => Promise<Object>} props.onCategoryCreated
 * @param {(name: string, categoryId: number, desc?: string) => Promise<Object>} props.onSubCategoryCreated
 * @param {(name: string, subCategoryId: number, desc?: string) => Promise<Object>} props.onTypeCreated
 * @param {?number} [props.initialPartyId=null]
 * @returns {JSX.Element|null}
 */
export default function RemapPartyModal({
  isOpen,
  onClose,
  onSave,
  parties,
  categories,
  subCategories,
  types,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  initialPartyId = null,
}) {
  const [selectedPartyId, setSelectedPartyId] = useState(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [saving, setSaving] = useState(false);

  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null,
  });

  useEffect(() => {
    if (isOpen) {
      setSelectedPartyId(initialPartyId);
      setSelectedCategoryId(null);
      setSelectedSubCategoryId(null);
      setSelectedTypeId(null);
      setSaving(false);
    }
  }, [isOpen, initialPartyId]);

  const selectedParty = useMemo(
    () => parties.find((p) => p.id === selectedPartyId) ?? null,
    [parties, selectedPartyId]
  );

  const currentMapping = useMemo(() => {
    if (!selectedParty) return null;
    const type = types.find((t) => t.id === selectedParty.type_id);
    if (!type) return null;
    const subCategory = subCategories.find((sc) => sc.id === type.sub_category_id);
    const category = subCategory ? categories.find((c) => c.id === subCategory.category_id) : null;
    return {
      category: category?.category ?? 'Unknown',
      subCategory: subCategory?.sub_category ?? 'Unknown',
      type: type?.type ?? 'Unknown',
    };
  }, [selectedParty, types, subCategories, categories]);

  const unknownTypeId = useMemo(
    () => types.find((t) => t.type === 'Unknown')?.id ?? null,
    [types]
  );

  const sortedParties = useMemo(() => {
    const unknown = parties.filter((p) => p.type_id === unknownTypeId).sort((a, b) => a.name.localeCompare(b.name));
    const known = parties.filter((p) => p.type_id !== unknownTypeId).sort((a, b) => a.name.localeCompare(b.name));
    return [...unknown, ...known];
  }, [parties, unknownTypeId]);

  const filteredSubCategories = useMemo(() => {
    if (!selectedCategoryId) return [];
    return [...subCategories].filter((sc) => sc.category_id === selectedCategoryId).sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, selectedCategoryId]);

  const filteredTypes = useMemo(() => {
    if (!selectedSubCategoryId) return [];
    return [...types].filter((t) => t.sub_category_id === selectedSubCategoryId).sort((a, b) => a.type.localeCompare(b.type));
  }, [types, selectedSubCategoryId]);

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  const handlePartyChange = (partyId) => {
    setSelectedPartyId(partyId ? parseInt(partyId) : null);
    setSelectedCategoryId(null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
  };

  const handleCategoryChange = (categoryId) => {
    setSelectedCategoryId(categoryId ? parseInt(categoryId) : null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
  };

  const handleSubCategoryChange = (subCategoryId) => {
    if (subCategoryId) {
      const sc = subCategories.find((s) => s.id === parseInt(subCategoryId));
      setSelectedCategoryId(sc?.category_id ?? selectedCategoryId);
    }
    setSelectedSubCategoryId(subCategoryId ? parseInt(subCategoryId) : null);
    setSelectedTypeId(null);
  };

  const handleTypeChange = (typeId) => {
    if (typeId) {
      const type = types.find((t) => t.id === parseInt(typeId));
      const sc = type ? subCategories.find((s) => s.id === type.sub_category_id) : null;
      setSelectedSubCategoryId(type?.sub_category_id ?? selectedSubCategoryId);
      setSelectedCategoryId(sc?.category_id ?? selectedCategoryId);
    }
    setSelectedTypeId(typeId ? parseInt(typeId) : null);
  };

  const handleCreateCategory = () => {
    setCreateModalState({ isOpen: true, type: 'category', parentName: '', parentId: null });
  };

  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === selectedCategoryId);
    setCreateModalState({ isOpen: true, type: 'sub_category', parentName: cat.category, parentId: cat.id });
  };

  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === selectedSubCategoryId);
    setCreateModalState({ isOpen: true, type: 'type', parentName: sc.sub_category, parentId: sc.id });
  };

  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
    try {
      let newItem;
      switch (type) {
        case 'category':
          newItem = await onCategoryCreated(name, description);
          if (newItem?.id) { setSelectedCategoryId(newItem.id); setSelectedSubCategoryId(null); setSelectedTypeId(null); }
          break;
        case 'sub_category':
          newItem = await onSubCategoryCreated(name, parentId, description);
          if (newItem?.id) { setSelectedSubCategoryId(newItem.id); setSelectedTypeId(null); }
          break;
        case 'type':
          newItem = await onTypeCreated(name, parentId, description);
          if (newItem?.id) setSelectedTypeId(newItem.id);
          break;
      }
      setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
      return newItem;
    } catch (err) {
      logger.error('Error creating item:', err);
      throw err;
    }
  };

  const handleCloseCreateModal = () => {
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
  };

  const handleSave = async () => {
    if (!selectedPartyId || !selectedTypeId) return;
    setSaving(true);
    try {
      await onSave(selectedPartyId, selectedTypeId);
      handleClose();
    } catch {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (saving) return;
    setSelectedPartyId(null);
    setSelectedCategoryId(null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  if (!isOpen) return null;

  const isChanged = selectedTypeId !== null && selectedParty?.type_id !== selectedTypeId;
  const canSave = isChanged && !saving;
  const partyLabel = (p) => (p.type_id === unknownTypeId ? `⚠ ${p.name}` : p.name);

  return (
    <>
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000] p-[1rem]" onClick={handleBackdropClick}>
        <div className="bg-white rounded-[8px] shadow-[0_4px_24px_rgba(0,0,0,0.18)] flex flex-col max-h-[90vh] w-full max-w-[520px] overflow-hidden" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between px-[1.5rem] pt-[1.25rem] pb-[1rem] border-b border-[#e5e7eb] shrink-0">
            <h2 className="m-0 text-[1.2rem] font-semibold text-[#111827]">Remap Party</h2>
            <button
              className="bg-none border-none text-[1.5rem] leading-[1] cursor-pointer text-[#6b7280] px-[0.25rem] rounded-[4px] transition-[color,background] duration-150 hover:not-disabled:text-[#111827] hover:not-disabled:bg-[#f3f4f6] disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={handleClose}
              disabled={saving}
              aria-label="Close modal"
            >
              ×
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-[1.5rem] py-[1rem] flex flex-col gap-[1.25rem]">
            <div className="flex flex-col gap-[0.75rem]">
              <h3 className="m-0 text-[0.95rem] font-semibold text-[#374151] uppercase tracking-[0.05em]">Party</h3>
              <p className="m-0 text-[0.8rem] text-[#6b7280] leading-[1.4]">
                Select the party whose category mapping you want to change. Uncategorised parties are marked with ⚠.
              </p>
              <div className="flex flex-col gap-[0.3rem]">
                <label className="text-[0.85rem] font-medium text-[#374151]">Party</label>
                <DropdownWithCreate value={selectedPartyId} onChange={handlePartyChange} options={sortedParties} valueKey="id" labelKey="name" getLabel={partyLabel} includeEmpty emptyLabel="Select a party..." disabled={saving} />
              </div>
              {currentMapping && (
                <div className="flex flex-wrap items-center gap-[0.4rem] py-[0.5rem] px-[0.75rem] bg-[#f9fafb] border border-[#e5e7eb] rounded-[6px] text-[0.82rem]">
                  <span className="text-[#6b7280] font-medium whitespace-nowrap">Currently mapped to:</span>
                  <span className="text-[#111827] font-normal">{currentMapping.category} → {currentMapping.subCategory} → {currentMapping.type}</span>
                </div>
              )}
            </div>

            {selectedPartyId && (
              <div className="flex flex-col gap-[0.75rem]">
                <h3 className="m-0 text-[0.95rem] font-semibold text-[#374151] uppercase tracking-[0.05em]">New Category</h3>
                <p className="m-0 text-[0.8rem] text-[#6b7280] leading-[1.4]">
                  Select at any level — parent levels will be set automatically. Lower levels will be cleared when you change a higher level.
                </p>
                <div className="flex flex-col gap-[0.3rem]">
                  <label className="text-[0.85rem] font-medium text-[#374151]">Category</label>
                  <DropdownWithCreate value={selectedCategoryId} onChange={handleCategoryChange} options={sortedCategories} valueKey="id" labelKey="category" includeEmpty emptyLabel="Select category..." onCreateNew={handleCreateCategory} createLabel="➕ Create New Category..." disabled={saving} />
                </div>
                <div className="flex flex-col gap-[0.3rem]">
                  <label className="text-[0.85rem] font-medium text-[#374151]">Sub-Category</label>
                  <DropdownWithCreate value={selectedSubCategoryId} onChange={handleSubCategoryChange} options={filteredSubCategories} valueKey="id" labelKey="sub_category" includeEmpty emptyLabel={selectedCategoryId ? 'Select sub-category...' : 'Select a category first'} onCreateNew={selectedCategoryId ? handleCreateSubCategory : null} createLabel="➕ Create New Sub-Category..." disabled={saving || !selectedCategoryId} />
                </div>
                <div className="flex flex-col gap-[0.3rem]">
                  <label className="text-[0.85rem] font-medium text-[#374151]">Type</label>
                  <DropdownWithCreate value={selectedTypeId} onChange={handleTypeChange} options={filteredTypes} valueKey="id" labelKey="type" includeEmpty emptyLabel={selectedSubCategoryId ? 'Select type...' : 'Select a sub-category first'} onCreateNew={selectedSubCategoryId ? handleCreateType : null} createLabel="➕ Create New Type..." disabled={saving || !selectedSubCategoryId} />
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-[0.75rem] px-[1.5rem] py-[1rem] border-t border-[#e5e7eb] shrink-0">
            <button className="py-[0.5rem] px-[1.1rem] border border-[#d1d5db] rounded-[6px] bg-white text-[#374151] text-[0.9rem] cursor-pointer transition-[background,border-color] duration-150 hover:not-disabled:bg-[#f9fafb] hover:not-disabled:border-[#9ca3af] disabled:opacity-50 disabled:cursor-not-allowed" onClick={handleClose} disabled={saving} type="button">
              Cancel
            </button>
            <button className="py-[0.5rem] px-[1.25rem] border-none rounded-[6px] bg-[#2563eb] text-white text-[0.9rem] font-medium cursor-pointer transition-colors duration-150 hover:not-disabled:bg-[#1d4ed8] disabled:bg-[#93c5fd] disabled:cursor-not-allowed" onClick={handleSave} disabled={!canSave} type="button">
              {saving ? 'Remapping...' : 'Remap Party'}
            </button>
          </div>
        </div>
      </div>

      <CreateCategoryModal isOpen={createModalState.isOpen} onClose={handleCloseCreateModal} onSave={handleSaveNewItem} type={createModalState.type} parentName={createModalState.parentName} parentId={createModalState.parentId} />
    </>
  );
}
