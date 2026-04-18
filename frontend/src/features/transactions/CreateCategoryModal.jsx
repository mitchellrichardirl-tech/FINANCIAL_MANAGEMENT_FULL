/**
 * @file CreateCategoryModal.jsx
 * Generic modal for creating a new taxonomy item (category, sub-category,
 * type, or party).
 *
 * Rendered via `createPortal` directly into `document.body` so it
 * overlays correctly regardless of where the opener lives in the tree.
 *
 * Distinguishes **field-level errors** (duplicate name, required field)
 * — shown inline under the input — from **general errors** (server
 * failure) — shown in a banner.
 */

import { createPortal } from 'react-dom';
import { useState, useEffect } from 'react';
import { ErrorCode } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CreateCategoryModal');

/**
 * UI copy for each taxonomy level.
 */
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

/**
 * Modal for creating a category, sub-category, type, or party.
 *
 * @component
 */
export default function CreateCategoryModal({ isOpen, onClose, onSave, type, parentName, parentId }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [nameError, setNameError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
      setError(null);
      setNameError(null);
    }
  }, [isOpen, type]);

  const config = TYPE_CONFIG[type] || TYPE_CONFIG.category;

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!name.trim()) {
      setNameError('Name is required');
      return;
    }

    setIsSaving(true);
    setError(null);
    setNameError(null);

    try {
      await onSave(name.trim(), parentId, description.trim());
    } catch (err) {
      logger.error('Error creating item:', err);

      const message = err.userMessage || err.message || 'Failed to create item';

      const isNameField =
        NAME_FIELD_CODES.has(err.code) ||
        err.field === 'name' ||
        err.field === type ||
        err.field === 'sub_category';

      if (isNameField) {
        setNameError(message);
      } else {
        setError(message);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleNameChange = (e) => {
    setName(e.target.value);
    if (nameError) setNameError(null);
  };

  const handleClose = () => {
    if (!isSaving) onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSaving) onClose();
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1000]"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-[8px] shadow-[0_4px_20px_rgba(0,0,0,0.2)] w-full max-w-[450px] max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex justify-between items-center py-[16px] px-[20px] border-b border-[#eee]">
          <h2 className="m-0 text-[18px] font-semibold text-text-dark">{config.title}</h2>
          <button
            className="bg-none border-none text-[24px] text-text-muted cursor-pointer p-0 leading-[1] transition-colors duration-200 hover:not-disabled:text-text-dark disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleClose}
            disabled={isSaving}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="p-[20px] overflow-y-auto">
            {error && (
              <div className="bg-[#ffebee] text-[#c62828] py-[10px] px-[12px] rounded-[4px] mb-[16px] text-[14px]" role="alert">
                {error}
              </div>
            )}

            {config.parentLabel && parentName && (
              <div className="mb-[16px]">
                <label className="block mb-[6px] font-medium text-[#555] text-[14px]">{config.parentLabel}</label>
                <div className="py-[10px] px-[12px] bg-[#f5f5f5] rounded-[4px] text-text-dark text-[14px]">{parentName}</div>
              </div>
            )}

            <div className={`mb-[16px] ${nameError ? '[&_input]:border-[#dc2626] [&_input]:bg-[#fef2f2] [&_input:focus]:outline-[#dc2626]' : ''}`}>
              <label htmlFor="item-name" className="block mb-[6px] font-medium text-[#555] text-[14px]">{config.nameLabel} *</label>
              <input
                id="item-name"
                type="text"
                value={name}
                onChange={handleNameChange}
                placeholder={config.namePlaceholder}
                disabled={isSaving}
                autoFocus
                aria-invalid={!!nameError}
                aria-describedby={nameError ? 'item-name-error' : undefined}
                className="w-full py-[10px] px-[12px] border border-border rounded-[4px] text-[14px] box-border transition-[border-color,box-shadow] duration-200 focus:border-[#2196f3] focus:outline-none focus:shadow-[0_0_0_3px_rgba(33,150,243,0.1)] disabled:bg-[#f5f5f5] disabled:cursor-not-allowed"
              />
              {nameError && (
                <span id="item-name-error" className="block mt-[0.375rem] text-[0.875rem] text-[#dc2626]" role="alert">
                  {nameError}
                </span>
              )}
            </div>

            <div className="mb-0">
              <label htmlFor="item-description" className="block mb-[6px] font-medium text-[#555] text-[14px]">Description (optional)</label>
              <textarea
                id="item-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter description"
                disabled={isSaving}
                rows={3}
                className="w-full py-[10px] px-[12px] border border-border rounded-[4px] text-[14px] box-border transition-[border-color,box-shadow] duration-200 resize-y min-h-[80px] focus:border-[#2196f3] focus:outline-none focus:shadow-[0_0_0_3px_rgba(33,150,243,0.1)] disabled:bg-[#f5f5f5] disabled:cursor-not-allowed"
              />
            </div>
          </div>

          <div className="flex justify-end gap-[12px] py-[16px] px-[20px] border-t border-[#eee] bg-[#fafafa]">
            <button
              type="button"
              className="py-[10px] px-[20px] border-none rounded-[4px] text-[14px] font-medium cursor-pointer transition-[background-color,opacity] duration-200 bg-[#e0e0e0] text-text-dark hover:not-disabled:bg-[#d0d0d0] disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={handleClose}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="py-[10px] px-[20px] border-none rounded-[4px] text-[14px] font-medium cursor-pointer transition-[background-color,opacity] duration-200 bg-[#2196f3] text-white hover:not-disabled:bg-[#1976d2] disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isSaving || !name.trim()}
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
