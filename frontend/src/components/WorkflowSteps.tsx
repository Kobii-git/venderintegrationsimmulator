import { Icon } from "./Icon";

export function WorkflowSteps({ steps, current, onBack, disabled = false }: {
  steps: string[]; current: number; onBack: (step: number) => void; disabled?: boolean;
}) {
  return <nav className="setup-steps" aria-label="Upload steps"><ol>
    {steps.map((label, index) => <li key={label} className={index === current ? "current" : index < current ? "complete" : ""}>
      <button type="button" disabled={disabled || index > current || current === steps.length - 1}
        aria-current={current === index ? "step" : undefined} onClick={() => onBack(index)}>
        <span className="step-number">{index < current ? <Icon name="check" /> : index + 1}</span><span>{label}</span>
      </button>
    </li>)}
  </ol></nav>;
}
