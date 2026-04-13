/**
 * @file Button.jsx
 * App-standard button with primary / secondary / danger variants and a
 * built-in loading state.
 */

import './Button.css';

/**
 * @component
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @param {() => void} [props.onClick]
 * @param {'primary'|'secondary'|'danger'|'ghost'} [props.variant='primary']
 * @param {boolean} [props.disabled=false]
 * @param {boolean} [props.loading=false] - Shows a spinner and disables the button.
 * @param {'button'|'submit'|'reset'} [props.type='button']
 */
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
      className={`btn btn--${variant} ${loading ? 'btn--loading' : ''}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading && <span className="btn__spinner" aria-hidden="true" />}
      <span className="btn__label">{children}</span>
    </button>
  );
}