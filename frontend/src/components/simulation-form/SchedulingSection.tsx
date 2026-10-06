import type { ScheduleType } from "../../types/api";

interface SchedulingSectionProps {
  type: ScheduleType;
  intervalSeconds: number;
  eventCount: number;
  onTypeChange: (value: ScheduleType) => void;
  onIntervalChange: (value: number) => void;
  onEventCountChange: (value: number) => void;
}

export function SchedulingSection({
  type,
  intervalSeconds,
  eventCount,
  onTypeChange,
  onIntervalChange,
  onEventCountChange,
}: SchedulingSectionProps) {
  return (
    <section className="form-section" aria-labelledby="schedule-heading">
      <div id="schedule-heading" className="section-title">Schedule</div>
      <div className="grid-2">
        <div className="form-row">
          <label htmlFor="schedule">Mode</label>
          <select
            id="schedule"
            value={type}
            onChange={(event) => onTypeChange(event.target.value as ScheduleType)}
          >
            <option value="manual">Manual (one-shot via Send)</option>
            <option value="continuous">Continuous</option>
            <option value="finite">Finite count</option>
          </select>
        </div>
        {type !== "manual" ? (
          <div className="form-row">
            <label htmlFor="interval">Interval (seconds)</label>
            <input
              id="interval"
              type="number"
              min={1}
              value={intervalSeconds}
              onChange={(event) => onIntervalChange(Number(event.target.value))}
            />
          </div>
        ) : null}
      </div>
      {type === "finite" ? (
        <div className="form-row">
          <label htmlFor="count">Event count</label>
          <input
            id="count"
            type="number"
            min={1}
            value={eventCount}
            onChange={(event) => onEventCountChange(Number(event.target.value))}
          />
        </div>
      ) : null}
    </section>
  );
}
