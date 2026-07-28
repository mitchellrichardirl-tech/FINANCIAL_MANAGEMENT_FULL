/**
 * @file PartyCascadeFields.jsx
 * Renders the Category → Sub-category → Type → Party dropdown cascade
 * plus the nested create-taxonomy modal.
 *
 * Purely presentational over a {@link useTaxonomyCascade} instance;
 * owns only the nested-modal state.
 */
import { useState } from 'react';
import DropdownWithCreate from '@/components/DropdownWithCreate';
import CreateCategoryModal from '@/features/transactions/CreateCategoryModal';
import * as M from '@/styles/modalClasses';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('PartyCascadeFields');
/** Blank nested-modal state. */
const NO_CREATE_MODAL = {
  isOpen: false,
  type: null,
  parentName: '',
  parentId: null,
};
/**
 * @component
 * @param {Object} props
 * @param {ReturnType<import('./useTaxonomyCascade').useTaxonomyCascade>} props.cascade
 * @param {boolean} [props.disabled]
 * @param {string}  [props.hint] Copy shown under the section heading.
 * @param {Array<Object>} props.categories
 * @param {Array<Object>} props.subCategories
 * @param {Array<Object>} props.types
 * @param {(name:string, desc?:string)=>Promise<Object>} props.onCategoryCreated
 * @param {(name:string, categoryId:number, desc?:string)=>Promise<Object>} props.onSubCategoryCreated
 * @param {(name:string, subCategoryId:number, desc?:string)=>Promise<Object>} props.onTypeCreated
 * @param {(name:string, typeId:number, desc?:string)=>Promise<Object>} props.onPartyCreated
 * @returns {JSX.Element}
 */
export default function PartyCascadeFields({
  cascade,
  disabled = false,
  hint,
  categories,
  subCategories,
  types,
  onCategoryCreated,
  onSubCategoryCreated,
  onTypeCreated,
  onPartyCreated,
}) {
  const [createModalState, setCreateModalState] = useState(NO_CREATE_MODAL);
  const openCreateModal = (type, parentName, parentId) =>
    setCreateModalState({ isOpen: true, type, parentName, parentId });
  const closeCreateModal = () => setCreateModalState(NO_CREATE_MODAL);
  const handleCreateCategory = () => openCreateModal('category', '', null);
  const handleCreateSubCategory = () => {
    const cat = categories.find((c) => c.id === cascade.categoryId);
    if (!cat) return;
    openCreateModal('sub_category', cat.category, cat.id);
  };
  const handleCreateType = () => {
    const sc = subCategories.find((s) => s.id === cascade.subCategoryId);
    if (!sc) return;
    openCreateModal('type', sc.sub_category, sc.id);
  };
  const handleCreateParty = () => {
    const t = types.find((x) => x.id === cascade.typeId);
    if (!t) return;
    openCreateModal('party', t.type, t.id);
  };
  /**
   * Delegates to the appropriate `onXxxCreated` prop, then selects the
   * newly created node so the cascade advances for the user.
   *
   * Rethrows so the nested modal can surface the error inline.
   */
  const handleSaveNewItem = async (name, parentId, description) => {
    const { type } = createModalState;
    try {
      let created;
      switch (type) {
        case 'category':
          created = await onCategoryCreated(name, description);
          if (created?.id) cascade.selectCategory(created.id);
          break;
        case 'sub_category':
          created = await onSubCategoryCreated(name, parentId, description);
          if (created?.id) cascade.selectSubCategory(created.id);
          break;
        case 'type':
          created = await onTypeCreated(name, parentId, description);
          if (created?.id) cascade.selectType(created.id);
          break;
        case 'party':
          created = await onPartyCreated(name, parentId, description);
          if (created?.id) cascade.selectParty(created.id);
          break;
        default:
          break;
      }
      closeCreateModal();
      return created;
    } catch (err) {
      logger.error('Error creating taxonomy item:', err);
      throw err;
    }
  };
  return (
    <div className={M.SECTION}>
      <h3 className={M.SECTION_TITLE}>Party</h3>
      {hint && <p className={M.HINT}>{hint}</p>}
      <div className={M.FORM_GROUP}>
        <label className={M.FORM_LABEL}>Category</label>
        <DropdownWithCreate
          value={cascade.categoryId}
          onChange={cascade.selectCategory}
          options={cascade.sortedCategories}
          valueKey="id"
          labelKey="category"
          includeEmpty
          emptyLabel="Select category..."
          onCreateNew={handleCreateCategory}
          createLabel="➕ Create New Category..."
          disabled={disabled}
        />
      </div>
      <div className={M.FORM_GROUP}>
        <label className={M.FORM_LABEL}>Sub-Category</label>
        <DropdownWithCreate
          value={cascade.subCategoryId}
          onChange={cascade.selectSubCategory}
          options={cascade.filteredSubCategories}
          valueKey="id"
          labelKey="sub_category"
          includeEmpty
          emptyLabel={
            cascade.categoryId
              ? 'Select sub-category...'
              : 'Select a category first'
          }
          onCreateNew={cascade.categoryId ? handleCreateSubCategory : null}
          createLabel="➕ Create New Sub-Category..."
          disabled={disabled || !cascade.categoryId}
        />
      </div>
      <div className={M.FORM_GROUP}>
        <label className={M.FORM_LABEL}>Type</label>
        <DropdownWithCreate
          value={cascade.typeId}
          onChange={cascade.selectType}
          options={cascade.filteredTypes}
          valueKey="id"
          labelKey="type"
          includeEmpty
          emptyLabel={
            cascade.subCategoryId
              ? 'Select type...'
              : 'Select a sub-category first'
          }
          onCreateNew={cascade.subCategoryId ? handleCreateType : null}
          createLabel="➕ Create New Type..."
          disabled={disabled || !cascade.subCategoryId}
        />
      </div>
      <div className={M.FORM_GROUP}>
        <label className={M.FORM_LABEL}>Party</label>
        <DropdownWithCreate
          value={cascade.partyId}
          onChange={cascade.selectParty}
          options={cascade.filteredParties}
          valueKey="id"
          labelKey="name"
          includeEmpty
          emptyLabel={cascade.typeId ? 'Select party...' : 'Select a type first'}
          onCreateNew={cascade.typeId ? handleCreateParty : null}
          createLabel="➕ Create New Party..."
          disabled={disabled || !cascade.typeId}
        />
      </div>
      <CreateCategoryModal
        isOpen={createModalState.isOpen}
        onClose={closeCreateModal}
        onSave={handleSaveNewItem}
        type={createModalState.type}
        parentName={createModalState.parentName}
        parentId={createModalState.parentId}
      />
    </div>
  );
}