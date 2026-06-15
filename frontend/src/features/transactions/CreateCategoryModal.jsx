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
import '@/styles/Modal.css';
import './CreateCategoryModal.css';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('CreateCategoryModal');

/**
 * UI copy for each taxonomy level.
 * @type {Object<string, {title: string, nameLabel: string, namePlaceholder: string, parentLabel: ?string}>}
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

/**
 * Error codes considered "name-field" scoped. These are shown inline
 * under the input rather than in a banner.
 *
 * @type {Set<string>}
 */
const NAME_FIELD_CODES = new Set([ErrorCode.DUPLICATE_NAME, ErrorCode.REQUIRED_FIELD]);

/**
 * Modal for creating a category, sub-category, type, or party.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen - Visibility flag.
 * @param {() => void} props.onClose - Called to close the modal (Cancel, ×, backdrop).
 * @param {(name: string, parentId: ?number, description: string) => Promise<Object>} props.onSave
 *        Async callback that creates the item. Should throw on failure
 *        (the modal catches and displays the error).
 * @param {'category'|'sub_category'|'type'|'party'} props.type
 *        Taxonomy level being created.
 * @param {string} [props.parentName]
 *        Display name of the parent entity (shown read-only).
 * @param {?number} [props.parentId]
 *        ID passed to `onSave` for non-root levels.
 * @returns {JSX.Element|null}
 */
export default function CreateCategoryModal({ isOpen, onClose, onSave, type, parentName, parentId }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  /** General/banner error. */
  const [error, setError] = useState(null);
  /** Inline error under the name input. */
  const [nameError, setNameError] = useState(null);

  // Reset form when opened
  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
      setError(null);
      setNameError(null);
    }
  }, [isOpen, type]);

  const config = TYPE_CONFIG[type] || TYPE_CONFIG.category;

  /**
   * Validate, call `onSave`, and route errors to the appropriate UI
   * location.
   */
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
      // Parent closes modal on success
    } catch (err) {
      logger.error('Error creating item:', err);

      const message = err.userMessage || err.message || 'Failed to create item';

      // Determine whether the error is name-field scoped
      const isNameField =
        NAME_FIELD_CODES.has(err.code) ||
        err.field === 'name' ||
        err.field === type || // backend may send field='category', 'type', …
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

  /** Clear field error as user types. */
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
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="modal-content create-modal">
        <div className="modal-header">
          <h2>{config.title}</h2>
          <button
            className="modal-close"
            onClick={handleClose}
            disabled={isSaving}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="modal-error" role="alert">
                {error}
              </div>
            )}

            {config.parentLabel && parentName && (
              <div className="form-group">
                <label>{config.parentLabel}</label>
                <div className="parent-value">{parentName}</div>
              </div>
            )}

            <div className={`form-group ${nameError ? 'has-error' : ''}`}>
              <label htmlFor="item-name">{config.nameLabel} *</label>
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
              />
              {nameError && (
                <span id="item-name-error" className="field-error" role="alert">
                  {nameError}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="item-description">Description (optional)</label>
              <textarea
                id="item-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter description"
                disabled={isSaving}
                rows={3}
              />
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={handleClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={isSaving || !name.trim()}>
              {isSaving ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}