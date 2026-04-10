/**
 * @file features/statementFormats/configModel.js
 * Conversion + validation between the editor's internal draft shape and
 * the backend's `StatementConfig.to_dict()` shape.
 *
 * The draft adds one field the API doesn't have — `amountMode` — because
 * a radio group needs an explicit discriminator, whereas the backend
 * infers the mode from which `AmountConfig` fields are populated.
 * `toApiShape()` strips it back out and nulls the irrelevant fields so
 * we never send a config that's ambiguously half-SPLIT, half-SIGNED.
 */

import { AMOUNT_MODE, STEP } from './constants';

// ---------------------------------------------------------------------
// Draft construction
// ---------------------------------------------------------------------

/**
 * @returns {Object} A blank draft suitable for "create" mode.
 */
export function emptyDraft() {
  return {
    bank_name: '',
    account_type: '',

    date_config: {
      column: '',
      format: null,
      dayfirst: true,
    },

    amountMode: AMOUNT_MODE.SPLIT,
    amount_config: {
      credit_column: '',
      debit_column: '',
      amount_column: '',
      credit_indicator_column: '',
      credit_indicator_value: '',
      signed_amount: false,
      currency_symbols: ['€', '$', '£'],
      decimal_separator: '.',
      thousands_separator: ',',
      debit_is_negative: true,
    },

    description_column: '',
    balance_column: null,
    reference_column: null,

    skip_rows_start: 0,
    skip_rows_end: 0,

    exclude_patterns: [],
    defaults: {},
  };
}

/**
 * Backend config → editor draft. Tolerates missing optional keys
 * (mirrors `StatementConfig.from_dict`'s leniency).
 *
 * @param {Object} config - `StatementConfig.to_dict()` shape.
 * @returns {Object} draft
 */
export function fromApiShape(config) {
  const base = emptyDraft();
  const amt = { ...base.amount_config, ...(config.amount_config || {}) };

  return {
    ...base,
    ...pick(config, [
      'bank_name', 'account_type', 'description_column',
      'balance_column', 'reference_column',
      'skip_rows_start', 'skip_rows_end',
      'exclude_patterns', 'defaults',
    ]),
    date_config: { ...base.date_config, ...(config.date_config || {}) },
    amount_config: amt,
    amountMode: inferAmountMode(amt),
  };
}

/**
 * Editor draft → backend config. Drops `amountMode`, normalizes the
 * amount_config to *only* the fields relevant to the chosen mode, and
 * converts empty strings to `null` for optional columns.
 *
 * @param {Object} draft
 * @returns {Object} `StatementConfig.to_dict()` shape.
 */
export function toApiShape(draft) {
  const {
    amountMode,
    amount_config: amtIn,
    date_config,
    ...rest
  } = draft;

  const common = {
    currency_symbols: amtIn.currency_symbols,
    decimal_separator: amtIn.decimal_separator,
    thousands_separator: amtIn.thousands_separator,
    debit_is_negative: amtIn.debit_is_negative,
  };

  let amount_config;
  switch (amountMode) {
    case AMOUNT_MODE.SPLIT:
      amount_config = {
        ...common,
        credit_column: emptyToNull(amtIn.credit_column),
        debit_column: emptyToNull(amtIn.debit_column),
        amount_column: null,
        credit_indicator_column: null,
        credit_indicator_value: null,
        signed_amount: false,
      };
      break;
    case AMOUNT_MODE.SIGNED:
      amount_config = {
        ...common,
        amount_column: emptyToNull(amtIn.amount_column),
        signed_amount: true,
        credit_column: null,
        debit_column: null,
        credit_indicator_column: null,
        credit_indicator_value: null,
      };
      break;
    case AMOUNT_MODE.INDICATOR:
    default:
      amount_config = {
        ...common,
        amount_column: emptyToNull(amtIn.amount_column),
        credit_indicator_column: emptyToNull(amtIn.credit_indicator_column),
        credit_indicator_value: emptyToNull(amtIn.credit_indicator_value),
        signed_amount: false,
        credit_column: null,
        debit_column: null,
      };
      break;
  }

  return {
    ...pick(rest, [
      'bank_name', 'account_type', 'description_column',
      'skip_rows_start', 'skip_rows_end',
      'exclude_patterns', 'defaults',
    ]),
    balance_column: emptyToNull(rest.balance_column),
    reference_column: emptyToNull(rest.reference_column),
    date_config: {
      column: date_config.column,
      format: emptyToNull(date_config.format),
      dayfirst: date_config.dayfirst,
    },
    amount_config,
  };
}

// ---------------------------------------------------------------------
// Validation — mirrors StatementConfig.__post_init__ so we can disable
// "Next" before a doomed server round-trip.
// ---------------------------------------------------------------------

/**
 * @param {Object} draft
 * @returns {{ ok: boolean, errorsByField: Object<string,string>, errorsByStep: Object<number,string[]> }}
 */
export function validate(draft) {
  /** @type {Object<string,string>} */
  const errorsByField = {};

  if (!draft.bank_name?.trim()) errorsByField.bank_name = 'Bank name is required.';
  if (!draft.account_type?.trim()) errorsByField.account_type = 'Account type is required.';

  if (!draft.date_config.column) errorsByField['date_config.column'] = 'Choose the date column.';
  if (!draft.description_column) errorsByField.description_column = 'Choose the description column.';

  const amt = draft.amount_config;
  switch (draft.amountMode) {
    case AMOUNT_MODE.SPLIT:
      if (!amt.credit_column) errorsByField['amount_config.credit_column'] = 'Required for split mode.';
      if (!amt.debit_column) errorsByField['amount_config.debit_column'] = 'Required for split mode.';
      break;
    case AMOUNT_MODE.SIGNED:
      if (!amt.amount_column) errorsByField['amount_config.amount_column'] = 'Required.';
      break;
    case AMOUNT_MODE.INDICATOR:
      if (!amt.amount_column) errorsByField['amount_config.amount_column'] = 'Required.';
      if (!amt.credit_indicator_column) errorsByField['amount_config.credit_indicator_column'] = 'Required.';
      if (!amt.credit_indicator_value) errorsByField['amount_config.credit_indicator_value'] = 'Required.';
      break;
  }

  if (draft.skip_rows_start < 0) errorsByField.skip_rows_start = 'Must be ≥ 0.';
  if (draft.skip_rows_end < 0) errorsByField.skip_rows_end = 'Must be ≥ 0.';

  const errorsByStep = {
    [STEP.SAMPLE]: pickErrors(errorsByField, ['skip_rows_start', 'skip_rows_end']),
    [STEP.IDENTITY]: pickErrors(errorsByField, ['bank_name', 'account_type']),
    [STEP.COLUMNS]: pickErrors(errorsByField, [
      'date_config.column', 'description_column',
      'amount_config.credit_column', 'amount_config.debit_column',
      'amount_config.amount_column', 'amount_config.credit_indicator_column',
      'amount_config.credit_indicator_value',
    ]),
    [STEP.DEFAULTS]: [],
    [STEP.PREVIEW]: [],
  };

  return {
    ok: Object.keys(errorsByField).length === 0,
    errorsByField,
    errorsByStep,
  };
}

// ---------------------------------------------------------------------
// Error adapters
// ---------------------------------------------------------------------

/**
 * Map an `INVALID_FORMAT` ApiError into the prop shape
 * `ColumnMismatchPanel` expects.
 *
 * @param {Object} err - ApiError with `.message` and `.details`.
 * @returns {import('@/features/statements/ColumnMismatchPanel').ColumnMismatch|null}
 */
export function mismatchFromApiError(err) {
  const d = err?.details;
  if (!d?.missing_columns) return null;
  return {
    message: err.userMessage || err.message,
    formatName: d.statement_format,
    missing: d.missing_columns || [],
    required: d.required_columns || [],
    found: d.found_columns || [],
  };
}

// ---------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------

function inferAmountMode(amt) {
  if (amt.credit_column && amt.debit_column) return AMOUNT_MODE.SPLIT;
  if (amt.signed_amount) return AMOUNT_MODE.SIGNED;
  if (amt.credit_indicator_column) return AMOUNT_MODE.INDICATOR;
  // amount_column alone with no other signal — treat as signed, the
  // safest default (backend's _parse_single_amount with no indicator
  // assumes everything is a credit, which is rarely what the user wants).
  if (amt.amount_column) return AMOUNT_MODE.SIGNED;
  return AMOUNT_MODE.SPLIT;
}

function emptyToNull(v) {
  return v === '' || v === undefined ? null : v;
}

function pick(obj, keys) {
  const out = {};
  for (const k of keys) if (k in obj) out[k] = obj[k];
  return out;
}

function pickErrors(errorsByField, keys) {
  return keys.filter((k) => k in errorsByField).map((k) => errorsByField[k]);
}