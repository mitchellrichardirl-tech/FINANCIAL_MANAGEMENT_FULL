/**
 * @file useStatementFormats.js
 * Plain `useEffect`/`useState` loader for the format list. Returns a
 * `refetch` so callers can refresh after create/update/delete without
 * a global cache.
 */

import { useCallback, useEffect, useState } from 'react';
import { fetchFormats } from './api';
import { createLogger } from '@/lib/logger';

const logger = createLogger('statementFormats:useStatementFormats');

/**
 * @returns {{
 *   formats: import('./api').FormatSummary[],
 *   loading: boolean,
 *   error: Error|null,
 *   refetch: () => Promise<void>,
 * }}
 */
export function useStatementFormats() {
  const [formats, setFormats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFormats();
      setFormats(result);
    } catch (err) {
      logger.error('Failed to load formats', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { formats, loading, error, refetch: load };
}