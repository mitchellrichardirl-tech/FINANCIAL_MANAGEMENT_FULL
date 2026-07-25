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
import * as M from '@/styles/modalClasses';
import { createLogger } from '@/lib/logger';
/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CreateCategoryModal');
/* ── Form field styling ────────────────────────────────────────────── */
const FORM_GROUP = 'mb-4 last:mb-0';
const FORM_LABEL = 'mb-1.5 block text-sm font-medium text-gray-600';
const FIELD =
  'w-full rounded-md border border-gray-300 px-3 py-2 text-sm ' +
  'transition-[border-color,box-shadow] ' +
  'focus:border-blue-600 focus:shadow-[0_0_0_2px_rgba(37,99,235,0.2)] focus:outline-none ' +
  'disabled:cursor-not-allowed disabled:bg-gray-100';
const FIELD_ERR =
  'w-full rounded-md border border-red-600 bg-red-50 px-3 py-2 text-sm ' +
  'transition-[border-color,box-shadow] ' +
  'focus:border-red-600 focus:shadow-[0_0_0_2px_rgba(220,38,38,0.2)] focus:outline-none ' +
  'disabled:cursor-not-allowed disabled:bg-gray-100';
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
 * (full docblock unchanged)
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
    <div className={M.BACKDROP} onClick={handleBackdropClick}>
      <div className={M.PANEL} onClick={(e) => e.stopPropagation()}>
        <div className={M.HEADER}>
          <h2 className={M.TITLE}>{config.title}</h2>
          <button
            className={M.CLOSE_BTN}
            onClick={handleClose}
            disabled={isSaving}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className={M.BODY}>
            {error && (
              <div className={M.ERROR_BANNER} role="alert">
                {error}
              </div>
            )}
            {config.parentLabel && parentName && (
              <div className={FORM_GROUP}>
                <label className={FORM_LABEL}>{config.parentLabel}</label>
                <div className="rounded-md bg-gray-100 px-3 py-2.5 text-sm text-gray-800">
                  {parentName}
                </div>
              </div>
            )}
            <div className={FORM_GROUP}>
              <label htmlFor="item-name" className={FORM_LABEL}>
                {config.nameLabel} *
              </label>
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
                className={nameError ? FIELD_ERR : FIELD}
              />
              {nameError && (
                <span id="item-name-error" className="mt-1 block text-[0.8rem] text-red-600" role="alert">
                  {nameError}
                </span>
              )}
            </div>
            <div className={FORM_GROUP}>
              <label htmlFor="item-description" className={FORM_LABEL}>
                Description (optional)
              </label>
              <textarea
                id="item-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter description"
                disabled={isSaving}
                rows={3}
                className={`${FIELD} min-h-20 resize-y`}
              />
            </div>
          </div>
          <div className={M.FOOTER}>
            <button type="button" className={M.BTN_SECONDARY} onClick={handleClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className={M.BTN_PRIMARY} disabled={isSaving || !name.trim()}>
              {isSaving ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}