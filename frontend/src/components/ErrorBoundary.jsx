/**
 * @file ErrorBoundary.jsx
 * Top-level React error boundary.
 *
 * Catches render-time exceptions in the descendant tree, logs them via
 * the app logger, and swaps in a friendly fallback UI instead of a blank
 * screen. Note: error boundaries do **not** catch errors in event
 * handlers, async code, or outside React's render lifecycle — those
 * should be surfaced via {@link module:ToastContext}.
 */

import { Component } from 'react';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const log = createLogger('ErrorBoundary');

/**
 * React error boundary component.
 *
 * Wrap around any subtree (typically the whole app, just inside the
 * providers) to prevent an uncaught render error from unmounting the
 * entire UI.
 *
 * The fallback offers a "Try again" button that clears the error state
 * and re-renders `children`; this recovers from transient errors but will
 * immediately re-trip if the underlying cause persists.
 *
 * @class
 *
 * @example
 * <ToastProvider>
 *   <ErrorBoundary>
 *     <App />
 *   </ErrorBoundary>
 * </ToastProvider>
 */
export class ErrorBoundary extends Component {
  /** @type {{hasError: boolean}} */
  state = { hasError: false };

  /**
   * React lifecycle: map a thrown error to the next state.
   * Called during the render phase, so no side effects here — we just
   * flip `hasError` so the next render shows the fallback.
   *
   * @returns {{hasError: true}}
   */
  static getDerivedStateFromError() {
    return { hasError: true };
  }

  /**
   * React lifecycle: invoked after an error has been thrown by a
   * descendant. Used purely for side effects (logging / telemetry).
   *
   * @param {Error} error - The error that was thrown.
   * @param {React.ErrorInfo} info - React-provided info including `componentStack`.
   */
  componentDidCatch(error, info) {
    log.error('Unhandled error', error, info.componentStack);
  }

  /**
   * Render the fallback UI when in an error state, otherwise render
   * children unchanged.
   *
   * @returns {React.ReactNode}
   */
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2>Something went wrong</h2>
          <p>Try refreshing the page. If the problem persists, contact support.</p>
          <button onClick={() => this.setState({ hasError: false })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}