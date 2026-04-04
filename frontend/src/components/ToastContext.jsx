/**
 * @file ToastContext.jsx
 * Global toast notification system.
 *
 * Exposes a {@link ToastProvider} that renders a stack of transient
 * messages in the corner of the viewport, and a {@link useToast} hook
 * that lets any descendant push notifications without prop-drilling.
 *
 * Typical usage is to surface `err.userMessage` from `AppError` /
 * `ApiError` after a failed API call.
 */

import './Toast.css';
import { createContext, useCallback, useContext, useState } from 'react';

/**
 * Visual/semantic variant of a toast. Maps to a `.toast-<type>` CSS class.
 * @typedef {'error'|'success'|'info'|'warning'} ToastType
 */

/**
 * Options accepted by {@link ToastContextValue.addToast}.
 * @typedef {Object} ToastOptions
 * @property {string} message        - Text shown inside the toast.
 * @property {ToastType} [type='error'] - Visual variant.
 * @property {number} [duration=5000]
 *           Milliseconds before auto-dismiss. Pass `0` (or any falsy
 *           value) to make the toast persist until manually closed.
 */

/**
 * Value provided by {@link ToastContext}.
 * @typedef {Object} ToastContextValue
 * @property {(opts: ToastOptions) => void} addToast
 *           Queue a new toast notification.
 * @property {(id: string) => void} removeToast
 *           Dismiss a toast by id (rarely needed by consumers — toasts
 *           auto-dismiss and render their own close button).
 */

/**
 * React context carrying the toast API.
 * `null` when accessed outside a {@link ToastProvider}.
 *
 * @type {React.Context<ToastContextValue|null>}
 */
const ToastContext = createContext(null);

/**
 * Provider that owns toast state and renders the toast stack.
 *
 * Mount once near the root of the app (typically wrapping `<App />`).
 * Descendants call {@link useToast} to push notifications.
 *
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children - Subtree that gains access to the toast API.
 * @returns {JSX.Element}
 *
 * @example
 * // main.jsx
 * <ToastProvider>
 *   <App />
 * </ToastProvider>
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(({ message, type = 'error', duration = 5000 }) => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { id, message, type }]);
    if (duration) setTimeout(() => removeToast(id), duration);
  }, [removeToast]);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <span>{t.message}</span>
            <button onClick={() => removeToast(t.id)}>✕</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/**
 * Hook to access the toast API.
 *
 * Must be called from a component rendered inside {@link ToastProvider};
 * throws otherwise so misconfiguration fails loudly during development.
 *
 * @returns {ToastContextValue} `{ addToast, removeToast }`
 * @throws {Error} If no enclosing `ToastProvider` is found.
 *
 * @example
 * const { addToast } = useToast();
 *
 * try {
 *   await apiCall('/categories', { method: 'POST', body });
 *   addToast({ type: 'success', message: 'Category created.' });
 * } catch (err) {
 *   addToast({ message: err.userMessage });
 * }
 */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}