import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from './CreateCategoryModal';
import {
  overlayCls, headerCls, headerTitleCls, closeBtnCls, bodyCls,
  sectionCls, sectionTitleCls, formHintCls, formFieldCls,
  formLabelCls, footerCls, cancelBtnCls, saveBtnCls,
} from './_modalShell';
import { createLogger } from '@/lib/logger';

const logger = createLogger('RemapPartyModal');
const remapDialogCls =
  'bg-white rounded-lg shadow-[0_4px_24px_rgba(0,0,0,0.18)] flex flex-col max-h-[90vh] w-full max-w-[520px] overflow-hidden';

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
    isOpen: false, type: null, parentName: '', parentId: null,
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
    const sc = subCategories.find((s) => s.id === type.sub_category_id);
    const cat = sc ? categories.find((c) => c.id === sc.category_id) : null;
    return {
      category: cat?.category ?? 'Unknown',
      subCategory: sc?.sub_category ?? 'Unknown',
      type: type?.type ?? 'Unknown',
    };
  }, [selectedParty, types, subCategories, categories]);

  const unknownTypeId = useMemo(
    () => types.find((t) => t.type === 'Unknown')?.id ?? null,
    [types]
  );

  const sortedParties = useMemo(() => {
    const unknown = parties
      .filter((p) => p.type_id === unknownTypeId)
      .sort((a, b) => a.name.localeCompare(b.name));
    const known = parties
      .filter((p) => p.type_id !== unknownTypeId)
      .sort((a, b) => a.name.localeCompare(b.name));
    return [...unknown, ...known];
  }, [parties, unknownTypeId]);

  const filteredSubCategories = useMemo(() => {
    if (!selectedCategoryId) return [];
    return [...subCategories]
      .filter((sc) => sc.category_id === selectedCategoryId)
      .sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, selectedCategoryId]);

  const filteredTypes = useMemo(() => {
    if (!selectedSubCategoryId) return [];
    return [...types]
      .filter((t) => t.sub_category_id === selectedSubCategoryId)
      .sort((a, b) => a.type.localeCompare(b.type));
  }, [types, selectedSubCategoryId]);

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  const handlePartyChange = (partyId) => {
    setSelectedPartyId(partyId ? parseInt(partyId) : null);
    setSelectedCategoryId(null); setSelectedSubCategoryId(null); setSelectedTypeId(null);
  };
  const handleCategoryChange = (categoryId) => {
    setSelectedCategoryId(categoryId ? parseInt(categoryId) : null);
    setSelectedSubCategoryId(null); setSelectedTypeId(null);
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

  const openCreate = (type, parentName, parentId) =>
    setCreateModalState({ isOpen: true, type, parentName, parentId });
  const handleCreateCategory = () => openCreate('category', '', null);
  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === selectedCategoryId);
    openCreate('sub_category', cat.category, cat.id);
  };
  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === selectedSubCategoryId);
    openCreate('type', sc.sub_category, sc.id);
  };

  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
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
  };

  const closeCreateModal = () =>
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });

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
    setSelectedPartyId(null); setSelectedCategoryId(null);
    setSelectedSubCategoryId(null); setSelectedTypeId(null);
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  if (!isOpen) return null;

  const isChanged = selectedTypeId !== null && selectedParty?.type_id !== selectedTypeId;
  const canSave = isChanged && !saving;

  return (
    <>
      <div onClick={handleBackdropClick} className={overlayCls}>
        <div onClick={(e) => e.stopPropagation()} className={remapDialogCls}>
          <div className={headerCls}>
            <h2 className={headerTitleCls}>Remap Party</h2>
            <button type="button" onClick={handleClose} disabled={saving} aria-label="Close modal" className={closeBtnCls}>
              ×
            </button>
          </div>

          <div className={bodyCls}>
            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Party</h3>
              <p className={formHintCls}>
                Select the party whose category mapping you want to change. Uncategorised parties are marked with ⚠.
              </p>
              <div className={formFieldCls}>
                <label className={formLabelCls}>Party</label>
                <DropdownWithCreate
                  value={selectedPartyId}
                  onChange={handlePartyChange}
                  options={sortedParties}
                  valueKey="id"
                  labelKey="name"
                  includeEmpty
                  emptyLabel="Select a party..."
                  disabled={saving}
                />
              </div>
              {currentMapping && (
                <div className="flex flex-wrap items-center gap-[0.4rem] py-2 px-3 bg-[#f9fafb] border border-[#e5e7eb] rounded-md text-[0.82rem]">
                  <span className="text-[#6b7280] font-medium whitespace-nowrap">Currently mapped to:</span>
                  <span className="text-[#111827] font-normal">
                    {currentMapping.category} → {currentMapping.subCategory} → {currentMapping.type}
                  </span>
                </div>
              )}
            </div>

            {selectedPartyId && (
              <div className={sectionCls}>
                <h3 className={sectionTitleCls}>New Category</h3>
                <p className={formHintCls}>
                  Select at any level — parent levels will be set automatically. Lower levels will be cleared when you change a higher level.
                </p>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Category</label>
                  <DropdownWithCreate
                    value={selectedCategoryId}
                    onChange={handleCategoryChange}
                    options={sortedCategories}
                    valueKey="id"
                    labelKey="category"
                    includeEmpty
                    emptyLabel="Select category..."
                    onCreateNew={handleCreateCategory}
                    createLabel="➕ Create New Category..."
                    disabled={saving}
                  />
                </div>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Sub-Category</label>
                  <DropdownWithCreate
                    value={selectedSubCategoryId}
                    onChange={handleSubCategoryChange}
                    options={filteredSubCategories}
                    valueKey="id"
                    labelKey="sub_category"
                    includeEmpty
                    emptyLabel={selectedCategoryId ? 'Select sub-category...' : 'Select a category first'}
                    onCreateNew={selectedCategoryId ? handleCreateSubCategory : null}
                    createLabel="➕ Create New Sub-Category..."
                    disabled={saving || !selectedCategoryId}
                  />
                </div>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Type</label>
                  <DropdownWithCreate
                    value={selectedTypeId}
                    onChange={handleTypeChange}
                    options={filteredTypes}
                    valueKey="id"
                    labelKey="type"
                    includeEmpty
                    emptyLabel={selectedSubCategoryId ? 'Select type...' : 'Select a sub-category first'}
                    onCreateNew={selectedSubCategoryId ? handleCreateType : null}
                    createLabel="➕ Create New Type..."
                    disabled={saving || !selectedSubCategoryId}
                  />
                </div>
              </div>
            )}
          </div>

          <div className={footerCls}>
            <button type="button" onClick={handleClose} disabled={saving} className={cancelBtnCls}>Cancel</button>
            <button type="button" onClick={handleSave} disabled={!canSave} className={saveBtnCls}>
              {saving ? 'Remapping...' : 'Remap Party'}
            </button>
          </div>
        </div>
      </div>

      <CreateCategoryModal
        isOpen={createModalState.isOpen}
        onClose={closeCreateModal}
        onSave={handleSaveNewItem}
        type={createModalState.type}
        parentName={createModalState.parentName}
        parentId={createModalState.parentId}
      />
    </>
  );
}
