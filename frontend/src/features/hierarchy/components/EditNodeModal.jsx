/**
 * @file EditNodeModal.jsx
 * Modal for editing the name and description of a hierarchy node.
 *
 * Level-agnostic: works for category, sub_category, type, and party.
 * The API layer maps `{ name, description }` onto the right
 * per-level column names.
 *
 * Does NOT handle re-parenting — use RemapNodeModal for that.
 */

import { createPortal } from 'react-dom';
import { useState, useEffect } from 'react';
import { ErrorCode } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';
import { LEVEL_LABELS } from '../constants';
import '@/styles/Modal.css';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('EditNodeModal');

/** Error codes routed to the inline name-field error slot. */
const NAME_FIELD_CODES = new Set([
  ErrorCode.DUPLICATE_NAME,
  ErrorCode.REQUIRED_FIELD,
]);

/** Backend field names the server may label a name-error with. */
const NAME_FIELD_KEYS = new Set([
  'name', 'category', 'sub_category', 'type',
]);

/**
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {() => void} props.onClose
 * @param {(payload: {name?: string, description?: string|null}) => Promise<void>} props.onSave
 *        Called with only the fields that changed. Should throw on
 *        failure (the modal catches and routes the error to the UI).
 * @param {?{name: string, description: ?string}} props.node
 *        The currently selected node (from `detail.node`).
 * @param {?('category'|'sub_category'|'type'|'party')} props.level
 * @returns {JSX.Element|null}
 */
export default function EditNodeModal({ isOpen, onClose, onSave, node, level }) {

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  /** Banner error (non-field-scoped failures). */
  const [error, setError] = useState(null);
  /** Inline error under the name input. */
  const [nameError, setNameError] = useState(null);

  // Re-seed the form every time the modal opens for a new node.
  useEffect(() => {
    if (isOpen && node) {
      setName(node.name ?? '');
      setDescription(node.description ?? '');
      setError(null);
      setNameError(null);
      setIsSaving(false);
    }
  }, [isOpen, node]);

  if (!isOpen || !node) return null;

  const levelLabel = LEVEL_LABELS[level] || 'Item';

  const trimmedName = name.trim();
  const trimmedDesc = description.trim();
  const currentName = node.name ?? '';
  const currentDesc = node.description ?? '';

  const nameChanged = trimmedName !== currentName;
  const descChanged = trimmedDesc !== currentDesc;
  const hasChanges = nameChanged || descChanged;
  const canSave = hasChanges && trimmedName.length > 0 && !isSaving;

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!trimmedName) {
      setNameError('Name is required');
      return;
    }
    if (!hasChanges) return;

    setIsSaving(true);
    setError(null);
    setNameError(null);

    const payload = {};
    if (nameChanged) payload.name = trimmedName;
    if (descChanged) payload.description = trimmedDesc || null;

    try {
      await onSave(payload);
    } catch (err) {
      logger.error('Error updating node:', err);
      const message = err.userMessage || err.message || 'Failed to update item';
      const isNameField =
        NAME_FIELD_CODES.has(err.code) ||
        NAME_FIELD_KEYS.has(err.field) ||
        err.field === level;
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

  if (!isOpen || !node) return null;

  return createPortal(
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="modal-content max-w-[480px]">
        <div className="modal-header">
          <h2>Edit {levelLabel}</h2>
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

            <div className={`form-group ${nameError ? 'has-error' : ''}`}>
              <label htmlFor="edit-node-name">{levelLabel} Name *</label>
              <input
                id="edit-node-name"
                type="text"
                value={name}
                onChange={handleNameChange}
                disabled={isSaving}
                autoFocus
                aria-invalid={!!nameError}
                aria-describedby={nameError ? 'edit-node-name-error' : undefined}
              />
              {nameError && (
                <span id="edit-node-name-error" className="field-error" role="alert">
                  {nameError}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="edit-node-description">Description</label>
              <textarea
                id="edit-node-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional"
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
              disabled={!canSave}
            >
              {isSaving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}