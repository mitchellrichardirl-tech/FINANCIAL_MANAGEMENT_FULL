/**
 * @file Button.jsx
 * App-standard button with primary / secondary / danger variants and a
 * built-in loading state.
 */

const variantClasses = {
  primary: 'bg-primary text-white hover:enabled:bg-primary-hover',
  secondary: 'bg-white text-[#333] border-border-input hover:enabled:bg-[#f1f3f5]',
  danger: 'bg-danger text-white hover:enabled:bg-danger-hover',
  ghost: 'bg-transparent text-primary border-transparent hover:enabled:bg-[#f0f8ff]',
};

export default function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  loading = false,
  type = 'button',
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border border-transparent rounded cursor-pointer transition-[background-color,border-color] duration-[0.12s] disabled:opacity-55 disabled:cursor-not-allowed ${variantClasses[variant] || ''}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading && <span className="inline-block w-3.5 h-3.5 border-2 border-current border-r-transparent rounded-full animate-spin-fast" aria-hidden="true" />}
      <span>{children}</span>
    </button>
  );
}