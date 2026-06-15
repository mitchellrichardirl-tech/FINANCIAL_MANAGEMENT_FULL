/**
 * @file format.js
 * Display formatters used across the hierarchy feature.
 *
 * If you already have a shared currency/number formatter elsewhere in
 * the app, swap these out for it and delete this file.
 */

const currencyFmt = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  minimumFractionDigits: 2,
});

const countFmt = new Intl.NumberFormat('en-GB');

/**
 * Format a signed monetary value.
 * @param {number} value
 * @returns {string}
 */
export function formatCurrency(value) {
  return currencyFmt.format(value ?? 0);
}

/**
 * Format an integer count with thousands separators.
 * @param {number} value
 * @returns {string}
 */
export function formatCount(value) {
  return countFmt.format(value ?? 0);
}