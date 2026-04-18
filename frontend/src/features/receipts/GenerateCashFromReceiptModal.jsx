import { useState, useEffect, useMemo } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from '@/features/transactions/CreateCategoryModal';
import {
  overlayCls, dialogCls, headerCls, headerTitleCls, closeBtnCls,
  bodyCls, sectionCls, sectionTitleCls, formHintCls, formFieldCls,
  formLabelCls, footerCls, cancelBtnCls, saveBtnCls,
} from '@/features/transactions/_modalShell';
import { createLogger } from '@/lib/logger';

const logger = createLogger('GenerateCashFromReceiptModal');

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
  const [isWithdrawal, setIsWithdrawal] = useState(true);
  const [isCredit, setIsCredit] = useState(false);
  const [isKids, setIsKids] = useState(false);
  const [isOneOff, setIsOneOff] = useState(false);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);
  const [selectedSubCategoryId, setSelectedSubCategoryId] = useState(null);
  const [selectedTypeId, setSelectedTypeId] = useState(null);
  const [selectedPartyId, setSelectedPartyId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [createModalState, setCreateModalState] = useState({
    isOpen: false, type: null, parentName: '', parentId: null,
  });

  useEffect(() => {
    if (!isOpen) return;
    setIsWithdrawal(true); setIsCredit(false); setSaving(false);
    setIsKids(false); setIsOneOff(false);
    if (suggestedPartyId) {
      const party = parties.find((p) => p.id === suggestedPartyId);
      const type  = party ? types.find((t) => t.id === party.type_id) : null;
      const sub   = type ? subCategories.find((s) => s.id === type.sub_category_id) : null;
      setSelectedPartyId(party?.id ?? null);
      setSelectedTypeId(type?.id ?? null);
      setSelectedSubCategoryId(sub?.id ?? null);
      setSelectedCategoryId(sub?.category_id ?? null);
    } else {
      setSelectedPartyId(null); setSelectedTypeId(null);
      setSelectedSubCategoryId(null); setSelectedCategoryId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => a.category.localeCompare(b.category)),
    [categories]
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

  const handleCategoryChange = (id) => {
    setSelectedCategoryId(id ? parseInt(id) : null);
    setSelectedSubCategoryId(null); setSelectedTypeId(null); setSelectedPartyId(null);
  };
  const handleSubCategoryChange = (id) => {
    setSelectedSubCategoryId(id ? parseInt(id) : null);
    setSelectedTypeId(null); setSelectedPartyId(null);
  };
  const handleTypeChange = (id) => {
    setSelectedTypeId(id ? parseInt(id) : null);
    setSelectedPartyId(null);
  };
  const handlePartyChange = (id) =>
    setSelectedPartyId(id ? parseInt(id) : null);

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

  const handleConfirm = async () => {
    if (!selectedPartyId) return;
    setSaving(true);
    try {
      await onConfirm({ partyId: selectedPartyId, isWithdrawal, isCredit, isKids, isOneOff });
    } catch {
      setSaving(false);
    }
  };

  const handleClose = () => { if (!saving) onClose(); };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !saving) handleClose();
  };

  if (!isOpen) return null;

  const canSave = !!selectedPartyId && !saving;
  const amountNum = parseFloat(receiptData.amount);
  const amountDisplay = Number.isFinite(amountNum) ? amountNum.toFixed(2) : '—';

  const mappingCls =
    'flex flex-wrap items-center gap-[0.4rem] py-2 px-3 bg-[#f9fafb] border border-[#e5e7eb] rounded-md text-[0.82rem]';
  const mappingLabelCls = 'text-[#6b7280] font-medium whitespace-nowrap';
  const mappingPathCls = 'text-[#111827] font-normal';

  return (
    <>
      <div onClick={handleBackdropClick} className={overlayCls}>
        <div onClick={(e) => e.stopPropagation()} className={dialogCls}>
          <div className={headerCls}>
            <h2 className={headerTitleCls}>Generate Cash Transaction</h2>
            <button type="button" onClick={handleClose} disabled={saving} aria-label="Close modal" className={closeBtnCls}>
              ×
            </button>
          </div>

          <div className={bodyCls}>
            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Receipt</h3>
              <p className={formHintCls}>
                A new transaction will be created on the <strong>Cash</strong> account using these details.
              </p>
              <div className={mappingCls}>
                <span className={mappingLabelCls}>Vendor:</span>
                <span className={mappingPathCls}>{receiptData.vendor || '—'}</span>
              </div>
              <div className={mappingCls}>
                <span className={mappingLabelCls}>Date:</span>
                <span className={mappingPathCls}>{receiptData.date || '—'}</span>
              </div>
              <div className={mappingCls}>
                <span className={mappingLabelCls}>Amount:</span>
                <span className={mappingPathCls}>{amountDisplay}</span>
              </div>
            </div>

            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Transaction</h3>
              <div className={formFieldCls}>
                <label className={formLabelCls}>Direction</label>
                <div className="flex gap-5 mt-1.5">
                  <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                    <input type="radio" name="cash-direction" checked={isWithdrawal} onChange={() => setIsWithdrawal(true)} disabled={saving} />
                    Withdrawal (cash out)
                  </label>
                  <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                    <input type="radio" name="cash-direction" checked={!isWithdrawal} onChange={() => setIsWithdrawal(false)} disabled={saving} />
                    Lodgement (cash in)
                  </label>
                </div>
              </div>
              {[
                ['isCredit', isCredit, setIsCredit, 'Mark as income'],
                ['isKids', isKids, setIsKids, 'Kids'],
                ['isOneOff', isOneOff, setIsOneOff, 'One-off'],
              ].map(([key, value, setter, label]) => (
                <div key={key} className={formFieldCls}>
                  <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                    <input type="checkbox" checked={value} onChange={(e) => setter(e.target.checked)} disabled={saving} />
                    {label}
                  </label>
                </div>
              ))}
            </div>

            <div className={sectionCls}>
              <h3 className={sectionTitleCls}>Party</h3>
              <p className={formHintCls}>
                {suggestedPartyId
                  ? 'A party has been suggested from the vendor name. Change it if needed.'
                  : 'Select the party for this transaction. You can create a new one at any level.'}
              </p>

              {[
                ['Category', selectedCategoryId, handleCategoryChange, sortedCategories, 'category', 'Select category...', handleCreateCategory, false],
                ['Sub-Category', selectedSubCategoryId, handleSubCategoryChange, filteredSubCategories, 'sub_category', selectedCategoryId ? 'Select sub-category...' : 'Select a category first', selectedCategoryId ? handleCreateSubCategory : null, !selectedCategoryId],
                ['Type', selectedTypeId, handleTypeChange, filteredTypes, 'type', selectedSubCategoryId ? 'Select type...' : 'Select a sub-category first', selectedSubCategoryId ? handleCreateType : null, !selectedSubCategoryId],
                ['Party', selectedPartyId, handlePartyChange, filteredParties, 'name', selectedTypeId ? 'Select party...' : 'Select a type first', selectedTypeId ? handleCreateParty : null, !selectedTypeId],
              ].map(([label, value, onChange, options, labelKey, emptyLabel, onCreate, disabled]) => (
                <div key={label} className={formFieldCls}>
                  <label className={formLabelCls}>{label}</label>
                  <DropdownWithCreate
                    value={value}
                    onChange={onChange}
                    options={options}
                    valueKey="id"
                    labelKey={labelKey}
                    includeEmpty
                    emptyLabel={emptyLabel}
                    onCreateNew={onCreate}
                    createLabel={`➕ Create New ${label}...`}
                    disabled={saving || disabled}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className={footerCls}>
            <button type="button" onClick={handleClose} disabled={saving} className={cancelBtnCls}>Cancel</button>
            <button type="button" onClick={handleConfirm} disabled={!canSave} className={saveBtnCls}>
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
