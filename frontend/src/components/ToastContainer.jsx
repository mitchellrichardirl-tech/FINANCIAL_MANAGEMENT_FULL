import { useToastStore } from '@/stores/toastStore';

const TYPE_STYLES = {
  error: 'bg-toast-error-bg border-toast-error-border text-toast-error-text',
  success: 'bg-toast-success-bg border-toast-success-border text-toast-success-text',
  info: 'bg-toast-info-bg border-toast-info-border text-toast-info-text',
  warning: 'bg-toast-warning-bg border-toast-warning-border text-toast-warning-text',
};

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-[28rem]">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex justify-between items-center gap-4 px-4 py-3 rounded-md border shadow-md animate-slide-in ${TYPE_STYLES[t.type] || TYPE_STYLES.error}`}
        >
          <span>{t.message}</span>
          <button
            onClick={() => removeToast(t.id)}
            className="bg-transparent border-none cursor-pointer opacity-60 text-base p-0"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
