import { Component } from 'react';
import { createLogger } from '@/lib/logger';

const log = createLogger('ErrorBoundary');

export class ErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    log.error('Unhandled error', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-2xl font-semibold mb-2">Something went wrong</h2>
          <p className="mb-4">Try refreshing the page. If the problem persists, contact support.</p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false })}
            className="py-2 px-4 rounded bg-[#007bff] text-white hover:bg-[#0069d9]"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
