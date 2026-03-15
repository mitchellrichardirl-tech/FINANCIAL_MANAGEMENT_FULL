import { createPortal } from 'react-dom';
import { useState, useEffect } from 'react';
import { ErrorCode } from '@/lib/apiErrors';
import './CreateCategoryModal.css';
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

// Error codes that relate to the name input specifically.
// These get attached to the field rather than shown as a general banner.
const NAME_FIELD_CODES = new Set([
  ErrorCode.DUPLICATE_NAME,
  ErrorCode.REQUIRED_FIELD,
]);

export default function CreateCategoryModal({
  isOpen,
  onClose,
  onSave,
  type,
  parentName,
  parentId,
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // General error (shown in banner at top of form)
  const [error, setError] = useState(null);
  // Field-specific error (shown inline under the name input)
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
      // Parent closes modal on success
    } catch (err) {
      logger.error('Error creating item:', err);

      // Prefer the pre-formatted userMessage from ApiError
      const message = err.userMessage || err.message || 'Failed to create item';

      // Route the error to the right place:
      // - DUPLICATE_NAME, REQUIRED_FIELD on `name` → inline under the input
      // - err.field === 'name' (or the entity's name column) → inline
      // - Everything else → general banner
      const isNameField =
        NAME_FIELD_CODES.has(err.code) ||
        err.field === 'name' ||
        err.field === type ||          // backend sends field='category', 'type', etc.
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
    // Clear field error as soon as user starts typing
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
            <button
              type="button"
              className="btn-secondary"
              onClick={handleClose}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
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