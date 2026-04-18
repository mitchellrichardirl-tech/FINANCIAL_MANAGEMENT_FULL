import { useEffect, useMemo, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from './CreateCategoryModal';
import {
  overlayCls, dialogCls, headerCls, headerTitleCls, closeBtnCls,
  bodyCls, sectionCls, sectionTitleCls, formHintCls, formFieldCls,
  formLabelCls, footerCls, cancelBtnCls, saveBtnCls,
} from './_modalShell';
import { createLogger } from '@/lib/logger';

const logger = createLogger('CreateCashTransactionModal');

function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const inputCls =
  'w-full py-2.5 px-3 border border-[#ddd] rounded text-sm box-border focus:border-[#2196f3] focus:outline-none focus:shadow-[0_0_0_3px_rgba(33,150,243,0.1)] disabled:bg-[#f5f5f5] disabled:cursor-not-allowed';

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
  const { register, handleSubmit, control, watch, setValue, reset, formState: { isSubmitting } } = useForm({
    defaultValues: {
      transactionDate: todayIso(),
      description: '',
      amount: '',
      isWithdrawal: true,
      isCredit: false,
      isKids: false,
      isOneOff: false,
      categoryId: null,
      subCategoryId: null,
      typeId: null,
      partyId: null,
    },
  });

  const [createModalState, setCreateModalState] = useState({
    isOpen: false, type: null, parentName: '', parentId: null,
  });

  useEffect(() => {
    if (isOpen) {
      reset({
        transactionDate: todayIso(),
        description: '',
        amount: '',
        isWithdrawal: true,
        isCredit: false,
        isKids: false,
        isOneOff: false,
        categoryId: null,
        subCategoryId: null,
        typeId: null,
        partyId: null,
      });
    }
  }, [isOpen, reset]);

  const selectedCategoryId = watch('categoryId');
  const selectedSubCategoryId = watch('subCategoryId');
  const selectedTypeId = watch('typeId');
  const selectedPartyId = watch('partyId');
  const isWithdrawal = watch('isWithdrawal');
  const description = watch('description');
  const amount = watch('amount');
  const transactionDate = watch('transactionDate');

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
    setValue('categoryId', id ? parseInt(id) : null);
    setValue('subCategoryId', null);
    setValue('typeId', null);
    setValue('partyId', null);
  };
  const handleSubCategoryChange = (id) => {
    setValue('subCategoryId', id ? parseInt(id) : null);
    setValue('typeId', null);
    setValue('partyId', null);
  };
  const handleTypeChange = (id) => {
    setValue('typeId', id ? parseInt(id) : null);
    setValue('partyId', null);
  };
  const handlePartyChange = (id) => {
    setValue('partyId', id ? parseInt(id) : null);
  };

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

  const amountNum = parseFloat(amount);
  const amountValid = Number.isFinite(amountNum) && amountNum > 0;
  const canSave =
    !!selectedPartyId &&
    !!transactionDate &&
    description?.trim() !== '' &&
    amountValid &&
    !isSubmitting;

  const onSubmit = async (data) => {
    try {
      await onConfirm({
        transactionDate: data.transactionDate,
        description: data.description.trim(),
        amount: parseFloat(data.amount),
        partyId: data.partyId,
        isWithdrawal: data.isWithdrawal,
        isCredit: data.isCredit,
        isKids: data.isKids,
        isOneOff: data.isOneOff,
      });
    } catch {
      /* parent already toasted */
    }
  };

  const handleClose = () => { if (!isSubmitting) onClose(); };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSubmitting) handleClose();
  };

  if (!isOpen) return null;

  return (
    <>
      <div onClick={handleBackdropClick} className={overlayCls}>
        <div onClick={(e) => e.stopPropagation()} className={dialogCls}>
          <div className={headerCls}>
            <h2 className={headerTitleCls}>New Cash Transaction</h2>
            <button type="button" onClick={handleClose} disabled={isSubmitting} aria-label="Close modal" className={closeBtnCls}>
              ×
            </button>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col flex-1 overflow-hidden">
            <div className={bodyCls}>
              <div className={sectionCls}>
                <h3 className={sectionTitleCls}>Details</h3>
                <p className={formHintCls}>
                  A new transaction will be created on the <strong>Cash</strong> account using these details.
                </p>

                <div className={formFieldCls}>
                  <label className={formLabelCls}>Date</label>
                  <input type="date" {...register('transactionDate')} disabled={isSubmitting} className={inputCls} />
                </div>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Description</label>
                  <input
                    type="text"
                    {...register('description')}
                    placeholder="e.g. Coffee at Bewley's"
                    disabled={isSubmitting}
                    className={inputCls}
                  />
                </div>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    {...register('amount')}
                    placeholder="0.00"
                    disabled={isSubmitting}
                    className={inputCls}
                  />
                </div>
              </div>

              <div className={sectionCls}>
                <h3 className={sectionTitleCls}>Transaction</h3>
                <div className={formFieldCls}>
                  <label className={formLabelCls}>Direction</label>
                  <div className="flex gap-5 mt-1.5">
                    <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                      <input
                        type="radio"
                        checked={isWithdrawal}
                        onChange={() => setValue('isWithdrawal', true)}
                        disabled={isSubmitting}
                      />
                      Withdrawal (cash out)
                    </label>
                    <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                      <input
                        type="radio"
                        checked={!isWithdrawal}
                        onChange={() => setValue('isWithdrawal', false)}
                        disabled={isSubmitting}
                      />
                      Lodgement (cash in)
                    </label>
                  </div>
                </div>
                {[
                  ['isCredit', 'Mark as income'],
                  ['isKids', 'Kids'],
                  ['isOneOff', 'One-off'],
                ].map(([field, label]) => (
                  <div key={field} className={formFieldCls}>
                    <label className="inline-flex items-center gap-1.5 font-normal cursor-pointer">
                      <input type="checkbox" {...register(field)} disabled={isSubmitting} />
                      {label}
                    </label>
                  </div>
                ))}
              </div>

              <div className={sectionCls}>
                <h3 className={sectionTitleCls}>Party</h3>
                <p className={formHintCls}>
                  Select the party for this transaction. You can create a new one at any level.
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
                      disabled={isSubmitting || disabled}
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className={footerCls}>
              <button type="button" onClick={handleClose} disabled={isSubmitting} className={cancelBtnCls}>
                Cancel
              </button>
              <button type="submit" disabled={!canSave} className={saveBtnCls}>
                {isSubmitting ? 'Creating…' : 'Create Transaction'}
              </button>
            </div>
          </form>
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
