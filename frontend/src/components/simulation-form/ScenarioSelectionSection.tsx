import type { ScenarioSummary } from "../../types/api";

interface ScenarioSelectionSectionProps {
  scenarios: ScenarioSummary[];
  selectedIds: string[];
  onToggle: (scenarioId: string) => void;
}

export function ScenarioSelectionSection({
  scenarios,
  selectedIds,
  onToggle,
}: ScenarioSelectionSectionProps) {
  return (
    <section className="form-section" aria-labelledby="scenarios-heading">
      <div id="scenarios-heading" className="section-title">Scenarios</div>
      <div className="checkbox-group">
        {scenarios.map((scenario) => (
          <label key={scenario.id} className="checkbox-item">
            <input
              type="checkbox"
              checked={selectedIds.includes(scenario.id)}
              onChange={() => onToggle(scenario.id)}
            />
            <span>
              <strong>{scenario.display_name}</strong>{" "}
              <span style={{ color: "var(--text-muted)" }}>({scenario.id})</span>
            </span>
          </label>
        ))}
      </div>
      {selectedIds.length === 0 ? (
        <span className="form-hint" style={{ color: "var(--danger)" }}>
          Select at least one scenario
        </span>
      ) : null}
    </section>
  );
}
