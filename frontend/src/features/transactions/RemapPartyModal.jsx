import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from './CreateCategoryModal';
import './RemapPartyModal.css';
import { createLogger } from '@/lib/logger';

const logger = createLogger('RemapPartyModal');

export default function RemapPartyModal({
  isOpen, onClose, onSave, parties, categories, subCategories, types,
  onCategoryCreated, onSubCategoryCreated, onTypeCreated,
  initialPartyId = null,
}) {
  const [selectedPartyId, setSelectedPartyId] = useState(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [saving, setSaving] = useState(false);
  // error state removed — parent handles all messaging

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

  // ── Derived data (unchanged) ──
  const selectedParty = useMemo(
    () => parties.find((p) => p.id === selectedPartyId) ?? null,
    [parties, selectedPartyId]
  );

  const currentMapping = useMemo(() => {
    if (!selectedParty) return null;
    const type = types.find((t) => t.id === selectedParty.type_id);
    if (!type) return null;
    const subCategory = subCategories.find((sc) => sc.id === type.sub_category_id);
    const category = subCategory
      ? categories.find((c) => c.id === subCategory.category_id)
      : null;
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

  // ── Change handlers (unchanged) ──
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

  // ── Create-new handlers — dead validation removed ──
  const handleCreateCategory = () => {
    setCreateModalState({ isOpen: true, type: 'category', parentName: '', parentId: null });
  };

  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === selectedCategoryId);
    setCreateModalState({
      isOpen: true, type: 'sub_category',
      parentName: cat.category, parentId: cat.id,
    });
  };

  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === selectedSubCategoryId);
    setCreateModalState({
      isOpen: true, type: 'type',
      parentName: sc.sub_category, parentId: sc.id,
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
            setSelectedCategoryId(newItem.id);
            setSelectedSubCategoryId(null);
            setSelectedTypeId(null);
          }
          break;
        case 'sub_category':
          newItem = await onSubCategoryCreated(name, parentId, description);
          if (newItem?.id) {
            setSelectedSubCategoryId(newItem.id);
            setSelectedTypeId(null);
          }
          break;
        case 'type':
          newItem = await onTypeCreated(name, parentId, description);
          if (newItem?.id) setSelectedTypeId(newItem.id);
          break;
      }
      setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
      return newItem;
    } catch (err) {
      // parent's create handlers already toast
      logger.error('Error creating item:', err);
      throw err;
    }
  };

  const handleCloseCreateModal = () => {
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
  };

  // ── Save — simplified, parent handles all messaging ──
  const handleSave = async () => {
    if (!selectedPartyId || !selectedTypeId) return;
    setSaving(true);
    try {
      await onSave(selectedPartyId, selectedTypeId);
      handleClose();
    } catch {
      // parent already toasted — just release the spinner
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
      <div className="modal-overlay" onClick={handleBackdropClick}>
        <div className="modal-content remap-modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>Remap Party</h2>
            <button className="modal-close-btn" onClick={handleClose} disabled={saving} aria-label="Close modal">×</button>
          </div>

          {/* error banner removed */}

          <div className="bulk-edit-form">
            <div className="form-section">
              <h3>Party</h3>
              <p className="form-hint">
                Select the party whose category mapping you want to change.
                Uncategorised parties are marked with ⚠.
              </p>
              <div className="form-field">
                <label>Party</label>
                <DropdownWithCreate
                  value={selectedPartyId}
                  onChange={handlePartyChange}
                  options={sortedParties}
                  valueKey="id"
                  labelKey="name"
                  getLabel={partyLabel}
                  includeEmpty
                  emptyLabel="Select a party..."
                  disabled={saving}
                />
              </div>
              {currentMapping && (
                <div className="current-mapping">
                  <span className="mapping-label">Currently mapped to:</span>
                  <span className="mapping-path">
                    {currentMapping.category} → {currentMapping.subCategory} → {currentMapping.type}
                  </span>
                </div>
              )}
            </div>

            {selectedPartyId && (
              <div className="form-section">
                <h3>New Category</h3>
                <p className="form-hint">
                  Select at any level — parent levels will be set automatically.
                  Lower levels will be cleared when you change a higher level.
                </p>
                <div className="form-field">
                  <label>Category</label>
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
                <div className="form-field">
                  <label>Sub-Category</label>
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
                <div className="form-field">
                  <label>Type</label>
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

          <div className="modal-actions">
            <button className="cancel-button" onClick={handleClose} disabled={saving} type="button">Cancel</button>
            <button className="save-button" onClick={handleSave} disabled={!canSave} type="button">
              {saving ? 'Remapping...' : 'Remap Party'}
            </button>
          </div>
        </div>a
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