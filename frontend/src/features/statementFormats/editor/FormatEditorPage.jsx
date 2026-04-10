/**
 * @file editor/FormatEditorPage.jsx
 * Route component for `/statement-formats/new` and
 * `/statement-formats/:identifier`.
 *
 * Responsibilities kept *out* of `<FormatEditor>` so that component can
 * assume its props are ready:
 *   - resolve mode + identifier / cloneFrom
 *   - fetch initial config (edit / clone) and convert to draft shape
 *   - fetch the defaults schema
 *   - guard against editing built-ins
 */

import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import Button from '@/components/Button';
import { useToast } from '@/components/ToastContext';
import { parseApiError, getUserMessage } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';

import { fetchFormat, fetchFormatSchema } from '../api';
import { emptyDraft, fromApiShape } from '../configModel';
import FormatEditor from './FormatEditor';
import './FormatEditorPage.css';

const logger = createLogger('statementFormats:FormatEditorPage');

/**
 * @component
 * @param {Object} props
 * @param {'create'|'edit'} props.mode
 */
export default function FormatEditorPage({ mode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { identifier } = useParams();
  const { addToast } = useToast();

  const cloneFrom = mode === 'create' ? location.state?.cloneFrom : null;

  const [state, setState] = useState({
    loading: true,
    error: null,
    initialDraft: null,
    numericId: null,
    schema: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        // Edit mode: built-ins aren't editable — redirect with a hint.
        if (mode === 'edit' && identifier && !identifier.startsWith('user:')) {
          addToast({
            type: 'info',
            message: 'Built-in formats can’t be edited — clone one instead.',
          });
          navigate('/statement-formats', { replace: true });
          return;
        }

        const schemaPromise = fetchFormatSchema();

        let initialDraft = emptyDraft();
        let numericId = null;

        if (mode === 'edit') {
          const detail = await fetchFormat(identifier);
          initialDraft = fromApiShape(detail.config);
          numericId = Number(identifier.split(':')[1]);
        } else if (cloneFrom) {
          const detail = await fetchFormat(cloneFrom);
          const draft = fromApiShape(detail.config);
          // Nudge the name so saving doesn't immediately 409.
          draft.account_type = draft.account_type
            ? `${draft.account_type} (Copy)`
            : draft.account_type;
          initialDraft = draft;
        }

        const schema = await schemaPromise;

        if (!cancelled) {
          setState({ loading: false, error: null, initialDraft, numericId, schema });
        }
      } catch (err) {
        const parsed = await parseApiError(err);
        logger.error('Editor bootstrap failed', parsed);
        if (!cancelled) {
          setState((s) => ({
            ...s,
            loading: false,
            error: getUserMessage(parsed, 'Loading format'),
          }));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
    // `addToast` / `navigate` are stable; intentionally excluded to avoid re-running.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, identifier, cloneFrom]);

  const title =
    mode === 'edit'
      ? 'Edit statement format'
      : cloneFrom
        ? 'New statement format (cloned)'
        : 'New statement format';

  return (
    <div className="format-editor-page">
      <header className="format-editor-page__header">
        <div>
          <h1>{title}</h1>
          <p className="format-editor-page__sub">
            Describe how this bank&apos;s export maps to transactions, then test it
            against a sample file.
          </p>
        </div>
      </header>

      {state.loading && <p className="format-editor-page__status">Loading…</p>}

      {state.error && (
        <div className="format-editor-page__error" role="alert">
          <p>{state.error}</p>
          <Button variant="secondary" onClick={() => navigate('/statement-formats')}>
            Back to formats
          </Button>
        </div>
      )}

      {!state.loading && !state.error && (
        <FormatEditor
          mode={mode}
          initialDraft={state.initialDraft}
          numericId={state.numericId}
          schema={state.schema}
        />
      )}
    </div>
  );
}