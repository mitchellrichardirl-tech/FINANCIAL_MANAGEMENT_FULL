/**
 * @file features/statementFormats/constants.js
 * Enums and presets shared across the format editor. Anything that
 * mirrors a backend enum lives here so there's one place to update.
 */

/** How the bank expresses amounts — mirrors the three `AmountConfig` shapes. */
export const AMOUNT_MODE = Object.freeze({
  SPLIT: 'split',         // credit_column + debit_column
  SIGNED: 'signed',       // amount_column, sign = direction
  INDICATOR: 'indicator', // amount_column + credit_indicator_column/value
});

/** Human-readable labels for the radio group. */
export const AMOUNT_MODE_LABELS = Object.freeze({
  [AMOUNT_MODE.SPLIT]: 'Separate credit & debit columns',
  [AMOUNT_MODE.SIGNED]: 'Single signed column (negative = debit)',
  [AMOUNT_MODE.INDICATOR]: 'Amount column + CR/DR indicator',
});

/**
 * Date-format presets offered in the dropdown.
 * `__AUTO__` = let the backend auto-detect (pandas inference + fallbacks).
 * `__CUSTOM__` = reveal a free-text input for a strptime pattern.
 * Using string sentinels for both because Dropdown maps `null` to `''`
 * internally, which collides with a real "empty" option.
 */
export const DATE_FORMAT_PRESETS = Object.freeze([
  { value: '__AUTO__',       label: 'Auto-detect' },
  { value: '%d/%m/%Y',      label: 'DD/MM/YYYY  (31/12/2024)' },
  { value: '%d-%m-%Y',      label: 'DD-MM-YYYY  (31-12-2024)' },
  { value: '%d.%m.%Y',      label: 'DD.MM.YYYY  (31.12.2024)' },
  { value: '%Y-%m-%d',      label: 'YYYY-MM-DD  (2024-12-31)' },
  { value: '%m/%d/%Y',      label: 'MM/DD/YYYY  (12/31/2024)' },
  { value: 'ISO8601',       label: 'ISO 8601  (2024-12-31T10:15:30Z)' },
  { value: '__CUSTOM__',    label: 'Custom strptime…' },
]);

/** Editor step indices — keep in one place so `goToStep(STEP.COLUMNS)` reads cleanly. */
export const STEP = Object.freeze({
  SAMPLE: 0,
  IDENTITY: 1,
  COLUMNS: 2,
  DEFAULTS: 3,
  PREVIEW: 4,
});

export const STEP_LABELS = Object.freeze([
  'Sample file',
  'Name',
  'Columns',
  'Defaults',
  'Preview & save',
]);