/**
 * @file editor/steps/StepColumns.jsx
 * Step 3 — map source columns to the fields the pipeline needs: date,
 * description, amount(s), and optional extras.
 *
 * This is the most complex step. It's split into three visible sections
 * plus a collapsible "Advanced" block:
 *   1. Date configuration (delegated to DateFormatField)
 *   2. Description column
 *   3. Amount configuration (mode radio + conditional fields)
 *   4. Advanced: optional columns, number formatting, exclude patterns
 */

import Checkbox from '@/components/Checkbox';
import ChipInput from '@/components/ChipInput';
import FormField from '@/components/FormField';
import TextInput from '@/components/TextInput';

import { AMOUNT_MODE } from '../../constants';
import AmountModeRadio from '../fields/AmountModeRadio';
import ColumnSelect from '../fields/ColumnSelect';
import DateFormatField from '../fields/DateFormatField';

import './StepColumns.css';

/**
 * @component
 * @param {{ editor: ReturnType<import('../useFormatEditor').useFormatEditor> }} props
 */
export default function StepColumns({ editor }) {
  const { draft, updateDraft, sampleColumns, sampleColumnTypes, validation } = editor;
  const errors = validation.errorsByField;
  const amt = draft.amount_config;

  return (
    <div className="fe-step fe-step-cols">
      <h2>Columns</h2>
      <p className="fe-step__sub">
        Map the columns in the bank&apos;s export to the fields the system needs.
        {sampleColumns.length > 0
          ? ` Detected ${sampleColumns.length} columns from your sample file.`
          : ' No sample file loaded — type column names manually.'}
      </p>

      {/* ── 1. Date ─────────────────────────────────────────────────── */}
      <section className="fe-step-cols__section">
        <h3>Date</h3>
        <DateFormatField editor={editor} />
      </section>

      {/* ── 2. Description ──────────────────────────────────────────── */}
      <section className="fe-step-cols__section">
        <h3>Description</h3>
        <FormField
          label="Description column"
          required
          error={errors.description_column}
          help="The column containing the transaction narrative or memo."
        >
          <ColumnSelect
            value={draft.description_column}
            onChange={(v) => updateDraft('description_column', v)}
            columns={sampleColumns}
            columnTypes={sampleColumnTypes}
            placeholder="Select description column…"
          />
        </FormField>
      </section>

      {/* ── 3. Amount ───────────────────────────────────────────────── */}
      <section className="fe-step-cols__section">
        <h3>Amount</h3>

        <AmountModeRadio
          value={draft.amountMode}
          onChange={(m) => updateDraft('amountMode', m)}
        />

        {/* Conditional fields per mode */}
        {draft.amountMode === AMOUNT_MODE.SPLIT && (
          <div className="fe-step-cols__fields">
            <FormField
              label="Credit column"
              required
              error={errors['amount_config.credit_column']}
              help="Column with money-in values."
            >
              <ColumnSelect
                value={amt.credit_column}
                onChange={(v) => updateDraft('amount_config.credit_column', v)}
                columns={sampleColumns}
                columnTypes={sampleColumnTypes}
                placeholder="Select credit column…"
              />
            </FormField>
            <FormField
              label="Debit column"
              required
              error={errors['amount_config.debit_column']}
              help="Column with money-out values."
            >
              <ColumnSelect
                value={amt.debit_column}
                onChange={(v) => updateDraft('amount_config.debit_column', v)}
                columns={sampleColumns}
                columnTypes={sampleColumnTypes}
                placeholder="Select debit column…"
              />
            </FormField>
          </div>
        )}

        {draft.amountMode === AMOUNT_MODE.SIGNED && (
          <FormField
            label="Amount column"
            required
            error={errors['amount_config.amount_column']}
            help="Negative values are debits, positive are credits."
          >
            <ColumnSelect
              value={amt.amount_column}
              onChange={(v) => updateDraft('amount_config.amount_column', v)}
              columns={sampleColumns}
              columnTypes={sampleColumnTypes}
              placeholder="Select amount column…"
            />
          </FormField>
        )}

        {draft.amountMode === AMOUNT_MODE.INDICATOR && (
          <>
            <FormField
              label="Amount column"
              required
              error={errors['amount_config.amount_column']}
            >
              <ColumnSelect
                value={amt.amount_column}
                onChange={(v) => updateDraft('amount_config.amount_column', v)}
                columns={sampleColumns}
                columnTypes={sampleColumnTypes}
                placeholder="Select amount column…"
              />
            </FormField>
            <div className="fe-step-cols__fields">
              <FormField
                label="Credit indicator column"
                required
                error={errors['amount_config.credit_indicator_column']}
                help="Column that flags whether a row is a credit."
              >
                <ColumnSelect
                  value={amt.credit_indicator_column}
                  onChange={(v) => updateDraft('amount_config.credit_indicator_column', v)}
                  columns={sampleColumns}
                  columnTypes={sampleColumnTypes}
                  placeholder="Select indicator column…"
                />
              </FormField>
              <FormField
                label="Credit indicator value"
                required
                error={errors['amount_config.credit_indicator_value']}
                help='The value that means "credit", e.g. "CR" or "C".'
              >
                <TextInput
                  value={amt.credit_indicator_value ?? ''}
                  onChange={(v) => updateDraft('amount_config.credit_indicator_value', v)}
                  placeholder='e.g. CR'
                />
              </FormField>
            </div>
          </>
        )}
      </section>

      {/* ── 4. Advanced ─────────────────────────────────────────────── */}
      <details className="fe-step-cols__advanced">
        <summary>Advanced settings</summary>
        <div className="fe-step-cols__advanced-body">

          {/* Optional columns */}
          <div className="fe-step-cols__fields">
            <FormField label="Balance column" help="Optional running balance — not used in processing.">
              <ColumnSelect
                value={draft.balance_column}
                onChange={(v) => updateDraft('balance_column', v)}
                columns={sampleColumns}
                columnTypes={sampleColumnTypes}
                required={false}
                placeholder="None"
              />
            </FormField>
            <FormField label="Reference column" help="Optional reference or memo column.">
              <ColumnSelect
                value={draft.reference_column}
                onChange={(v) => updateDraft('reference_column', v)}
                columns={sampleColumns}
                columnTypes={sampleColumnTypes}
                required={false}
                placeholder="None"
              />
            </FormField>
          </div>

          {/* Number formatting */}
          <div className="fe-step-cols__fields fe-step-cols__fields--narrow">
            <FormField label="Decimal separator" help='Usually "." — some European banks use ","'>
              <TextInput
                value={amt.decimal_separator}
                onChange={(v) => updateDraft('amount_config.decimal_separator', v)}
                placeholder="."
                maxLength={1}
              />
            </FormField>
            <FormField label="Thousands separator" help='Usually "," — leave empty if none.'>
              <TextInput
                value={amt.thousands_separator}
                onChange={(v) => updateDraft('amount_config.thousands_separator', v)}
                placeholder=","
                maxLength={1}
              />
            </FormField>
          </div>

          <FormField
            label="Currency symbols to strip"
            help="Symbols removed from amount values before parsing. Press Enter to add."
          >
            <ChipInput
              value={amt.currency_symbols}
              onChange={(v) => updateDraft('amount_config.currency_symbols', v)}
              placeholder="e.g. €"
            />
          </FormField>

          <Checkbox
            checked={amt.debit_is_negative}
            onChange={(v) => updateDraft('amount_config.debit_is_negative', v)}
            label="Store debits as negative amounts (standard convention)"
          />

          <FormField
            label="Exclude patterns"
            help="Regex patterns matched against the description column. Matching rows are dropped — use for OPENING BALANCE lines etc. Press Enter to add."
          >
            <ChipInput
              value={draft.exclude_patterns}
              onChange={(v) => updateDraft('exclude_patterns', v)}
              placeholder="e.g. OPENING BALANCE"
            />
          </FormField>
        </div>
      </details>
    </div>
  );
}