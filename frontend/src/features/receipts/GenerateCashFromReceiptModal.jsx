/**
 * @file GenerateCashFromReceiptModal.jsx
 * Modal for creating a Cash-account transaction from a receipt.
 *
 * Shown from {@link ProcessReceipts} as the third disposition option
 * alongside "Save" and "Link to existing transaction". Used when the
 * purchase was paid for in cash so there is no bank transaction to
 * link to.
 *
 * Reuses the taxonomy cascade machinery from the categorization
 * feature (DropdownWithCreate + CreateCategoryModal) so the user can
 * drill Category → Sub-category → Type → Party and create missing
 * nodes inline.
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from '@/features/transactions/CreateCategoryModal';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('GenerateCashFromReceiptModal');

/**
 * @component
 * @param {Object} props
 *
 * @param {boolean} props.isOpen - Visibility flag.
 * @param {() => void} props.onClose
 * @param {(opts: {
 *   partyId: number,
 *   isWithdrawal: boolean,
 *   isCredit: boolean,
 *   isKids: boolean,
 *   isOneOff: boolean,
 * }) => Promise<void>} props.onConfirm
 *        Async callback that performs the generation. Should throw
 *        on failure; the parent handles toasting.
 *
 * @param {{vendor:string, date:string, amount:string}} props.receiptData
 *        The (possibly edited) OCR fields for display.
 *
 * @param {?number} props.suggestedPartyId
 *        Party id returned by `/parties/match`, or null. When set the
 *        cascade is pre-filled so the user can accept with one click.
 *
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {Array<Object>} props.parties
 *
 * @param {(name:string, desc?:string)=>Promise<Object>} props.onCategoryCreated
 * @param {(name:string, categoryId:number, desc?:string)=>Promise<Object>} props.onSubCategoryCreated
 * @param {(name:string, subCategoryId:number, desc?:string)=>Promise<Object>} props.onTypeCreated
 * @param {(name:string, typeId:number, desc?:string)=>Promise<Object>} props.onPartyCreated
 *
 * @returns {JSX.Element|null}
 */
export default function GenerateCashFromReceiptModal({
  isOpen,
  onClose,
  onConfirm,
  receiptData,
  suggestedPartyId,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  // ── Local form state ──────────────────────────────────────────────
  const [isWithdrawal, setIsWithdrawal] = useState(true);
  const [isCredit, setIsCredit] = useState(false);
  const [isKids, setIsKids] = useState(false);
  const [isOneOff, setIsOneOff] = useState(false);

  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [selectedPartyId, setSelectedPartyId] = useState(null);

  const [saving, setSaving] = useState(false);

  /** State for the nested create-taxonomy modal. */
  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null,
  });

  /**
   * Reset the form each time the modal opens.
   * If a suggested party is supplied, walk up the hierarchy to
   * pre-fill every level so the user can accept with one click.
   *
   * Runs once per open — subsequent changes to `parties` / `types` /
   * `subCategories` (e.g. after creating a new item inline) do not
   * re-trigger the reset.
   */
  useEffect(() => {
    if (!isOpen) return;

    setIsWithdrawal(true);
    setIsCredit(false);
    setSaving(false);
    setIsKids(false);
    setIsOneOff(false);

    if (suggestedPartyId) {
      const party = parties.find((p) => p.id === suggestedPartyId);
      const type  = party ? types.find((t) => t.id === party.type_id) : null;
      const sub   = type  ? subCategories.find((s) => s.id === type.sub_category_id) : null;

      setSelectedPartyId(party?.id ?? null);
      setSelectedTypeId(type?.id ?? null);
      setSelectedSubCategoryId(sub?.id ?? null);
      setSelectedCategoryId(sub?.category_id ?? null);
    } else {
      setSelectedPartyId(null);
      setSelectedTypeId(null);
      setSelectedSubCategoryId(null);
      setSelectedCategoryId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  // ── Derived / filtered option lists ──────────────────────────────

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories],
  );

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

  const filteredParties = useMemo(() => {
    if (!selectedTypeId) return [];
    return [...parties]
      .filter((p) => p.type_id === selectedTypeId)
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [parties, selectedTypeId]);

  // ── Cascade change handlers (clear children on parent change) ───

  const handleCategoryChange = (id) => {
    setSelectedCategoryId(id ? parseInt(id) : null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
    setSelectedPartyId(null);
  };

  const handleSubCategoryChange = (id) => {
    setSelectedSubCategoryId(id ? parseInt(id) : null);
    setSelectedTypeId(null);
    setSelectedPartyId(null);
  };

  const handleTypeChange = (id) => {
    setSelectedTypeId(id ? parseInt(id) : null);
    setSelectedPartyId(null);
  };

  const handlePartyChange = (id) => {
    setSelectedPartyId(id ? parseInt(id) : null);
  };

  // ── Nested create-modal launchers ────────────────────────────────

  const openCreateModal = (type, parentName, parentId) =>
    setCreateModalState({ isOpen: true, type, parentName, parentId });

  const handleCreateCategory = () => openCreateModal('category', '', null);
  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === selectedCategoryId);
    openCreateModal('sub_category', cat.category, cat.id);
  };
  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === selectedSubCategoryId);
    openCreateModal('type', sc.sub_category, sc.id);
  };
  const handleCreateParty = () => {
    const t = types.find((x) => x.id === selectedTypeId);
    openCreateModal('party', t.type, t.id);
  };

  /**
   * Callback from the nested create modal; delegates to the
   * appropriate `onXxxCreated` prop and updates local selection.
   */
  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
    try {
      let created;
      switch (type) {
        case 'category':
          created = await onCategoryCreated(name, description);
          if (created?.id) handleCategoryChange(created.id);
          break;
        case 'sub_category':
          created = await onSubCategoryCreated(name, parentId, description);
          if (created?.id) handleSubCategoryChange(created.id);
          break;
        case 'type':
          created = await onTypeCreated(name, parentId, description);
          if (created?.id) handleTypeChange(created.id);
          break;
        case 'party':
          created = await onPartyCreated(name, parentId, description);
          if (created?.id) handlePartyChange(created.id);
          break;
      }
      setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });
      return created;
    } catch (err) {
      logger.error('Error creating taxonomy item:', err);
      throw err;
    }
  };

  const closeCreateModal = () =>
    setCreateModalState({ isOpen: false, type: null, parentName: '', parentId: null });

  // ── Save / close ──────────────────────────────────────────────────

  const handleConfirm = async () => {
    if (!selectedPartyId) return;
    setSaving(true);
    try {
      await onConfirm({
        partyId: selectedPartyId,
        isWithdrawal,
        isCredit,
        isKids,
        isOneOff,
      });
      // Parent closes on success.
    } catch {
      setSaving(false);
    }
  };

  const handleClose = () => {
    if (saving) return;
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  if (!isOpen) return null;

  const canSave = !!selectedPartyId && !saving;
  const amountNum = parseFloat(receiptData.amount);
  const amountDisplay = Number.isFinite(amountNum) ? amountNum.toFixed(2) : '—';

  return (
    <>
      <div className="modal-overlay" onClick={handleBackdropClick}>
        <div
          className="modal-content generate-cash-modal"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            <h2>Generate Cash Transaction</h2>
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
            {/* ── Summary ── */}
            <div className="form-section">
              <h3>Receipt</h3>
              <p className="form-hint">
                A new transaction will be created on the <strong>Cash</strong>{' '}
                account using these details.
              </p>
              <div className="current-mapping">
                <span className="mapping-label">Vendor:</span>
                <span className="mapping-path">{receiptData.vendor || '—'}</span>
              </div>
              <div className="current-mapping">
                <span className="mapping-label">Date:</span>
                <span className="mapping-path">{receiptData.date || '—'}</span>
              </div>
              <div className="current-mapping">
                <span className="mapping-label">Amount:</span>
                <span className="mapping-path">{amountDisplay}</span>
              </div>
            </div>

            {/* ── Direction + income flag ── */}
            <div className="form-section">
              <h3>Transaction</h3>
              <div className="form-field">
                <label>Direction</label>
                <div className="radio-row">
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="cash-direction"
                      checked={isWithdrawal}
                      onChange={() => setIsWithdrawal(true)}
                      disabled={saving}
                    />
                    Withdrawal (cash out)
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="cash-direction"
                      checked={!isWithdrawal}
                      onChange={() => setIsWithdrawal(false)}
                      disabled={saving}
                    />
                    Lodgement (cash in)
                  </label>
                </div>
              </div>
              <div className="form-field">
                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={isCredit}
                    onChange={(e) => setIsCredit(e.target.checked)}
                    disabled={saving}
                  />
                  Mark as income
                </label>
              </div>
              <div className="form-field">
                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={isKids}
                    onChange={(e) => setIsKids(e.target.checked)}
                    disabled={saving}
                  />
                  Kids
                </label>
              </div>
              <div className="form-field">
                <label className="checkbox-option">
                  <input
                    type="checkbox"
                    checked={isOneOff}
                    onChange={(e) => setIsOneOff(e.target.checked)}
                    disabled={saving}
                  />
                  One-off
                </label>
              </div>
            </div>

            {/* ── Party cascade ── */}
            <div className="form-section">
              <h3>Party</h3>
              <p className="form-hint">
                {suggestedPartyId
                  ? 'A party has been suggested from the vendor name. Change it if needed.'
                  : 'Select the party for this transaction. You can create a new one at any level.'}
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
                  emptyLabel={
                    selectedCategoryId ? 'Select sub-category...' : 'Select a category first'
                  }
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
                  emptyLabel={
                    selectedSubCategoryId ? 'Select type...' : 'Select a sub-category first'
                  }
                  onCreateNew={selectedSubCategoryId ? handleCreateType : null}
                  createLabel="➕ Create New Type..."
                  disabled={saving || !selectedSubCategoryId}
                />
              </div>

              <div className="form-field">
                <label>Party</label>
                <DropdownWithCreate
                  value={selectedPartyId}
                  onChange={handlePartyChange}
                  options={filteredParties}
                  valueKey="id"
                  labelKey="name"
                  includeEmpty
                  emptyLabel={selectedTypeId ? 'Select party...' : 'Select a type first'}
                  onCreateNew={selectedTypeId ? handleCreateParty : null}
                  createLabel="➕ Create New Party..."
                  disabled={saving || !selectedTypeId}
                />
              </div>
            </div>
          </div>

          <div className="modal-actions">
            <button
              className="cancel-button"
              onClick={handleClose}
              disabled={saving}
              type="button"
            >
              Cancel
            </button>
            <button
              className="save-button"
              onClick={handleConfirm}
              disabled={!canSave}
              type="button"
            >
              {saving ? 'Generating…' : 'Generate Transaction'}
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