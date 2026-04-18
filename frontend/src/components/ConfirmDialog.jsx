import Button from './Button';

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
    <div
      onClick={onCancel}
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-[1000]"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-md w-[90%] max-w-[440px] py-5 px-6 shadow-[0_10px_40px_rgba(0,0,0,0.2)]"
      >
        <h3
          id="confirm-dialog-title"
          className="m-0 mb-3 text-lg font-semibold"
        >
          {title}
        </h3>
        <div className="text-sm text-[#444] mb-5 [&>p]:m-0 [&>p]:mb-2">
          {children ?? <p>{message}</p>}
        </div>
        <div className="flex justify-end gap-[10px]">
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
