/**
 * @file CreateCashTransactionModal.jsx
 * Modal for creating a Cash-account transaction from manually entered
 * information — no bank statement row, no receipt.
 *
 * Shown from {@link CategorizeTransactions}. Mirrors
 * {@link GenerateCashFromReceiptModal} but with editable
 * date / description / amount fields in place of the read-only
 * receipt summary.
 */

import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from '@/features/transactions/CreateCategoryModal';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CreateCashTransactionModal');

/** Today's date as a YYYY-MM-DD string (local time). */
function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/**
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(opts: {
 *   transactionDate: string,
 *   description: string,
 *   amount: number,
 *   partyId: number,
 *   isWithdrawal: boolean,
 *   isCredit: boolean,
 *   isKids: boolean,
 *   isOneOff: boolean,
 * }) => Promise<void>} props.onConfirm
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {Array<Object>} props.parties
 * @param {(name:string, desc?:string)=>Promise<Object>} props.onCategoryCreated
 * @param {(name:string, categoryId:number, desc?:string)=>Promise<Object>} props.onSubCategoryCreated
 * @param {(name:string, subCategoryId:number, desc?:string)=>Promise<Object>} props.onTypeCreated
 * @param {(name:string, typeId:number, desc?:string)=>Promise<Object>} props.onPartyCreated
 * @returns {JSX.Element|null}
 */
export default function CreateCashTransactionModal({
  isOpen,
  onClose,
  onConfirm,
  categories,
  subCategories,
  types,
  parties,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  // ── Editable fields ──────────────────────────────────────────────
  const [transactionDate, setTransactionDate] = useState(todayIso());
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');

  // ── Flags ────────────────────────────────────────────────────────
  const [isWithdrawal, setIsWithdrawal] = useState(true);
  const [isCredit, setIsCredit] = useState(false);
  const [isKids, setIsKids] = useState(false);
  const [isOneOff, setIsOneOff] = useState(false);

  // ── Cascade ──────────────────────────────────────────────────────
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [selectedPartyId, setSelectedPartyId] = useState(null);

  const [saving, setSaving] = useState(false);

  const [createModalState, setCreateModalState] = useState({
    isOpen: false,
    type: null,
    parentName: '',
    parentId: null,
  });

  /** Reset every time the modal opens. */
  useEffect(() => {
    if (!isOpen) return;
    setTransactionDate(todayIso());
    setDescription('');
    setAmount('');
    setIsWithdrawal(true);
    setIsCredit(false);
    setIsKids(false);
    setIsOneOff(false);
    setSelectedCategoryId(null);
    setSelectedSubCategoryId(null);
    setSelectedTypeId(null);
    setSelectedPartyId(null);
    setSaving(false);
  }, [isOpen]);

  // ── Option lists (same as the receipt modal) ─────────────────────

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

  // ── Cascade handlers ─────────────────────────────────────────────

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

  // ── Create-modal launchers ───────────────────────────────────────

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

  // ── Validation / save ────────────────────────────────────────────

  const amountNum = parseFloat(amount);
  const amountValid = Number.isFinite(amountNum) && amountNum > 0;

  const canSave =
    !!selectedPartyId &&
    !!transactionDate &&
    description.trim() !== '' &&
    amountValid &&
    !saving;

  const handleConfirm = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await onConfirm({
        transactionDate,
        description: description.trim(),
        amount: amountNum,
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

  return (
    <>
      <div className="modal-overlay" onClick={handleBackdropClick}>
        <div
          className="modal-content generate-cash-modal"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            <h2>New Cash Transaction</h2>
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
            {/* ── Details ── */}
            <div className="form-section">
              <h3>Details</h3>
              <p className="form-hint">
                A new transaction will be created on the <strong>Cash</strong>{' '}
                account using these details.
              </p>

              <div className="form-field">
                <label>Date</label>
                <input
                  type="date"
                  value={transactionDate}
                  onChange={(e) => setTransactionDate(e.target.value)}
                  disabled={saving}
                />
              </div>

              <div className="form-field">
                <label>Description</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Coffee at Bewley's"
                  disabled={saving}
                />
              </div>

              <div className="form-field">
                <label>Amount</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  disabled={saving}
                />
              </div>
            </div>

            {/* ── Flags ── */}
            <div className="form-section">
              <h3>Transaction</h3>
              <div className="form-field">
                <label>Direction</label>
                <div className="radio-row">
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="new-cash-direction"
                      checked={isWithdrawal}
                      onChange={() => setIsWithdrawal(true)}
                      disabled={saving}
                    />
                    Withdrawal (cash out)
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="new-cash-direction"
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
                Select the party for this transaction. You can create a new
                one at any level.
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
              {saving ? 'Creating…' : 'Create Transaction'}
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