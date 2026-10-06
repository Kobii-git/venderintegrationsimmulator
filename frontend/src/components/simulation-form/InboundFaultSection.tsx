export interface InboundFaultState {
  enabled: boolean;
  responseStatus: number | "";
  delayMs: number;
  forceEmpty: boolean;
  malformedJson: boolean;
  paginationInconsistent: boolean;
  oauthEnabled: boolean;
  oauthInvalidClient: boolean;
  oauthTokenEndpointFailure: boolean;
  oauthWrongScope: boolean;
  oauthRejectExpired: boolean;
}

interface InboundFaultSectionProps {
  value: InboundFaultState;
  onChange: (value: Partial<InboundFaultState>) => void;
}

export function InboundFaultSection({ value, onChange }: InboundFaultSectionProps) {
  return (
    <section className="form-section" aria-labelledby="inbound-fault-heading">
      <div id="inbound-fault-heading" className="section-title">Inbound fault simulation</div>
      <label className="checkbox-item">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(event) => onChange({ enabled: event.target.checked })}
        />
        Enable inbound fault injection
      </label>
      {value.enabled ? (
        <div className="grid-2">
          <div className="form-row">
            <label htmlFor="inbound-status">Forced HTTP status</label>
            <input
              id="inbound-status"
              type="number"
              placeholder="e.g. 429"
              value={value.responseStatus}
              onChange={(event) =>
                onChange({
                  responseStatus: event.target.value ? Number(event.target.value) : "",
                })
              }
            />
          </div>
          <div className="form-row">
            <label htmlFor="inbound-delay">Delay (ms)</label>
            <input
              id="inbound-delay"
              type="number"
              min={0}
              max={30000}
              value={value.delayMs}
              onChange={(event) => onChange({ delayMs: Number(event.target.value) })}
            />
          </div>
          <FaultToggle
            label="Force empty result set"
            checked={value.forceEmpty}
            onChange={(forceEmpty) => onChange({ forceEmpty })}
          />
          <FaultToggle
            label="Malformed JSON body"
            checked={value.malformedJson}
            onChange={(malformedJson) => onChange({ malformedJson })}
          />
          <FaultToggle
            label="Pagination inconsistency"
            checked={value.paginationInconsistent}
            onChange={(paginationInconsistent) => onChange({ paginationInconsistent })}
          />
        </div>
      ) : null}

      <div className="section-title">OAuth fault simulation</div>
      <FaultToggle
        label="Enable OAuth fault injection"
        checked={value.oauthEnabled}
        onChange={(oauthEnabled) => onChange({ oauthEnabled })}
      />
      {value.oauthEnabled ? (
        <div className="grid-2">
          <FaultToggle
            label="Force invalid_client on token endpoint"
            checked={value.oauthInvalidClient}
            onChange={(oauthInvalidClient) => onChange({ oauthInvalidClient })}
          />
          <FaultToggle
            label="Token endpoint failure"
            checked={value.oauthTokenEndpointFailure}
            onChange={(oauthTokenEndpointFailure) => onChange({ oauthTokenEndpointFailure })}
          />
          <FaultToggle
            label="Force invalid_scope"
            checked={value.oauthWrongScope}
            onChange={(oauthWrongScope) => onChange({ oauthWrongScope })}
          />
          <FaultToggle
            label="Reject bearer tokens as expired"
            checked={value.oauthRejectExpired}
            onChange={(oauthRejectExpired) => onChange({ oauthRejectExpired })}
          />
        </div>
      ) : null}
    </section>
  );
}

function FaultToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="checkbox-item">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}
