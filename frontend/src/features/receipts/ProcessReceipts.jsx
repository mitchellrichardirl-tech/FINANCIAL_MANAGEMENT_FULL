/**
 * @file ProcessReceipts.jsx
 * Top-level page for the receipt-processing workflow.
 *
 * Three-column layout:
 *  - **Left**  — upload dropzone + receipt list with two tabs:
 *      *Session*  — receipts uploaded in this browser session.
 *      *Unlinked* — server-backed list of receipts awaiting a link
 *                   (pending + saved), from any session.
 *  - **Middle** — image/PDF preview of the selected receipt.
 *  - **Right** — editable fields (vendor / date / amount) and candidate
 *    bank transactions the receipt can be linked to.
 *
 * Receipt status is server-authoritative (see ./model.js):
 *   'pending'  → uploaded, not yet confirmed
 *   'unlinked' → confirmed, no transaction   (editable + linkable)
 *   'linked'   → attached to a transaction   (read-only; can Unlink)
 *
 * Error surfacing:
 *  - Validation errors targeting a known form field → inline under that
 *    input (see {@link FIELD_MAP} / `fieldErrors`).
 *  - Other validation errors → inline banner (`fieldErrors._general`).
 *  - Everything else → toast.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  updateTransaction,
  getCategories,
  getSubCategories,
  getTypes,
  getParties,
  createCategory,
  createSubCategory,
  createType,
  createParty,
} from '@/features/transactions/api';
import {
  confirmReceipt,
  updateReceipt,
  getReceipt,
  cancelReceipt,
  deleteReceipt,
  getCandidateTransactions,
  linkReceipt,
  unlinkReceipt,
  matchParty,
  createCashTransactionFromReceipt,
} from './api';
import {
  RECEIPT_STATUS,
  fromStreamEvent,
  fromServer,
  isEditable,
  isLinked,
  emitReceiptsChanged,
} from './model';
import { useUnlinkedReceipts } from './useUnlinkedReceipts';
import GenerateCashFromReceiptModal from './GenerateCashFromReceiptModal';
import BulkEditModal from '../transactions/BulkEditModal';
import { ErrorCode } from '@/lib/apiErrors';
import { useToast } from '@/components/ToastContext';
import BulkUploadReceipts from './BulkUploadReceipts';
import SelectableReceiptTable from './SelectableReceiptTable';
import UnlinkedReceiptsPanel from './UnlinkedReceiptsPanel';
import ImagePreview from './ImagePreview';
import CandidateTransactions from './CandidateTransactions';
import { createLogger } from '@/lib/logger';

/** @type {import('@/lib/logger').Logger} */
const logger = createLogger('ProcessReceipts');

const FIELD_MAP = {
  vendor: 'vendor',
  date: 'date',
  amount: 'amount',
  original_filename: null,
};

const TAB = { SESSION: 'session', UNLINKED: 'unlinked' };

/* ── Batch summary helpers ─────────────────────────────────────────── */
const MAX_NAMES_IN_TOAST = 3;
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const listFilenames = (items) => {
  const names = items.map((i) => i.filename ?? `file ${i.file_index + 1}`);
  if (names.length <= MAX_NAMES_IN_TOAST) return names.join(', ');
  const shown = names.slice(0, MAX_NAMES_IN_TOAST).join(', ');
  return `${shown} and ${names.length - MAX_NAMES_IN_TOAST} more`;
};
const summariseCounts = ({ succeeded, failed, cancelled }) => {
  const parts = [];
  if (succeeded) parts.push(`${succeeded} processed`);
  if (failed) parts.push(`${failed} failed`);
  if (cancelled) parts.push(`${cancelled} not processed`);
  return parts.length ? parts.join(', ') : 'nothing processed';
};

/* ── Reused class strings ──────────────────────────────────────────── */
const GRID = [
  'grid grid-cols-1 gap-5 flex-1 min-h-0',
  'min-[1200px]:grid-cols-[minmax(450px,500px)_minmax(320px,1fr)_minmax(450px,500px)]',
  'min-[1400px]:grid-cols-[minmax(480px,550px)_minmax(350px,1fr)_minmax(500px,600px)] min-[1400px]:gap-6',
  'min-[1600px]:grid-cols-[minmax(520px,600px)_minmax(400px,1fr)_minmax(600px,700px)] min-[1600px]:gap-8',
  'min-[1920px]:grid-cols-[minmax(550px,650px)_minmax(450px,1fr)_minmax(650px,750px)]',
].join(' ');
const COLUMN = 'flex min-h-0 flex-col gap-6';
const CARD = 'rounded-[10px] bg-white p-5 shadow-[0_2px_8px_rgba(0,0,0,0.08)]';
const SECTION_H3 =
  'mb-4 border-b-2 border-[#f0f0f0] pb-3 text-[1.1rem] font-semibold text-gray-800';
const EMPTY = 'px-4 py-8 text-center text-[0.95rem] text-gray-400';
const INPUT_CLS = [
  'w-full rounded-md border border-gray-300 px-3 py-2.5 text-[0.95rem]',
  'transition-[border-color,box-shadow]',
  'focus:outline-none focus:border-[#007bff] focus:shadow-[0_0_0_3px_rgba(0,123,255,0.15)]',
  'disabled:bg-gray-100 disabled:cursor-not-allowed disabled:text-gray-400',
].join(' ');
const BTN_DIS = 'disabled:cursor-not-allowed disabled:bg-gray-300';
const TAB_BTN = 'cursor-pointer rounded-t-md border-b-2 px-3 py-1.5 text-sm font-semibold transition-colors';
const TAB_ACTIVE = `${TAB_BTN} border-[#007bff] text-[#007bff]`;
const TAB_INACTIVE = `${TAB_BTN} border-transparent text-gray-500 hover:text-gray-800`;
const SCROLLBAR = [
  '[&::-webkit-scrollbar]:w-2',
  '[&::-webkit-scrollbar-track]:rounded [&::-webkit-scrollbar-track]:bg-gray-100',
  '[&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb]:bg-gray-400',
  '[&::-webkit-scrollbar-thumb:hover]:bg-gray-500',
].join(' ');

/** Extract the receipt object from a confirm/update response. */
const receiptFromResponse = (res) => res?.data?.receipt ?? res?.receipt ?? res;

/* ─────────────────────────────────────────────────────────────────── */
function ProcessReceipts() {
  const { addToast } = useToast();

  // ── Receipt lists ────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState(TAB.SESSION);
  const [sessionReceipts, setSessionReceipts] = useState([]);
  const unlinked = useUnlinkedReceipts({ enabled: activeTab === TAB.UNLINKED });

  const [selectedReceiptId, setSelectedReceiptId] = useState(null);
  const hasAutoSelectedRef = useRef(false);

  // The selected row can live in either list (a session upload is also a
  // server 'pending' row). Session wins so in-flight edits are consistent.
  const selectedReceipt =
    sessionReceipts.find((r) => r.receipt_id === selectedReceiptId) ??
    unlinked.rows.find((r) => r.receipt_id === selectedReceiptId) ??
    null;
  const activeList = activeTab === TAB.SESSION ? sessionReceipts : unlinked.rows;

  // ── Busy flags / form ────────────────────────────────────────────
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLinking, setIsLinking] = useState(false);
  const [isHydrating, setIsHydrating] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [editableData, setEditableData] = useState({ vendor: '', date: '', amount: '' });

  const [candidateTransactions, setCandidateTransactions] = useState([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [linkedTransactionId, setLinkedTransactionId] = useState(null);
  const [candidateRefreshKey, setCandidateRefreshKey] = useState(0);

  // ── Taxonomy / modals ────────────────────────────────────────────
  const [categories, setCategories] = useState([]);
  const [subCategories, setSubCategories] = useState([]);
  const [types, setTypes] = useState([]);
  const [parties, setParties] = useState([]);
  const [isCashModalOpen, setIsCashModalOpen] = useState(false);
  const [suggestedPartyId, setSuggestedPartyId] = useState(null);
  const [isGeneratingCash, setIsGeneratingCash] = useState(false);
  const [editTransaction, setEditTransaction] = useState(null);

  const busy = isSaving || isLinking || isHydrating;
  const editable = isEditable(selectedReceipt);

  // ── Shared row mutation: keeps both lists in sync ────────────────
  const patchReceipt = useCallback(
    (id, patch) => {
      const apply = (r) => (typeof patch === 'function' ? patch(r) : { ...r, ...patch });
      setSessionReceipts((prev) => prev.map((r) => (r.receipt_id === id ? apply(r) : r)));
      unlinked.patchRow(id, patch);
    },
    [unlinked.patchRow],
  );

  /** Replace a row's server-derived fields, keeping its `source`. */
  const absorbServerReceipt = useCallback(
    (serverReceipt) => {
      const fresh = fromServer(serverReceipt);
      patchReceipt(fresh.receipt_id, (r) => ({ ...fresh, source: r.source, hydrated: true }));
      emitReceiptsChanged();
    },
    [patchReceipt],
  );

  // ── Effects ──────────────────────────────────────────────────────

  // Populate the form when selection changes; hydrate server rows with detail.
  useEffect(() => {
    if (!selectedReceipt) {
      setEditableData({ vendor: '', date: '', amount: '' });
      setCandidateTransactions([]);
      setLinkedTransactionId(null);
      setFieldErrors({});
      return;
    }
    const ex = selectedReceipt.extracted_data || {};
    setEditableData({ vendor: ex.vendor || '', date: ex.date || '', amount: ex.amount || '' });
    setLinkedTransactionId(selectedReceipt.linked_transaction_id ?? null);
    setFieldErrors({});

    // Summary rows from the list endpoint lack raw_text etc.; fetch detail once.
    if (selectedReceipt.source === 'server' && !selectedReceipt.hydrated) {
      let cancelled = false;
      setIsHydrating(true);
      getReceipt(selectedReceipt.receipt_id)
        .then((detail) => { if (!cancelled) absorbServerReceipt(detail); })
        .catch((err) => {
          logger.error('Failed to hydrate receipt:', err);
          if (err.code === ErrorCode.NOT_FOUND) {
            addToast({ message: 'That receipt no longer exists', type: 'info' });
            unlinked.removeRow(selectedReceipt.receipt_id);
            setSelectedReceiptId(null);
          }
        })
        .finally(() => setIsHydrating(false));
      return () => { cancelled = true; };
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedReceiptId]);

  // Candidate search while editing (debounced). Only for linkable receipts.
  useEffect(() => {
    if (!selectedReceipt || !editable) {
      setCandidateTransactions([]);
      return undefined;
    }
    if (!editableData.date && !editableData.amount) {
      setCandidateTransactions([]);
      return undefined;
    }
    const fetchCandidates = async () => {
      setIsLoadingCandidates(true);
      try {
        const response = await getCandidateTransactions({
          date: editableData.date || null,
          amount: editableData.amount ? parseFloat(editableData.amount) : null,
          vendor: editableData.vendor || null,
        });
        setCandidateTransactions(
          response.success && response.data?.transactions ? response.data.transactions : [],
        );
      } catch (err) {
        logger.error('Failed to fetch candidate transactions:', err);
        setCandidateTransactions([]);
      } finally {
        setIsLoadingCandidates(false);
      }
    };
    const timeoutId = setTimeout(fetchCandidates, 500);
    return () => clearTimeout(timeoutId);
  }, [editableData.date, editableData.amount, editableData.vendor, selectedReceiptId, editable, candidateRefreshKey]);

  useEffect(() => {
    (async () => {
      try {
        const [cats, subs, ts, ps] = await Promise.all([
          getCategories(), getSubCategories(), getTypes(), getParties(),
        ]);
        setCategories(cats); setSubCategories(subs); setTypes(ts); setParties(ps);
      } catch (err) {
        logger.error('Failed to load taxonomy:', err);
      }
    })();
  }, []);

  // ── Error routing ────────────────────────────────────────────────
  const routeError = (err, fallbackMessage) => {
    const message = err.userMessage || err.message || fallbackMessage;
    const mappedField = err.field ? FIELD_MAP[err.field] : null;
    if (mappedField) { setFieldErrors({ [mappedField]: message }); return; }
    if (err.code === ErrorCode.INVALID_VALUE || err.code === ErrorCode.REQUIRED_FIELD) {
      setFieldErrors({ _general: message }); return;
    }
    addToast({ message, type: 'error' });
  };

  // ── Upload callbacks ─────────────────────────────────────────────
  const handleReceiptProcessed = (result) => {
    const row = fromStreamEvent(result);
    setSessionReceipts((prev) => [...prev, row]);
    emitReceiptsChanged();
    if (!hasAutoSelectedRef.current) {
      hasAutoSelectedRef.current = true;
      setActiveTab(TAB.SESSION);
      setSelectedReceiptId(row.receipt_id);
    }
  };

  const handleProcessingStart = () => {
    setIsUploading(true);
    hasAutoSelectedRef.current = false;
  };

  const handleProcessingComplete = ({
    outcome, succeeded = 0, failed = 0, cancelled = 0, failures = [], cancellations = [], error = null,
  }) => {
    setIsUploading(false);
    if (failures.length) logger.warn('Receipts that failed:', failures);
    if (cancellations.length) logger.info('Receipts not processed:', cancellations);
    const counts = summariseCounts({ succeeded, failed, cancelled });
    const failedNames = failed ? ` Failed: ${listFilenames(failures)}.` : '';
    switch (outcome) {
      case 'rejected':
        return;
      case 'completed':
        if (failed === 0) {
          addToast({ message: `${plural(succeeded, 'receipt')} processed`, type: 'success' });
        } else {
          addToast({ message: `${counts}.${failedNames}`, type: succeeded > 0 ? 'info' : 'error', duration: 8000 });
        }
        return;
      case 'aborted':
        addToast({ message: succeeded + failed > 0 ? `Upload cancelled: ${counts}.` : 'Upload cancelled', type: 'info' });
        return;
      case 'fatal':
      case 'disconnected':
        addToast({
          message: `${error ?? 'Processing stopped unexpectedly'}: ${counts}.${failedNames}`,
          type: 'error', duration: 10000,
        });
        return;
      default:
        logger.warn(`Unknown processing outcome: ${outcome}`);
        addToast({ message: counts, type: 'info' });
    }
  };

  // ── Taxonomy create handlers ─────────────────────────────────────
  const makeCreateHandler =
    (label, createFn, refetchFn, setFn, findFn) =>
    async (...args) => {
      const response = await createFn(...args);
      const fresh = await refetchFn();
      setFn(fresh);
      addToast({ message: `${label} "${args[0]}" created`, type: 'success', duration: 2500 });
      return findFn(fresh, ...args) || response;
    };
  const handleCategoryCreated = makeCreateHandler('Category', createCategory, getCategories, setCategories,
    (list, name) => list.find((c) => c.category === name));
  const handleSubCategoryCreated = makeCreateHandler('Sub-category', createSubCategory, getSubCategories, setSubCategories,
    (list, name, catId) => list.find((s) => s.sub_category === name && s.category_id === catId));
  const handleTypeCreated = makeCreateHandler('Type', createType, getTypes, setTypes,
    (list, name, subId) => list.find((t) => t.type === name && t.sub_category_id === subId));
  const handlePartyCreated = makeCreateHandler('Party', createParty, getParties, setParties,
    (list, name, typeId) => list.find((p) => p.name === name && p.type_id === typeId));

  // ── Selection / form ─────────────────────────────────────────────
  const handleSelectReceipt = (receiptId) => setSelectedReceiptId(receiptId);

  const handleInputChange = (field, value) => {
    setEditableData((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((prev) => { const next = { ...prev }; delete next[field]; return next; });
    }
  };

  /** Move to the next actionable receipt in the active list. */
  const selectNextReceipt = () => {
    const list = activeList;
    const currentIndex = list.findIndex((r) => r.receipt_id === selectedReceiptId);
    const actionable = list.filter((r) => isEditable(r) && r.receipt_id !== selectedReceiptId);
    if (actionable.length === 0) return;
    const nextAfter = actionable.find((r) => list.indexOf(r) > currentIndex);
    setSelectedReceiptId(nextAfter?.receipt_id ?? actionable[0].receipt_id);
  };

  // ── Persistence primitives ───────────────────────────────────────
  const buildConfirmPayload = () => ({
    id: selectedReceipt.receipt_id,
    original_filename: selectedReceipt.filename,
    vendor: editableData.vendor,
    amount: editableData.amount ? parseFloat(editableData.amount) : null,
    date: editableData.date || null,
    stored_filename: selectedReceipt.stored_filename ?? undefined,
    confidence: selectedReceipt.extracted_data?.confidence ?? 0,
    selected_method: selectedReceipt.extracted_data?.selected_method || 'manual',
    raw_text: selectedReceipt.extracted_data?.raw_text ?? undefined,
  });

  /**
   * Persist the form. pending → confirm (promotes to 'unlinked');
   * unlinked/linked → plain field update. Returns the server receipt.
   */
  const persistEdits = async () => {
    if (selectedReceipt.status === RECEIPT_STATUS.PENDING) {
      const res = await confirmReceipt(buildConfirmPayload());
      return receiptFromResponse(res);
    }
    return updateReceipt(selectedReceipt.receipt_id, {
      vendor: editableData.vendor,
      amount: editableData.amount ? parseFloat(editableData.amount) : null,
      date: editableData.date || null,
    });
  };

  // ── Actions ──────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsSaving(true);
    try {
      const saved = await persistEdits();
      absorbServerReceipt(saved);
      addToast({ message: 'Receipt saved', type: 'success', duration: 2000 });
      setTimeout(selectNextReceipt, 800);
    } catch (err) {
      logger.error('Failed to save receipt:', err);
      routeError(err, 'Failed to save receipt');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSelectTransaction = async (transaction) => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsLinking(true);
    try {
      await persistEdits();
      const { receipt } = await linkReceipt(selectedReceipt.receipt_id, transaction.id);
      absorbServerReceipt(receipt);
      setLinkedTransactionId(transaction.id);
      addToast({ message: 'Receipt linked to transaction', type: 'success', duration: 2500 });
      setEditTransaction(transaction);
    } catch (err) {
      logger.error('Failed to link receipt to transaction:', err);
      if ((err.code === ErrorCode.NOT_FOUND && err.entity === 'Transaction') || err.code === ErrorCode.CONFLICT) {
        addToast({
          message: err.code === ErrorCode.CONFLICT
            ? `${err.userMessage} Refreshing candidates…`
            : 'That transaction no longer exists. Refreshing candidates…',
          type: 'info',
        });
        setCandidateRefreshKey((k) => k + 1);
      } else {
        routeError(err, 'Failed to link receipt');
      }
    } finally {
      setIsLinking(false);
    }
  };

  const handleUnlink = async () => {
    if (!selectedReceipt || !isLinked(selectedReceipt)) return;
    setIsLinking(true);
    try {
      const { receipt } = await unlinkReceipt(selectedReceipt.receipt_id);
      absorbServerReceipt(receipt);
      setLinkedTransactionId(null);
      setCandidateRefreshKey((k) => k + 1);
      addToast({ message: 'Receipt unlinked', type: 'success', duration: 2000 });
    } catch (err) {
      logger.error('Failed to unlink receipt:', err);
      addToast({ message: err.userMessage || 'Failed to unlink receipt', type: 'error' });
    } finally {
      setIsLinking(false);
    }
  };

  const handleOpenCashModal = async () => {
    setSuggestedPartyId(null);
    try {
      const match = await matchParty(editableData.vendor);
      if (match?.party_id) setSuggestedPartyId(match.party_id);
    } catch (err) {
      logger.warn('Party match failed (non-fatal):', err);
    }
    setIsCashModalOpen(true);
  };

  const handleGenerateCash = async ({ partyId, isWithdrawal, isCredit, isKids, isOneOff }) => {
    if (!selectedReceipt) return;
    setFieldErrors({});
    setIsGeneratingCash(true);
    try {
      await persistEdits();
      const result = await createCashTransactionFromReceipt({
        receiptId: selectedReceipt.receipt_id, partyId, isWithdrawal, isCredit, isKids, isOneOff,
      });
      const txn = result?.data?.transaction ?? result?.transaction;
      // from-receipt links server-side; reflect it locally and refresh detail.
      patchReceipt(selectedReceipt.receipt_id, {
        status: RECEIPT_STATUS.LINKED,
        linked_transaction_id: txn?.id ?? null,
        extracted_data: { ...selectedReceipt.extracted_data, ...editableData },
      });
      emitReceiptsChanged();
      setIsCashModalOpen(false);
      addToast({ message: 'Cash transaction created from receipt', type: 'success', duration: 2500 });
      setTimeout(selectNextReceipt, 1000);
    } catch (err) {
      logger.error('Failed to generate cash transaction:', err);
      routeError(err, 'Failed to generate cash transaction');
      throw err;
    } finally {
      setIsGeneratingCash(false);
    }
  };

  const handleRecategorize = async (updates) => {
    if (!editTransaction) return;
    try {
      await updateTransaction(editTransaction.id, updates);
      addToast({ message: 'Transaction updated', type: 'success', duration: 2000 });
      handleCloseRecategorize();
    } catch (err) {
      logger.error('Failed to update transaction:', err);
      addToast({ message: `Failed to update transaction: ${err.userMessage || err.message}`, type: 'error' });
      throw err;
    }
  };

  const handleCloseRecategorize = () => {
    setEditTransaction(null);
    setTimeout(selectNextReceipt, 300);
  };

  /** Remove a row from whichever lists hold it and pick a neighbour. */
  const dropReceipt = (receiptId) => {
    const list = activeList;
    const currentIndex = list.findIndex((r) => r.receipt_id === receiptId);
    setSessionReceipts((prev) => prev.filter((r) => r.receipt_id !== receiptId));
    unlinked.removeRow(receiptId);
    if (selectedReceiptId === receiptId) {
      const remaining = list.filter((r) => r.receipt_id !== receiptId);
      setSelectedReceiptId(remaining.length ? remaining[Math.min(currentIndex, remaining.length - 1)].receipt_id : null);
    }
  };

  const handleDelete = async () => {
    if (!selectedReceipt) return;
    const linked = isLinked(selectedReceipt);
    if (linked && !window.confirm('This receipt is linked to a transaction. Unlink and delete it?')) return;
    setFieldErrors({});
    setIsSaving(true);
    try {
      if (selectedReceipt.status === RECEIPT_STATUS.PENDING) {
        await cancelReceipt(selectedReceipt.receipt_id);
      } else {
        await deleteReceipt(selectedReceipt.receipt_id, { force: linked });
      }
      dropReceipt(selectedReceipt.receipt_id);
      emitReceiptsChanged();
      addToast({ message: 'Receipt deleted', type: 'success', duration: 1500 });
    } catch (err) {
      logger.error('Failed to delete receipt:', err);
      if (err.code === ErrorCode.NOT_FOUND) {
        addToast({ message: 'Receipt was already deleted', type: 'info' });
        dropReceipt(selectedReceipt.receipt_id);
      } else {
        addToast({ message: err.userMessage || 'Failed to delete receipt', type: 'error' });
      }
    } finally {
      setIsSaving(false);
    }
  };

  /** Session-list only: forget a row locally (the server still has it). */
  const handleRemoveFromList = (receiptId) => {
    const currentIndex = sessionReceipts.findIndex((r) => r.receipt_id === receiptId);
    const remaining = sessionReceipts.filter((r) => r.receipt_id !== receiptId);
    setSessionReceipts(remaining);
    if (selectedReceiptId === receiptId) {
      setSelectedReceiptId(remaining.length ? remaining[Math.min(currentIndex, remaining.length - 1)].receipt_id : null);
    }
  };

  const handleClearSession = () => {
    setSessionReceipts([]);
    if (activeTab === TAB.SESSION) setSelectedReceiptId(null);
    hasAutoSelectedRef.current = false;
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    // Keep the selection if it exists in the target list; else clear.
    const target = tab === TAB.SESSION ? sessionReceipts : unlinked.rows;
    if (!target.some((r) => r.receipt_id === selectedReceiptId)) setSelectedReceiptId(null);
  };

  // ── Derived flags ────────────────────────────────────────────────
  const canSave = editable && editableData.vendor.trim() !== '' && !busy;
  const canDelete = !!selectedReceipt && !busy;
  const canUnlink = isLinked(selectedReceipt) && !busy;
  const canGenerateCash =
    editable && editableData.vendor.trim() !== '' && editableData.date !== '' &&
    editableData.amount !== '' && !busy && !isGeneratingCash;

  const pendingCount = sessionReceipts.filter((r) => r.status === RECEIPT_STATUS.PENDING).length;
  const processedCount = sessionReceipts.length - pendingCount;

  // ── Render ───────────────────────────────────────────────────────
  return (
    <div className="mx-auto flex h-full max-w-[calc(100vw-4rem)] flex-1 flex-col px-8 py-6">
      <div className="shrink-0">
        <h1 className="text-2xl font-bold">Process Receipts</h1>
        <div className="flex items-center gap-4">
          {sessionReceipts.length > 0 && (
            <span className="rounded-full bg-[#f0f0f0] px-4 py-2 text-sm text-gray-500">
              This session: {pendingCount} pending, {processedCount} processed
            </span>
          )}
        </div>
      </div>

      <div className={GRID}>
        {/* ── Left: upload + lists ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[420px] min-[1400px]:min-w-[500px]`}>
          <div className={`${CARD} shrink-0`}>
            <h3 className={SECTION_H3}>Upload Receipts</h3>
            <BulkUploadReceipts
              onReceiptProcessed={handleReceiptProcessed}
              onProcessingStart={handleProcessingStart}
              onProcessingComplete={handleProcessingComplete}
              onError={(err) => addToast({ message: err, type: 'error' })}
              compact={true}
            />
          </div>

          <div className={`${CARD} flex min-h-0 flex-1 flex-col`}>
            <div className="mb-3 flex items-center justify-between border-b border-gray-200">
              <div className="flex gap-1">
                <button
                  className={activeTab === TAB.SESSION ? TAB_ACTIVE : TAB_INACTIVE}
                  onClick={() => handleTabChange(TAB.SESSION)}
                  disabled={busy}
                >
                  This session ({sessionReceipts.length})
                </button>
                <button
                  className={activeTab === TAB.UNLINKED ? TAB_ACTIVE : TAB_INACTIVE}
                  onClick={() => handleTabChange(TAB.UNLINKED)}
                  disabled={busy}
                  title="Receipts saved or left unprocessed in any session"
                >
                  Unlinked{activeTab === TAB.UNLINKED ? ` (${unlinked.total})` : ''}
                </button>
              </div>
              {activeTab === TAB.SESSION && sessionReceipts.length > 0 && (
                <button
                  onClick={handleClearSession}
                  className="mb-1 cursor-pointer rounded border border-gray-400 bg-transparent px-3 py-1 text-[0.75rem] text-gray-600 transition-all hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isUploading || busy}
                  title="Clear this list. Receipts stay on the server and remain available under Unlinked."
                >
                  Clear session
                </button>
              )}
            </div>

            {activeTab === TAB.SESSION ? (
              <div className="min-h-0 flex-1 overflow-y-auto">
                <SelectableReceiptTable
                  receipts={sessionReceipts}
                  selectedReceiptId={selectedReceiptId}
                  onSelectReceipt={handleSelectReceipt}
                  onRemoveReceipt={handleRemoveFromList}
                  disabled={busy}
                />
              </div>
            ) : (
              <UnlinkedReceiptsPanel
                list={unlinked}
                selectedReceiptId={selectedReceiptId}
                onSelectReceipt={handleSelectReceipt}
                disabled={busy}
              />
            )}
          </div>
        </div>

        {/* ── Middle: image preview ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[350px]`}>
          <div className={`${CARD} flex flex-1 flex-col`}>
            <h3 className={SECTION_H3}>Receipt Image</h3>
            {selectedReceipt ? (
              <ImagePreview
                src={`/api/receipts/${selectedReceipt.receipt_id}/image`}
                alt="Receipt image"
                maxHeight="600px"
              />
            ) : (
              <div className="flex flex-1 items-center justify-center min-h-[300px] rounded-lg border-2 border-dashed border-[#e0e0e0] bg-gray-50 text-base text-gray-400">
                {activeList.length === 0 ? 'Upload receipts to get started' : 'Select a receipt to view'}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: details form + candidates ── */}
        <div className={`${COLUMN} min-[1200px]:min-w-[420px] min-[1400px]:min-w-[580px]`}>
          <div className={`${CARD} shrink-0`}>
            <h3 className={SECTION_H3}>Receipt Details</h3>
            {selectedReceipt ? (
              <div className="flex flex-col gap-5">
                {fieldErrors._general && (
                  <div className="rounded border border-danger-border bg-danger-bg px-3 py-2.5 text-sm text-danger-text" role="alert">
                    {fieldErrors._general}
                  </div>
                )}

                {[
                  { id: 'vendor', label: 'Vendor', type: 'text', required: true, placeholder: 'Enter vendor name' },
                  { id: 'date', label: 'Date', type: 'date' },
                  { id: 'amount', label: 'Amount', type: 'number', step: '0.01', placeholder: 'Enter amount' },
                ].map(({ id, label, required, ...inputProps }) => (
                  <div key={id} className="flex flex-col gap-1.5">
                    <label htmlFor={id} className="text-sm font-semibold text-[#444]">
                      {label}: {required && <span className="text-[#dc3545]">*</span>}
                    </label>
                    <input
                      id={id}
                      {...inputProps}
                      value={editableData[id]}
                      onChange={(e) => handleInputChange(id, e.target.value)}
                      required={required}
                      disabled={busy || !editable}
                      aria-invalid={!!fieldErrors[id]}
                      aria-describedby={fieldErrors[id] ? `${id}-error` : undefined}
                      className={INPUT_CLS}
                    />
                    {fieldErrors[id] && (
                      <span id={`${id}-error`} className="text-sm text-red-600">{fieldErrors[id]}</span>
                    )}
                  </div>
                ))}

                <div className="mt-2 flex gap-3">
                  <button
                    onClick={handleSave}
                    className={`flex-1 cursor-pointer rounded-md bg-[#28a745] px-5 py-2.5 text-[0.95rem] font-semibold text-white transition-colors hover:bg-[#218838] ${BTN_DIS}`}
                    disabled={!canSave}
                    title="Save receipt without linking to a transaction"
                  >
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                  <button
                    onClick={handleOpenCashModal}
                    className="cursor-pointer rounded bg-[#43a047] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2e7d32] disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!canGenerateCash}
                    title="Create a Cash-account transaction from this receipt"
                  >
                    Generate Cash
                  </button>
                  {isLinked(selectedReceipt) && (
                    <button
                      onClick={handleUnlink}
                      className="cursor-pointer rounded-md border border-[#007bff] bg-transparent px-5 py-2.5 font-medium text-[#007bff] transition-colors hover:bg-[#e7f1ff] disabled:cursor-not-allowed disabled:opacity-50"
                      disabled={!canUnlink}
                      title="Detach from its transaction; the receipt stays saved"
                    >
                      {isLinking ? 'Unlinking...' : 'Unlink'}
                    </button>
                  )}
                  <button
                    onClick={handleDelete}
                    className={`cursor-pointer rounded-md bg-[#dc3545] px-5 py-2.5 font-medium text-white transition-colors hover:bg-[#c82333] ${BTN_DIS}`}
                    disabled={!canDelete}
                  >
                    {isSaving ? 'Deleting...' : 'Delete'}
                  </button>
                </div>

                {selectedReceipt.status !== RECEIPT_STATUS.PENDING && (
                  <div
                    className={`mt-3 rounded-md p-2.5 text-center text-sm font-semibold ${
                      selectedReceipt.status === RECEIPT_STATUS.UNLINKED
                        ? 'bg-[#fff3cd] text-[#856404]'
                        : 'bg-[#cce5ff] text-[#004085]'
                    }`}
                  >
                    {selectedReceipt.status === RECEIPT_STATUS.UNLINKED && '◐ Saved — not yet linked to a transaction'}
                    {selectedReceipt.status === RECEIPT_STATUS.LINKED &&
                      `🔗 Linked to transaction${selectedReceipt.linked_transaction_id ? ` #${selectedReceipt.linked_transaction_id}` : ''}`}
                  </div>
                )}
              </div>
            ) : (
              <div className={EMPTY}>Select a receipt to edit details</div>
            )}
          </div>

          <div className={`${CARD} flex min-h-0 flex-1 flex-col`}>
            <h3 className={SECTION_H3}>Link to Transaction</h3>
            <div className={`min-h-0 flex-1 overflow-y-auto ${SCROLLBAR}`}>
              {!selectedReceipt ? (
                <div className={EMPTY}>Select a receipt to find matching transactions</div>
              ) : isLinked(selectedReceipt) ? (
                <div className={EMPTY}>This receipt is linked. Use Unlink to choose a different transaction.</div>
              ) : isHydrating || isLoadingCandidates ? (
                <div className="py-6 text-center text-sm text-gray-500">Loading candidate transactions...</div>
              ) : (
                <CandidateTransactions
                  transactions={candidateTransactions}
                  onSelectTransaction={handleSelectTransaction}
                  linkedTransactionId={linkedTransactionId}
                  disabled={busy || !editable}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      <GenerateCashFromReceiptModal
        isOpen={isCashModalOpen}
        onClose={() => setIsCashModalOpen(false)}
        onConfirm={handleGenerateCash}
        receiptData={editableData}
        suggestedPartyId={suggestedPartyId}
        categories={categories}
        subCategories={subCategories}
        types={types}
        parties={parties}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        onPartyCreated={handlePartyCreated}
      />
      <BulkEditModal
        isOpen={editTransaction !== null}
        onClose={handleCloseRecategorize}
        onSave={handleRecategorize}
        transactionCount={1}
        title="Categorise Linked Transaction"
        confirmLabel="Update Transaction"
        emptyLabel="-- Keep Current --"
        initialPartyId={editTransaction?.party_id ?? null}
        initialIsKids={editTransaction?.is_kids ?? null}
        initialIsOneOff={editTransaction?.is_one_off ?? null}
        categories={categories}
        subCategories={subCategories}
        types={types}
        parties={parties}
        onCategoryCreated={handleCategoryCreated}
        onSubCategoryCreated={handleSubCategoryCreated}
        onTypeCreated={handleTypeCreated}
        onPartyCreated={handlePartyCreated}
      />
    </div>
  );
}

export default ProcessReceipts;