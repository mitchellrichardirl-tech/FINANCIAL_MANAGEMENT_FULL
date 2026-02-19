import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from './DropdownWithCreate';
import Checkbox from './Checkbox';
import CreateCategoryModal from './CreateCategoryModal';
import './BulkEditModal.css';

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
  onPartyCreated
}) {
  const [updates, setUpdates] = useState({
    category_id: null,
    sub_category_id: null,
    type_id: null,
    party_id: null,
    party_name: '',
    is_kids: null,
    is_one_off: null
  });

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null
  });

  // Memoized sorted and filtered arrays
  const sortedCategories = useMemo(() => 
    [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  const filteredSubCategories = useMemo(() => {
    let filtered = [...subCategories];
    
    if (updates.category_id) {
      filtered = filtered.filter(sc => sc.category_id === updates.category_id);
    }
    
    return filtered.sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, updates.category_id]);

  const filteredTypes = useMemo(() => {
    let filtered = [...types];
    
    if (updates.sub_category_id) {
      filtered = filtered.filter(t => t.sub_category_id === updates.sub_category_id);
    } else if (updates.category_id) {
      const subCatIds = subCategories
        .filter(sc => sc.category_id === updates.category_id)
        .map(sc => sc.id);
      filtered = filtered.filter(t => subCatIds.includes(t.sub_category_id));
    }
    
    return filtered.sort((a, b) => a.type.localeCompare(b.type));
  }, [types, subCategories, updates.sub_category_id, updates.category_id]);

  const filteredParties = useMemo(() => {
    let filtered = [...parties];
    
    if (updates.type_id) {
      filtered = filtered.filter(p => p.type_id === updates.type_id);
    } else if (updates.sub_category_id) {
      const typeIds = types
        .filter(t => t.sub_category_id === updates.sub_category_id)
        .map(t => t.id);
      filtered = filtered.filter(p => typeIds.includes(p.type_id));
    } else if (updates.category_id) {
      const subCatIds = subCategories
        .filter(sc => sc.category_id === updates.category_id)
        .map(sc => sc.id);
      const typeIds = types
        .filter(t => subCatIds.includes(t.sub_category_id))
        .map(t => t.id);
      filtered = filtered.filter(p => typeIds.includes(p.type_id));
    }
    
    return filtered.sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, types, subCategories, updates.type_id, updates.sub_category_id, updates.category_id]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setUpdates({
        category_id: null,
        sub_category_id: null,
        type_id: null,
        party_id: null,
        party_name: '',
        is_kids: null,
        is_one_off: null
      });
      setError(null);
      setIsSaving(false);
    }
  }, [isOpen]);

  const handleCategoryChange = (categoryId) => {
    setUpdates(prev => ({
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
      const subCategory = subCategories.find(sc => sc.id === parseInt(subCategoryId));
      if (subCategory) {
        setUpdates(prev => ({
          ...prev,
          category_id: subCategory.category_id,
          sub_category_id: parseInt(subCategoryId),
          type_id: null,
          party_id: null,
          party_name: '',
        }));
      }
    } else {
      setUpdates(prev => ({
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
      const type = types.find(t => t.id === parseInt(typeId));
      if (type) {
        const subCategory = subCategories.find(sc => sc.id === type.sub_category_id);
        setUpdates(prev => ({
          ...prev,
          category_id: subCategory ? subCategory.category_id : prev.category_id,
          sub_category_id: type.sub_category_id,
          type_id: parseInt(typeId),
          party_id: null,
          party_name: '',
        }));
      }
    } else {
      setUpdates(prev => ({
        ...prev,
        type_id: null,
        party_id: null,
        party_name: '',
      }));
    }
  };

  const handlePartyChange = (partyId) => {
    if (partyId) {
      const party = parties.find(p => p.id === parseInt(partyId));
      if (party) {
        const type = types.find(t => t.id === party.type_id);
        const subCategory = type ? subCategories.find(sc => sc.id === type.sub_category_id) : null;
        
        setUpdates(prev => ({
          ...prev,
          category_id: subCategory ? subCategory.category_id : prev.category_id,
          sub_category_id: type ? type.sub_category_id : prev.sub_category_id,
          type_id: party.type_id,
          party_id: parseInt(partyId),
          party_name: party.name
        }));
      }
    } else {
      setUpdates(prev => ({
        ...prev,
        party_id: null,
        party_name: ''
      }));
    }
  };

  const handleCheckboxChange = (field, value) => {
    setUpdates(prev => ({ ...prev, [field]: value }));
  };

  const handleCreateCategory = () => {
    setCreateModalState({
      isOpen: true,
      type: 'category',
      parentName: '',
      parentId: null
    });
  };

  const handleCreateSubCategory = () => {
    const currentCategory = updates.category_id 
      ? categories.find(c => c.id === updates.category_id)
      : null;
    
    if (!currentCategory) {
      setError('Please select a category first');
      return;
    }
      
    setCreateModalState({
      isOpen: true,
      type: 'sub_category',
      parentName: currentCategory.category,
      parentId: currentCategory.id
    });
  };

  const handleCreateType = () => {
    const currentSubCategory = updates.sub_category_id
      ? subCategories.find(sc => sc.id === updates.sub_category_id)
      : null;
    
    if (!currentSubCategory) {
      setError('Please select a sub-category first');
      return;
    }
      
    setCreateModalState({
      isOpen: true,
      type: 'type',
      parentName: currentSubCategory.sub_category,
      parentId: currentSubCategory.id
    });
  };

  const handleCreateParty = () => {
    const currentType = updates.type_id
      ? types.find(t => t.id === updates.type_id)
      : null;
    
    if (!currentType) {
      setError('Please select a type first');
      return;
    }
      
    setCreateModalState({
      isOpen: true,
      type: 'party',
      parentName: currentType.type,
      parentId: currentType.id
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
            setUpdates(prev => ({ 
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
            setUpdates(prev => ({ 
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
            setUpdates(prev => ({ 
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
            setUpdates(prev => ({ 
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
      console.error('Error creating item:', err);
      throw err;
    }
  };

  const handleSave = async () => {
    console.log('BulkEditModal: handleSave called');
    setError(null);
    setIsSaving(true);
    
    try {
      const finalUpdates = {};
      
      if (updates.party_id) {
        finalUpdates.party_id = updates.party_id;
      }
      
      if (updates.is_kids !== null) {
        finalUpdates.is_kids = updates.is_kids;
      }
      
      if (updates.is_one_off !== null) {
        finalUpdates.is_one_off = updates.is_one_off;
      }

      console.log('BulkEditModal: Prepared updates:', finalUpdates);

      if (Object.keys(finalUpdates).length === 0) {
        setError('No changes to save');
        setIsSaving(false);
        return;
      }

      console.log('BulkEditModal: Calling onSave...');
      await onSave(finalUpdates);
      console.log('BulkEditModal: onSave completed successfully');
      
      setIsSaving(false);
      
    } catch (err) {
      console.error('BulkEditModal: Save failed:', err);
      setError(err.message || 'Failed to save changes');
      setIsSaving(false);
    }
  };

  const resetAndClose = () => {
    setUpdates({
      category_id: null,
      sub_category_id: null,
      type_id: null,
      party_id: null,
      party_name: '',
      is_kids: null,
      is_one_off: null
    });
    setError(null);
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

  const canSave = !isSaving && (
    updates.party_id || 
    updates.is_kids !== null || 
    updates.is_one_off !== null
  );

  return (
    <>
      <div className="modal-overlay" onClick={handleBackdropClick}>
        <div className="modal-content" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>Bulk Edit {transactionCount} Transactions</h2>
            <button 
              className="modal-close-btn" 
              onClick={handleCancel}
              disabled={isSaving}
              aria-label="Close modal"
            >
              ×
            </button>
          </div>
          
          {error && (
            <div className="modal-error">
              {error}
              <button onClick={() => setError(null)} aria-label="Dismiss error">×</button>
            </div>
          )}
          
          <div className="bulk-edit-form">
            <div className="form-section">
              <h3>Category Hierarchy</h3>
              <p className="form-hint">
                Select at any level - parent levels will be set automatically. 
                Lower levels will be cleared when you change a higher level.
              </p>
              
              <div className="form-field">
                <label>Category</label>
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

              <div className="form-field">
                <label>Sub-Category</label>
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

              <div className="form-field">
                <label>Type</label>
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

              <div className="form-field">
                <label>Party</label>
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

            <div className="form-section">
              <h3>Flags</h3>
              
              <div className="form-field checkbox-field">
                <Checkbox
                  checked={updates.is_kids === true}
                  onChange={(checked) => handleCheckboxChange('is_kids', checked ? true : null)}
                  label="Mark as Kid's"
                  disabled={isSaving}
                />
                {updates.is_kids === true && (
                  <button 
                    className="clear-btn" 
                    onClick={() => handleCheckboxChange('is_kids', null)}
                    disabled={isSaving}
                    type="button"
                  >
                    Clear
                  </button>
                )}
              </div>

              <div className="form-field checkbox-field">
                <Checkbox
                  checked={updates.is_one_off === true}
                  onChange={(checked) => handleCheckboxChange('is_one_off', checked ? true : null)}
                  label="Mark as One-Off"
                  disabled={isSaving}
                />
                {updates.is_one_off === true && (
                  <button 
                    className="clear-btn" 
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

          <div className="modal-actions">
            <button 
              onClick={handleCancel} 
              className="cancel-button"
              disabled={isSaving}
              type="button"
            >
              Cancel
            </button>
            <button 
              onClick={handleSave} 
              disabled={!canSave}
              className="save-button"
              type="button"
            >
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