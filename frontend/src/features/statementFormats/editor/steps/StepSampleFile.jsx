/** Filled in chunk 4. */
export default function StepSampleFile({ editor }) {
  return (
    <div className="fe-step">
      <h2>Sample file</h2>
      <p className="fe-step__sub">
        Upload an export from this bank so we can read its column names.
        {editor.mode !== 'create' && ' Optional — skip if you already know the columns.'}
      </p>
      <div className="fe-step__placeholder">File dropzone + raw preview — chunk 4</div>
    </div>
  );
}