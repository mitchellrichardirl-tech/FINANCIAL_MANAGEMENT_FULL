import { create } from 'zustand';

export const useToastStore = create((set, get) => ({
  toasts: [],
  addToast: ({ message, type = 'error', duration = 5000 }) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    if (duration) {
      setTimeout(() => get().removeToast(id), duration);
    }
  },
  removeToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function useToast() {
  const addToast = useToastStore((s) => s.addToast);
  const removeToast = useToastStore((s) => s.removeToast);
  return { addToast, removeToast };
}
