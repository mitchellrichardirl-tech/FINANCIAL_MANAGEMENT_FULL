import { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import Button from '@/components/Button';
import { useToast } from '@/components/ToastContext';
import { parseApiError, getUserMessage } from '@/lib/apiErrors';
import { createLogger } from '@/lib/logger';
import { useFormat, useFormatSchema } from '../hooks';
import { emptyDraft, fromApiShape } from '../configModel';
import FormatEditor from './FormatEditor';

const logger = createLogger('statementFormats:FormatEditorPage');

export default function FormatEditorPage({ mode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { identifier } = useParams();
  const { addToast } = useToast();

  const cloneFrom = mode === 'create' ? location.state?.cloneFrom : null;

  useEffect(() => {
    if (mode === 'edit' && identifier && !identifier.startsWith('user:')) {
      addToast({
        type: 'info',
        message: 'Built-in formats can\u2019t be edited \u2014 clone one instead.',
      });
      navigate('/statement-formats', { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, identifier]);

  const editIdentifier = mode === 'edit' ? identifier : null;
  const formatQuery = useFormat(editIdentifier || cloneFrom);
  const schemaQuery = useFormatSchema();

  const loading = (editIdentifier || cloneFrom) ? formatQuery.isLoading : false;
  const schemaLoading = schemaQuery.isLoading;
  const error = formatQuery.error || schemaQuery.error;

  let initialDraft = emptyDraft();
  let numericId = null;

  if (mode === 'edit' && formatQuery.data) {
    initialDraft = fromApiShape(formatQuery.data.config);
    numericId = Number(identifier.split(':')[1]);
  } else if (cloneFrom && formatQuery.data) {
    const draft = fromApiShape(formatQuery.data.config);
    draft.account_type = draft.account_type
      ? `${draft.account_type} (Copy)`
      : draft.account_type;
    initialDraft = draft;
  }

  const errorMessage = error
    ? (() => {
        try {
          const parsed = parseApiError(error);
          if (parsed?.then) return null;
          return getUserMessage(parsed, 'Loading format');
        } catch {
          return error.userMessage || error.message || 'Loading format';
        }
      })()
    : null;

  const title =
    mode === 'edit'
      ? 'Edit statement format'
      : cloneFrom
        ? 'New statement format (cloned)'
        : 'New statement format';

  return (
    <div className="w-full max-w-[960px] h-full mx-auto pt-6 px-5 box-border flex flex-col overflow-hidden">
      <header className="shrink-0 mb-5">
        <h1 className="m-0 mb-1 text-2xl font-semibold">{title}</h1>
        <p className="m-0 text-[#6c757d] text-sm">
          Describe how this bank&apos;s export maps to transactions, then test it
          against a sample file.
        </p>
      </header>

      {(loading || schemaLoading) && <p className="text-[#6c757d]">Loading…</p>}

      {error && (
        <div
          role="alert"
          className="py-3.5 px-4 border border-[#f5c2c7] bg-[#f8d7da] rounded text-[#842029] flex justify-between items-center gap-4"
        >
          <p className="m-0">{errorMessage || 'Failed to load.'}</p>
          <Button variant="secondary" onClick={() => navigate('/statement-formats')}>
            Back to formats
          </Button>
        </div>
      )}

      {!loading && !schemaLoading && !error && (
        <FormatEditor
          mode={mode}
          initialDraft={initialDraft}
          numericId={numericId}
          schema={schemaQuery.data}
        />
      )}
    </div>
  );
}
