/** Filled in chunk 6. */
export default function StepDefaults({ editor, schema }) {
  return (
    <div className="fe-step">
      <h2>Defaults</h2>
      <p className="fe-step__sub">Values applied to every transaction imported with this format.</p>
      <div className="fe-step__placeholder">Defaults form ({schema?.allowed_defaults?.length ?? 0} fields) — chunk 6</div>
    </div>
  );
}