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
import './RemapPartyModal.css';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('RemapPartyModal');

/**
 * Modal for moving a party to a different parent type.
 *
 * Workflow:
 *  1. Select (or pre-select via `initialPartyId`) the party to remap.
 *  2. Drill down through category → sub-category → type to pick the
 *     new destination.
 *  3. Save — the backend moves the party (or merges if an identical
 *     name+type already exists) and cascades the change to all linked
 *     transactions.
 *
 * Errors are handled by the parent via toast; this component only owns
 * the spinner state.
 *
 * @component
 * @param {Object} props
 *
 * @param {boolean} props.isOpen - Visibility flag.
 * @param {() => void} props.onClose - Called to close the modal.
 * @param {(partyId: number, newTypeId: number) => Promise<void>} props.onSave
 *        Async callback to persist the remap. Should throw on failure.
 *
 * @param {Array<Object>} props.parties
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 *
 * @param {(name: string, desc?: string) => Promise<Object>} props.onCategoryCreated
 * @param {(name: string, categoryId: number, desc?: string) => Promise<Object>} props.onSubCategoryCreated
 * @param {(name: string, subCategoryId: number, desc?: string) => Promise<Object>} props.onTypeCreated
 *
 * @param {?number} [props.initialPartyId=null]
 *        Pre-select this party when the modal opens.
 *
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
  // ── Local form state ──────────────────────────────────────────────
  const [selectedPartyId, setSelectedPartyId] = useState(null);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [saving, setSaving] = useState(false);

  /** State for the nested create-taxonomy modal. */
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null,
  });

  // Reset form each time the modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedPartyId(initialPartyId);
      setSelectedCategoryId(null);
      setSelectedSubCategoryId(null);
      setSelectedTypeId(null);
      setSaving(false);
    }
  }, [isOpen, initialPartyId]);

  // ── Derived / memoised data ───────────────────────────────────────

  /** Currently selected party object. */
  const selectedParty = useMemo(
    () => parties.find((p) => p.id === selectedPartyId) ?? null,
    [parties, selectedPartyId]
  );

  /**
   * The party's existing mapping, resolved into display names.
   * Shown so the user can see where the party currently lives.
   */
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

  /** Id of the "Unknown" type, used to flag uncategorized parties. */
  const unknownTypeId = useMemo(
    () => types.find((t) => t.type === 'Unknown')?.id ?? null,
    [types]
  );

  /**
   * Parties sorted with "Unknown" type first (they're the ones most
   * likely to need remapping) then alphabetically.
   */
  const sortedParties = useMemo(() => {
    const unknown = parties
      .filter((p) => p.type_id === unknownTypeId)
      .sort((a, b) => a.name.localeCompare(b.name));
    const known = parties
      .filter((p) => p.type_id !== unknownTypeId)
      .sort((a, b) => a.name.localeCompare(b.name));
    return [...unknown, ...known];
  }, [parties, unknownTypeId]);

  /** Sub-categories filtered to the selected category. */
  const filteredSubCategories = useMemo(() => {
    if (!selectedCategoryId) return [];
    return [...subCategories]
      .filter((sc) => sc.category_id === selectedCategoryId)
      .sort((a, b) => a.sub_category.localeCompare(b.sub_category));
  }, [subCategories, selectedCategoryId]);

  /** Types filtered to the selected sub-category. */
  const filteredTypes = useMemo(() => {
    if (!selectedSubCategoryId) return [];
    return [...types]
      .filter((t) => t.sub_category_id === selectedSubCategoryId)
      .sort((a, b) => a.type.localeCompare(b.type));
  }, [types, selectedSubCategoryId]);

  /** Categories sorted alphabetically. */
  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
  );

  // ── Change handlers ───────────────────────────────────────────────

  /**
   * Select a party; reset the destination hierarchy.
   * @param {?string} partyId
   */
  const handlePartyChange = (partyId) => {
    setSelectedPartyId(partyId ? parseInt(partyId) : null);
    setSelectedCategoryId(null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
  };

  /** Select a category; clear children. */
  const handleCategoryChange = (categoryId) => {
    setSelectedCategoryId(categoryId ? parseInt(categoryId) : null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
  };

  /** Select a sub-category; auto-fill parent category, clear type. */
  const handleSubCategoryChange = (subCategoryId) => {
    if (subCategoryId) {
      const sc = subCategories.find((s) => s.id === parseInt(subCategoryId));
      setSelectedCategoryId(sc?.category_id ?? selectedCategoryId);
    }
    setSelectedSubCategoryId(subCategoryId ? parseInt(subCategoryId) : null);
    setSelectedTypeId(null);
  };

  /** Select a type; auto-fill parent sub-category and category. */
  const handleTypeChange = (typeId) => {
    if (typeId) {
      const type = types.find((t) => t.id === parseInt(typeId));
      const sc = type ? subCategories.find((s) => s.id === type.sub_category_id) : null;
      setSelectedSubCategoryId(type?.sub_category_id ?? selectedSubCategoryId);
      setSelectedCategoryId(sc?.category_id ?? selectedCategoryId);
    }
    setSelectedTypeId(typeId ? parseInt(typeId) : null);
  };

  // ── Create-modal launchers ────────────────────────────────────────

  const handleCreateCategory = () => {
    setCreateModalState({ isOpen: true, type: 'category', parentName: '', parentId: null });
  };

  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === selectedCategoryId);
    setCreateModalState({
      isOpen: true,
      type: 'sub_category',
      parentName: cat.category,
      parentId: cat.id,
    });
  };

  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === selectedSubCategoryId);
    setCreateModalState({
      isOpen: true,
      type: 'type',
      parentName: sc.sub_category,
      parentId: sc.id,
    });
  };

  /**
   * Callback from the nested create modal; delegates to the appropriate
   * `onXxxCreated` prop and updates local selection.
   */
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
      logger.error('Error creating item:', err);
      throw err;
    }
  };

  const handleCloseCreateModal = () => {
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
  };

  // ── Save / close ──────────────────────────────────────────────────

  /**
   * Invoke the parent's `onSave` callback. Errors are toasted by the
   * parent; we just release the spinner.
   */
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

  /** Reset local state and invoke `onClose`. */
  const handleClose = () => {
    if (saving) return;
    setSelectedPartyId(null);
    setSelectedCategoryId(null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
    onClose();
  };

  /** Close when clicking the overlay backdrop. */
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  if (!isOpen) return null;

  /** Enable save only when a different type is selected. */
  const isChanged = selectedTypeId !== null && selectedParty?.type_id !== selectedTypeId;
  const canSave = isChanged && !saving;

  /**
   * Custom label renderer: prepend ⚠ for uncategorized parties.
   * @param {Object} p - Party object.
   * @returns {string}
   */
  const partyLabel = (p) => (p.type_id === unknownTypeId ? `⚠ ${p.name}` : p.name);

  return (
    <>
      <div className="modal-overlay" onClick={handleBackdropClick}>
        <div className="modal-content remap-modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-header">
            <h2>Remap Party</h2>
            <button
              className="modal-close-btn"
              onClick={handleClose}
              disabled={saving}
              aria-label="Close modal"
            >
              ×
            </button>
          </div>

          <div className="bulk-edit-form">
            {/* Party selector */}
            <div className="form-section">
              <h3>Party</h3>
              <p className="form-hint">
                Select the party whose category mapping you want to change. Uncategorised parties
                are marked with ⚠.
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

            {/* Destination hierarchy (shown once a party is selected) */}
            {selectedPartyId && (
              <div className="form-section">
                <h3>New Category</h3>
                <p className="form-hint">
                  Select at any level — parent levels will be set automatically. Lower levels will
                  be cleared when you change a higher level.
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
            <button className="cancel-button" onClick={handleClose} disabled={saving} type="button">
              Cancel
            </button>
            <button className="save-button" onClick={handleSave} disabled={!canSave} type="button">
              {saving ? 'Remapping...' : 'Remap Party'}
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