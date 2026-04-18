const VARIANTS = {
  primary:   'bg-[#007bff] text-white border-transparent hover:enabled:bg-[#0069d9]',
  secondary: 'bg-white text-[#333] border-[#ced4da] hover:enabled:bg-[#f1f3f5]',
  danger:    'bg-[#d9363e] text-white border-transparent hover:enabled:bg-[#c12e35]',
  ghost:     'bg-transparent text-[#007bff] border-transparent hover:enabled:bg-[#f0f8ff]',
};

export default function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  loading = false,
  type = 'button',
  className = '',
}) {
  const variantCls = VARIANTS[variant] ?? VARIANTS.primary;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-2 py-2 px-4 text-sm font-medium border rounded cursor-pointer transition-colors duration-[120ms] disabled:opacity-[0.55] disabled:cursor-not-allowed ${variantCls} ${className}`}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="w-[14px] h-[14px] rounded-full border-2 border-current border-r-transparent animate-btn-spin"
        />
      )}
      <span>{children}</span>
    </button>
  );
}
