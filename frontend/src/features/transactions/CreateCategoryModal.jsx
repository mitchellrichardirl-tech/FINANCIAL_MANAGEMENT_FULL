import { createPortal } from 'react-dom';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { ErrorCode } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

const logger = createLogger('CreateCategoryModal');

const TYPE_CONFIG = {
  category: {
    title: 'Create New Category',
    nameLabel: 'Category Name',
    namePlaceholder: 'Enter category name',
    parentLabel: null,
  },
  sub_category: {
    title: 'Create New Sub-Category',
    nameLabel: 'Sub-Category Name',
    namePlaceholder: 'Enter sub-category name',
    parentLabel: 'Parent Category',
  },
  type: {
    title: 'Create New Type',
    nameLabel: 'Type Name',
    namePlaceholder: 'Enter type name',
    parentLabel: 'Parent Sub-Category',
  },
  party: {
    title: 'Create New Party',
    nameLabel: 'Party Name',
    namePlaceholder: 'Enter party name',
    parentLabel: 'Parent Type',
  },
};

const NAME_FIELD_CODES = new Set([ErrorCode.DUPLICATE_NAME, ErrorCode.REQUIRED_FIELD]);

export default function CreateCategoryModal({ isOpen, onClose, onSave, type, parentName, parentId }) {
  const [generalError, setGeneralError] = useState(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    watch,
    formState: { errors, isSubmitting },
  } = useForm({ defaultValues: { name: '', description: '' } });

  useEffect(() => {
    if (isOpen) {
      reset({ name: '', description: '' });
      setGeneralError(null);
    }
  }, [isOpen, type, reset]);

  const config = TYPE_CONFIG[type] || TYPE_CONFIG.category;
  const isSaving = isSubmitting;
  const nameValue = watch('name');

  const onSubmit = async (data) => {
    setGeneralError(null);
    try {
      await onSave(data.name.trim(), parentId, data.description.trim());
    } catch (err) {
      logger.error('Error creating item:', err);
      const message = err.userMessage || err.message || 'Failed to create item';
      const isNameField =
        NAME_FIELD_CODES.has(err.code) ||
        err.field === 'name' ||
        err.field === type ||
        err.field === 'sub_category';
      if (isNameField) {
        setError('name', { type: 'server', message });
      } else {
        setGeneralError(message);
      }
    }
  };

  const handleClose = () => {
    if (!isSaving) onClose();
  };
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSaving) onClose();
  };

  if (!isOpen) return null;

  const inputBase =
    'w-full py-2.5 px-3 border rounded text-sm box-border transition-[border-color,box-shadow] duration-200 focus:border-[#2196f3] focus:outline-none focus:shadow-[0_0_0_3px_rgba(33,150,243,0.1)] disabled:bg-[#f5f5f5] disabled:cursor-not-allowed';

  return createPortal(
    <div
      onClick={handleBackdropClick}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000]"
    >
      <div className="bg-white rounded-lg shadow-[0_4px_20px_rgba(0,0,0,0.2)] w-full max-w-[450px] max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex justify-between items-center py-4 px-5 border-b border-[#eee]">
          <h2 className="m-0 text-lg font-semibold text-[#333]">{config.title}</h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSaving}
            aria-label="Close"
            className="bg-none border-0 text-2xl text-[#666] cursor-pointer p-0 leading-none transition-colors duration-200 hover:enabled:text-[#333] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="p-5 overflow-y-auto">
            {generalError && (
              <div className="bg-[#ffebee] text-[#c62828] py-2.5 px-3 rounded mb-4 text-sm" role="alert">
                {generalError}
              </div>
            )}

            {config.parentLabel && parentName && (
              <div className="mb-4">
                <label className="block mb-1.5 font-medium text-[#555] text-sm">
                  {config.parentLabel}
                </label>
                <div className="py-2.5 px-3 bg-[#f5f5f5] rounded text-[#333] text-sm">{parentName}</div>
              </div>
            )}

            <div className="mb-4">
              <label htmlFor="item-name" className="block mb-1.5 font-medium text-[#555] text-sm">
                {config.nameLabel} *
              </label>
              <input
                id="item-name"
                type="text"
                autoFocus
                {...register('name', { required: 'Name is required' })}
                placeholder={config.namePlaceholder}
                disabled={isSaving}
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? 'item-name-error' : undefined}
                className={`${inputBase} ${errors.name ? 'border-[#dc2626] bg-[#fef2f2] focus:outline-[#dc2626]' : 'border-[#ddd]'}`}
              />
              {errors.name && (
                <span id="item-name-error" className="block mt-1.5 text-sm text-[#dc2626]" role="alert">
                  {errors.name.message}
                </span>
              )}
            </div>

            <div className="mb-4 last:mb-0">
              <label htmlFor="item-description" className="block mb-1.5 font-medium text-[#555] text-sm">
                Description (optional)
              </label>
              <textarea
                id="item-description"
                {...register('description')}
                placeholder="Enter description"
                disabled={isSaving}
                rows={3}
                className={`${inputBase} border-[#ddd] resize-y min-h-20`}
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 py-4 px-5 border-t border-[#eee] bg-[#fafafa]">
            <button
              type="button"
              onClick={handleClose}
              disabled={isSaving}
              className="py-2.5 px-5 border-0 rounded text-sm font-medium cursor-pointer transition-[background,opacity] duration-200 bg-[#e0e0e0] text-[#333] hover:enabled:bg-[#d0d0d0] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving || !nameValue?.trim()}
              className="py-2.5 px-5 border-0 rounded text-sm font-medium cursor-pointer transition-[background,opacity] duration-200 bg-[#2196f3] text-white hover:enabled:bg-[#1976d2] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
