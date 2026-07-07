export function CategorySetupWarning() {
  return (
    <section className="setup-warning" role="status">
      <strong>No categories are configured.</strong>
      <span>Run the SpendLens category seed command before entering categorized transactions.</span>
      <code>python -m app.seed</code>
    </section>
  );
}
