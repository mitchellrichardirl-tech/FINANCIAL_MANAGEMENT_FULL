/**
 * @file features/receipts/model.js
 * Normalises the two receipt payload shapes the UI receives into one row.
 *
 *  - Stream event from /receipts/upload-stream:
 *      { receipt_id, status, original_filename, stored_filename,
 *        extracted_data: { vendor, amount, date, confidence } }
 *  - Server row from /receipts, /receipts/<id>, /receipts/<id>/link:
 *      { id, original_filename, vendor, amount, date, confidence,
 *        status, confirmed_at, linked_transaction_id, raw_text?, ... }
 *
 * Status vocabulary (server-authoritative): 'pending' | 'unlinked' | 'linked'.
 */

export const RECEIPT_STATUS = Object.freeze({
  PENDING: 'pending',
  UNLINKED: 'unlinked',
  LINKED: 'linked',
});

/** Statuses in which fields can be edited and a link can be made. */
export const EDITABLE_STATUSES = new Set([RECEIPT_STATUS.PENDING, RECEIPT_STATUS.UNLINKED]);

export const isEditable = (receipt) => !!receipt && EDITABLE_STATUSES.has(receipt.status);
export const isLinked = (receipt) => receipt?.status === RECEIPT_STATUS.LINKED;

const dateOnly = (d) => (d ? String(d).slice(0, 10) : '');

/**
 * @typedef {Object} ReceiptRow
 * @property {number} receipt_id
 * @property {string} filename
 * @property {'pending'|'unlinked'|'linked'} status
 * @property {?number} linked_transaction_id
 * @property {?string} confirmed_at
 * @property {{vendor:string, date:string, amount:string, confidence:?number, raw_text:?string, selected_method:?string}} extracted_data
 * @property {'session'|'server'} source
 * @property {?string} stored_filename
 */

/** Normalise a stream success event. */
export function fromStreamEvent(evt) {
  const ex = evt.extracted_data || {};
  return {
    receipt_id: evt.receipt_id,
    filename: evt.original_filename || evt.identifier || evt.filename || '',
    status: evt.status || RECEIPT_STATUS.PENDING,
    linked_transaction_id: null,
    confirmed_at: null,
    stored_filename: evt.stored_filename ?? null,
    extracted_data: {
      vendor: ex.vendor ?? '',
      date: dateOnly(ex.date),
      amount: ex.amount != null ? String(ex.amount) : '',
      confidence: ex.confidence ?? null,
      raw_text: ex.raw_text ?? null,
      selected_method: ex.selected_method ?? null,
    },
    source: 'session',
  };
}

/** Normalise a server receipt (summary or detail). */
export function fromServer(r, { source = 'server' } = {}) {
  return {
    receipt_id: r.id,
    filename: r.original_filename || '',
    status: r.status || RECEIPT_STATUS.PENDING,
    linked_transaction_id: r.linked_transaction_id ?? null,
    confirmed_at: r.confirmed_at ?? null,
    stored_filename: r.stored_filename ?? null,
    extracted_data: {
      vendor: r.vendor ?? '',
      date: dateOnly(r.date),
      amount: r.amount != null ? String(r.amount) : '',
      confidence: r.confidence ?? null,
      raw_text: r.raw_text ?? null,
      selected_method: r.selected_method ?? null,
    },
    source,
  };
}

/** Merge a fresh server receipt into an existing row, preserving `source`. */
export function mergeServer(row, r) {
  return { ...fromServer(r), source: row?.source ?? 'server' };
}