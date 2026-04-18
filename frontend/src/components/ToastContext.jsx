import { useToastStore, useToast } from '@/stores/toastStore';

export { useToast };

const TYPE_CLASSES = {
  error:   'bg-[#fef2f2] border-[#fca5a5] text-[#991b1b]',
  success: 'bg-[#f0fdf4] border-[#86efac] text-[#166534]',
  info:    'bg-[#eff6ff] border-[#93c5fd] text-[#1e40af]',
  warning: 'bg-[#fef3c7] border-[#f59e0b] text-black',
};

export function ToastProvider({ children }) {
  const toasts = useToastStore((s) => s.toasts);
  const removeToast = useToastStore((s) => s.removeToast);
  return (
    <>
      {children}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 max-w-md">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex justify-between items-center gap-4 py-3 px-4 rounded-md border shadow-[0_2px_8px_rgba(0,0,0,0.15)] animate-slide-in ${TYPE_CLASSES[t.type] ?? TYPE_CLASSES.error}`}
          >
            <span>{t.message}</span>
            <button
              type="button"
              onClick={() => removeToast(t.id)}
              className="bg-none border-0 cursor-pointer opacity-60 text-base"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
