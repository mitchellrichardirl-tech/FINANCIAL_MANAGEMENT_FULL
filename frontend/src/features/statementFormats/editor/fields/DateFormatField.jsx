import Checkbox from '@/components/Checkbox';
import Dropdown from '@/components/Dropdown';
import FormField from '@/components/FormField';
import TextInput from '@/components/TextInput';
import ColumnSelect from './ColumnSelect';
import { DATE_FORMAT_PRESETS } from '../../constants';

export default function DateFormatField({ editor }) {
  const { draft, updateDraft, sampleColumns, sampleColumnTypes, validation } = editor;
  const { column, format, dayfirst } = draft.date_config;
  const errors = validation.errorsByField;

  const isAuto = format === null || format === undefined;
  const isKnownPreset = !isAuto && DATE_FORMAT_PRESETS.some(
    (p) => p.value !== '__AUTO__' && p.value !== '__CUSTOM__' && p.value === format,
  );
  const isCustom = !isAuto && !isKnownPreset;

  const dropdownValue = isAuto ? '__AUTO__' : isCustom ? '__CUSTOM__' : format;

  const handlePresetChange = (val) => {
    if (val === '__AUTO__') {
      updateDraft('date_config.format', null);
    } else if (val === '__CUSTOM__') {
      if (isAuto || isKnownPreset) updateDraft('date_config.format', '');
    } else {
      updateDraft('date_config.format', val);
    }
  };

  const formatHelp = isAuto
    ? 'The system will try multiple common date formats automatically.'
    : undefined;

  return (
    <>
      <FormField
        label="Date column"
        required
        error={errors['date_config.column']}
        htmlFor="date-column"
      >
        <ColumnSelect
          value={column}
          onChange={(v) => updateDraft('date_config.column', v)}
          columns={sampleColumns}
          columnTypes={sampleColumnTypes}
          placeholder="Select date column…"
        />
      </FormField>

      <FormField label="Date format" help={formatHelp}>
        <Dropdown
          value={dropdownValue}
          onChange={handlePresetChange}
          options={DATE_FORMAT_PRESETS}
          valueKey="value"
          labelKey="label"
        />
      </FormField>

      {isCustom && (
        <FormField
          label="Custom format pattern"
          help="Python strptime codes — %d=day, %m=month, %Y=4-digit year, %y=2-digit, %H=hour, %M=minute, %S=second."
        >
          <TextInput
            value={format ?? ''}
            onChange={(v) => updateDraft('date_config.format', v)}
            placeholder="e.g. %d/%m/%Y"
          />
        </FormField>
      )}

      <Checkbox
        checked={dayfirst}
        onChange={(v) => updateDraft('date_config.dayfirst', v)}
        disabled={!isAuto}
        label="Assume day comes before month (European date order)"
      />
    </>
  );
}
