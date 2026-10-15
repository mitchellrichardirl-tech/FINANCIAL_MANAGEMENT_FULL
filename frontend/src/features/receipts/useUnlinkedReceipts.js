/**
 * @file useUnlinkedReceipts.js
 * Server-backed list of receipts awaiting a link (pending + unlinked).
 * Owns filters, paging and refresh; exposes patch/remove so the page can
 * keep rows in sync after link/save/delete without a round trip.
 */
import { useCallback, useEffect, useState } from 'react';
import { listReceipts } from './api';
import { fromServer, RECEIPTS_CHANGED_EVENT } from './model';
import { createLogger } from '@/lib/logger';

const logger = createLogger('useUnlinkedReceipts');

export const PAGE_SIZE = 50;

export const DEFAULT_FILTERS = Object.freeze({
  status: 'pending,unlinked',
  q: '',
  date_from: '',
  date_to: '',
  amount_min: '',
  amount_max: '',
});

export function useUnlinkedReceipts({ enabled }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFiltersState] = useState(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setLoading(true);
    setError(null);
    listReceipts({ ...filters, limit: PAGE_SIZE, offset, sort: 'date', direction: 'desc' })
      .then((d) => {
        if (cancelled) return;
        setRows((d.receipts ?? []).map((r) => fromServer(r)));
        setTotal(d.pagination?.total ?? 0);
      })
      .catch((err) => {
        if (cancelled) return;
        logger.error('Failed to list unlinked receipts:', err);
        setError(err.userMessage || 'Failed to load receipts');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [enabled, filters, offset, refreshKey]);

  // Other screens (Transactions page attach) can change counts; refetch if visible.
  useEffect(() => {
    if (!enabled) return undefined;
    const onChange = () => setRefreshKey((k) => k + 1);
    window.addEventListener(RECEIPTS_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(RECEIPTS_CHANGED_EVENT, onChange);
  }, [enabled]);

  const setFilters = useCallback((next) => {
    setOffset(0);
    setFiltersState((prev) => ({ ...prev, ...next }));
  }, []);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  const patchRow = useCallback((id, patch) => {
    setRows((prev) =>
      prev.map((r) =>
        r.receipt_id === id ? (typeof patch === 'function' ? patch(r) : { ...r, ...patch }) : r,
      ),
    );
  }, []);

  const removeRow = useCallback((id) => {
    setRows((prev) => prev.filter((r) => r.receipt_id !== id));
    setTotal((t) => Math.max(0, t - 1));
  }, []);

  return {
    rows, total, loading, error,
    filters, setFilters,
    offset, setOffset, pageSize: PAGE_SIZE,
    refresh, patchRow, removeRow,
  };
}