/**
 * @file ConfirmDialog.jsx
 * Minimal blocking confirmation modal. Controlled via `open`; no portal
 * — relies on fixed positioning, which is fine at this app's scale.
 */

import Button from './Button';
import './ConfirmDialog.css';

/**
 * @component
 * @param {Object} props
 * @param {boolean} props.open
 * @param {string} props.title
 * @param {React.ReactNode} [props.children] - Body content. Supersedes `message` if both given.
 * @param {string} [props.message]           - Plain-text body when you don't need JSX.
 * @param {string} [props.confirmLabel='Confirm']
 * @param {string} [props.cancelLabel='Cancel']
 * @param {'primary'|'danger'} [props.confirmVariant='primary']
 * @param {boolean} [props.confirmDisabled=false]
 * @param {boolean} [props.loading=false]    - Applied to the confirm button.
 * @param {() => void} props.onConfirm
 * @param {() => void} props.onCancel
 */
export default function ConfirmDialog({
  open,
  title,
  children,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  confirmVariant = 'primary',
  confirmDisabled = false,
  loading = false,
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  return (
    <div className="confirm-dialog__backdrop" onClick={onCancel}>
      <div
        className="confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-dialog-title" className="confirm-dialog__title">{title}</h3>
        <div className="confirm-dialog__body">
          {children ?? <p>{message}</p>}
        </div>
        <div className="confirm-dialog__actions">
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={confirmVariant}
            onClick={onConfirm}
            disabled={confirmDisabled}
            loading={loading}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}