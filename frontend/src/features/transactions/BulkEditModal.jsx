import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import Checkbox from '@/components/Checkbox';
import CreateCategoryModal from './CreateCategoryModal';
import {
  overlayCls, dialogCls, headerCls, headerTitleCls, closeBtnCls,
  errorBannerCls, errorCloseCls, bodyCls, sectionCls, sectionTitleCls,
  formHintCls, formFieldCls, formLabelCls, footerCls, cancelBtnCls,
  saveBtnCls, checkboxFieldCls, clearBtnCls,
} from './_modalShell';
import { createLogger } from '@/lib/logger';

const logger = createLogger('BulkEditModal');

const EMPTY_DRAFT = {
  category_id: null,
  sub_category_id: null,
  type_id: null,
  party_id: null,
  party_name: '',
  is_kids: null,
  is_one_off: null,
};

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
  const [updates, setUpdates] = useState(EMPTY_DRAFT);
  const [isSaving, setIsSaving] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [createModalState, setCreateModalState] = useState({
    isOpen: false, type: null, parentName: '', parentId: null,
  });

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  const filteredSubCategories = useMemo(() => {
    let f = [...subCategories];
    if (updates.category_id) f = f.filter((sc) => sc.category_id === updates.category_id);
    return f.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, updates.category_id]);

  const filteredTypes = useMemo(() => {
    let f = [...types];
    if (updates.sub_category_id) {
      f = f.filter((t) => t.sub_category_id === updates.sub_category_id);
    } else if (updates.category_id) {
      const ids = subCategories.filter((sc) => sc.category_id === updates.category_id).map((sc) => sc.id);
      f = f.filter((t) => ids.includes(t.sub_category_id));
    }
    return f.sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategories, updates.sub_category_id, updates.category_id]);

  const filteredParties = useMemo(() => {
    let f = [...parties];
    if (updates.type_id) {
      f = f.filter((p) => p.type_id === updates.type_id);
    } else if (updates.sub_category_id) {
      const ids = types.filter((t) => t.sub_category_id === updates.sub_category_id).map((t) => t.id);
      f = f.filter((p) => ids.includes(p.type_id));
    } else if (updates.category_id) {
      const sids = subCategories.filter((sc) => sc.category_id === updates.category_id).map((sc) => sc.id);
      const tids = types.filter((t) => sids.includes(t.sub_category_id)).map((t) => t.id);
      f = f.filter((p) => tids.includes(p.type_id));
    }
    return f.sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, types, subCategories, updates.type_id, updates.sub_category_id, updates.category_id]);

  useEffect(() => {
    if (isOpen) {
      setUpdates(EMPTY_DRAFT);
      setValidationError(null);
      setIsSaving(false);
    }
  }, [isOpen]);

  const handleCategoryChange = (categoryId) => {
    setUpdates((prev) => ({
      ...prev,
      category_id: categoryId ? parseInt(categoryId) : null,
      sub_category_id: null, type_id: null, party_id: null, party_name: '',
    }));
  };

  const handleSubCategoryChange = (subCategoryId) => {
    if (subCategoryId) {
      const sc = subCategories.find((s) => s.id === parseInt(subCategoryId));
      if (sc) {
        setUpdates((prev) => ({
          ...prev,
          category_id: sc.category_id,
          sub_category_id: parseInt(subCategoryId),
          type_id: null, party_id: null, party_name: '',
        }));
      }
    } else {
      setUpdates((prev) => ({ ...prev, sub_category_id: null, type_id: null, party_id: null, party_name: '' }));
    }
  };

  const handleTypeChange = (typeId) => {
    if (typeId) {
      const type = types.find((t) => t.id === parseInt(typeId));
      if (type) {
        const sc = subCategories.find((s) => s.id === type.sub_category_id);
        setUpdates((prev) => ({
          ...prev,
          category_id: sc ? sc.category_id : prev.category_id,
          sub_category_id: type.sub_category_id,
          type_id: parseInt(typeId),
          party_id: null, party_name: '',
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
        const sc = type ? subCategories.find((s) => s.id === type.sub_category_id) : null;
        setUpdates((prev) => ({
          ...prev,
          category_id: sc ? sc.category_id : prev.category_id,
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

  const openCreate = (type, parentName, parentId) =>
    setCreateModalState({ isOpen: true, type, parentName, parentId });

  const handleCreateCategory = () => openCreate('category', '', null);
  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === updates.category_id);
    openCreate('sub_category', cat.category, cat.id);
  };
  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === updates.sub_category_id);
    openCreate('type', sc.sub_category, sc.id);
  };
  const handleCreateParty = () => {
    const t = types.find((x) => x.id === updates.type_id);
    openCreate('party', t.type, t.id);
  };

  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
    let newItem;
    switch (type) {
      case 'category':
        newItem = await onCategoryCreated(name, description);
        if (newItem?.id) handleCategoryChange(newItem.id);
        break;
      case 'sub_category':
        newItem = await onSubCategoryCreated(name, parentId, description);
        if (newItem?.id) handleSubCategoryChange(newItem.id);
        break;
      case 'type':
        newItem = await onTypeCreated(name, parentId, description);
        if (newItem?.id) handleTypeChange(newItem.id);
        break;
      case 'party':
        newItem = await onPartyCreated(name, parentId, description);
        if (newItem?.id) {
          setUpdates((prev) => ({
            ...prev, party_id: newItem.id, party_name: newItem.name || name,
          }));
        }
        break;
    }
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
    return newItem;
  };

  const handleSave = async () => {
    setValidationError(null);
    setIsSaving(true);
    try {
      const finalUpdates = {};
      if (updates.party_id) finalUpdates.party_id = updates.party_id;
      if (updates.is_kids !== null) finalUpdates.is_kids = updates.is_kids;
      if (updates.is_one_off !== null) finalUpdates.is_one_off = updates.is_one_off;

      if (Object.keys(finalUpdates).length === 0) {
        setValidationError('No changes to save');
        setIsSaving(false);
        return;
      }
      await onSave(finalUpdates);
    } catch (err) {
      logger.error('BulkEditModal: Save failed:', err);
      setIsSaving(false);
    }
  };

  const resetAndClose = () => {
    setUpdates(EMPTY_DRAFT);
    setValidationError(null);
    setIsSaving(false);
    onClose();
  };

  const handleCancel = () => { if (!isSaving) resetAndClose(); };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSaving) resetAndClose();
  };
  const closeCreateModal = () =>
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });

  if (!isOpen) return null;

  const canSave =
    !isSaving && (updates.party_id || updates.is_kids !== null || updates.is_one_off !== null);

  return (
    <>
      <div onClick={handleBackdropClick} className={overlayCls}>
        <div onClick={(e) => e.stopPropagation()} className={dialogCls}>
          <div className={headerCls}>
            <h2 className={headerTitleCls}>Bulk Edit {transactionCount} Transactions</h2>
            <button type="button" onClick={handleCancel} disabled={isSaving} aria-label="Close modal" className={closeBtnCls}>
              ×
            </button>
          </div>

          {validationError && (
            <div className={errorBannerCls}>
              {validationError}
              <button type="button" onClick={() => setValidationError(null)} aria-label="Dismiss error" className={errorCloseCls}>
                ×
              </button>
            </div>
          )}

          <div className={bodyCls}>
            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Category Hierarchy</h3>
              <p className={formHintCls}>
                Select at any level - parent levels will be set automatically. Lower levels will be cleared when you change a higher level.
              </p>

              {[
                ['Category', updates.category_id, handleCategoryChange, sortedCategories, 'category', handleCreateCategory, true],
                ['Sub-Category', updates.sub_category_id, handleSubCategoryChange, filteredSubCategories, 'sub_category', updates.category_id ? handleCreateSubCategory : null, false],
                ['Type', updates.type_id, handleTypeChange, filteredTypes, 'type', updates.sub_category_id ? handleCreateType : null, false],
                ['Party', updates.party_id, handlePartyChange, filteredParties, 'name', updates.type_id ? handleCreateParty : null, false],
              ].map(([label, value, onChange, options, labelKey, onCreate]) => (
                <div key={label} className={formFieldCls}>
                  <label className={formLabelCls}>{label}</label>
                  <DropdownWithCreate
                    value={value}
                    onChange={onChange}
                    options={options}
                    valueKey="id"
                    labelKey={labelKey}
                    includeEmpty
                    emptyLabel="-- No Change --"
                    onCreateNew={onCreate}
                    createLabel={`➕ Create New ${label}...`}
                    disabled={isSaving}
                  />
                </div>
              ))}
            </div>

            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Flags</h3>

              {[
                ['is_kids', "Mark as Kid's"],
                ['is_one_off', 'Mark as One-Off'],
              ].map(([field, label]) => (
                <div key={field} className={`${formFieldCls} ${checkboxFieldCls}`}>
                  <Checkbox
                    checked={updates[field] === true}
                    onChange={(checked) => handleCheckboxChange(field, checked ? true : null)}
                    label={label}
                    disabled={isSaving}
                  />
                  {updates[field] === true && (
                    <button
                      type="button"
                      onClick={() => handleCheckboxChange(field, null)}
                      disabled={isSaving}
                      className={clearBtnCls}
                    >
                      Clear
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className={footerCls}>
            <button type="button" onClick={handleCancel} disabled={isSaving} className={cancelBtnCls}>
              Cancel
            </button>
            <button type="button" onClick={handleSave} disabled={!canSave} className={saveBtnCls}>
              {isSaving ? 'Updating...' : `Update ${transactionCount} Transactions`}
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
