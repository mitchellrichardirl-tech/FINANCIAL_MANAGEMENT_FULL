import { createPortal } from 'react-dom';
import { useState, useEffect } from 'react';
import './CreateCategoryModal.css';

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
  const [error, setError] = useState(null);

  // Reset form when modal opens/closes or type changes
  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
      setError(null);
    }
  }, [isOpen, type]);

  const config = TYPE_CONFIG[type] || TYPE_CONFIG.category;

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      await onSave(name.trim(), parentId, description.trim());
      // Modal will be closed by parent after successful save
    } catch (err) {
      console.error('Error creating item:', err);
      setError(err.message || 'Failed to create item');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    if (!isSaving) {
      onClose();
    }
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSaving) {
      onClose();
    }
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
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {error && (
              <div className="modal-error">
                {error}
              </div>
            )}

            {config.parentLabel && parentName && (
              <div className="form-group">
                <label>{config.parentLabel}</label>
                <div className="parent-value">{parentName}</div>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="item-name">{config.nameLabel} *</label>
              <input
                id="item-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={config.namePlaceholder}
                disabled={isSaving}
                autoFocus
              />
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