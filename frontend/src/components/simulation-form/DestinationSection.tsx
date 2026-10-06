import type {
  AuthMethodId,
  DestinationConfig,
  TransportId,
} from "../../types/api";
import { StructuredValueEditor } from "../StructuredValueEditor";

interface DestinationAuthState {
  authMethodId: AuthMethodId;
  username: string;
  password: string;
  token: string;
  headerName: string;
  headerPrefix: string;
  clearPassword: boolean;
  clearToken: boolean;
  hasPassword: boolean;
  hasToken: boolean;
}

interface DestinationSectionProps {
  destination: DestinationConfig;
  supportedTransports: string[];
  authMethods: AuthMethodId[];
  auth: DestinationAuthState;
  testing: boolean;
  onDestinationChange: (value: DestinationConfig) => void;
  onAuthChange: (value: Partial<DestinationAuthState>) => void;
  onTest: () => void;
}

export function DestinationSection({
  destination,
  supportedTransports,
  authMethods,
  auth,
  testing,
  onDestinationChange,
  onAuthChange,
  onTest,
}: DestinationSectionProps) {
  const isSyslog = destination.transport_id === "syslog";
  const updateDestination = (value: Partial<DestinationConfig>) =>
    onDestinationChange({ ...destination, ...value });

  return (
    <section className="form-section" aria-labelledby="destination-heading">
      <div id="destination-heading" className="section-title">Destination</div>
      {supportedTransports.length > 1 ? (
        <div className="form-row">
          <label htmlFor="transport">Transport</label>
          <select
            id="transport"
            value={destination.transport_id}
            onChange={(event) =>
              updateDestination({ transport_id: event.target.value as TransportId })
            }
          >
            {supportedTransports.map((transport) => (
              <option key={transport} value={transport}>{transport}</option>
            ))}
          </select>
        </div>
      ) : null}

      {isSyslog ? (
        <>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="host">Syslog host</label>
              <input
                id="host"
                required
                placeholder="10.0.0.5 or collector.example"
                value={destination.host ?? ""}
                onChange={(event) => updateDestination({ host: event.target.value })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="port">Port</label>
              <input
                id="port"
                type="number"
                min={1}
                max={65535}
                value={destination.port ?? 514}
                onChange={(event) => updateDestination({ port: Number(event.target.value) })}
              />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="protocol">Protocol</label>
              <select
                id="protocol"
                value={destination.protocol}
                onChange={(event) =>
                  updateDestination({ protocol: event.target.value as DestinationConfig["protocol"] })
                }
              >
                <option value="udp">UDP</option>
                <option value="tcp">TCP</option>
                <option value="tls">TLS</option>
              </select>
            </div>
            <div className="form-row">
              <label htmlFor="format">Message format</label>
              <select
                id="format"
                value={destination.format}
                onChange={(event) =>
                  updateDestination({ format: event.target.value as DestinationConfig["format"] })
                }
              >
                <option value="rfc5424">RFC 5424</option>
                <option value="rfc3164">RFC 3164</option>
                <option value="raw">Raw / vendor formatted</option>
              </select>
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="facility">Facility (0–23)</label>
              <input
                id="facility"
                type="number"
                min={0}
                max={23}
                value={destination.facility ?? 16}
                onChange={(event) => updateDestination({ facility: Number(event.target.value) })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="severity">Severity (0–7)</label>
              <input
                id="severity"
                type="number"
                min={0}
                max={7}
                value={destination.severity ?? 6}
                onChange={(event) => updateDestination({ severity: Number(event.target.value) })}
              />
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="app_name">App name</label>
              <input
                id="app_name"
                value={destination.app_name ?? ""}
                onChange={(event) => updateDestination({ app_name: event.target.value })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="syslog_hostname">Syslog hostname field</label>
              <input
                id="syslog_hostname"
                placeholder="Optional hostname in message header"
                value={destination.syslog_hostname ?? ""}
                onChange={(event) => updateDestination({ syslog_hostname: event.target.value })}
              />
            </div>
          </div>
          {destination.protocol !== "udp" ? (
            <div className="form-row">
              <label htmlFor="tcp_framing">TCP framing</label>
              <select
                id="tcp_framing"
                value={destination.tcp_framing}
                onChange={(event) =>
                  updateDestination({
                    tcp_framing: event.target.value as DestinationConfig["tcp_framing"],
                  })
                }
              >
                <option value="newline">Newline delimited</option>
                <option value="octet_counting">Octet counting (RFC 6587)</option>
              </select>
            </div>
          ) : null}
          {destination.protocol === "tls" ? (
            <label className="checkbox-item">
              <input
                type="checkbox"
                checked={destination.verify_tls ?? true}
                onChange={(event) => updateDestination({ verify_tls: event.target.checked })}
              />
              Verify TLS certificate and hostname
            </label>
          ) : null}
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="rate_limit">Rate limit (events/sec)</label>
              <input
                id="rate_limit"
                type="number"
                min={0.1}
                step={0.1}
                placeholder="Optional"
                value={destination.rate_limit_per_second ?? ""}
                onChange={(event) =>
                  updateDestination({
                    rate_limit_per_second: event.target.value
                      ? Number(event.target.value)
                      : null,
                  })
                }
              />
            </div>
            <TimeoutInput destination={destination} onChange={updateDestination} />
          </div>
          <p className="form-hint">
            UDP delivery is best-effort: a successful send does not prove the remote collector
            received the message.
          </p>
        </>
      ) : (
        <>
          <div className="form-row">
            <label htmlFor="url">Webhook URL</label>
            <input
              id="url"
              required
              type="url"
              placeholder="https://your-collector/webhook"
              value={destination.url ?? ""}
              onChange={(event) => updateDestination({ url: event.target.value })}
            />
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="method">HTTP method</label>
              <select
                id="method"
                value={destination.method}
                onChange={(event) => updateDestination({ method: event.target.value })}
              >
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="GET">GET</option>
                <option value="HEAD">HEAD</option>
              </select>
            </div>
            <TimeoutInput destination={destination} onChange={updateDestination} />
          </div>
          <div className="grid-2">
            <label className="checkbox-item">
              <input
                type="checkbox"
                checked={destination.verify_tls ?? true}
                onChange={(event) => updateDestination({ verify_tls: event.target.checked })}
              />
              Verify TLS certificates
            </label>
            <label className="checkbox-item">
              <input
                type="checkbox"
                checked={destination.follow_redirects ?? true}
                onChange={(event) => updateDestination({ follow_redirects: event.target.checked })}
              />
              Follow redirects
            </label>
          </div>
          <StructuredValueEditor
            label="Custom headers"
            value={destination.headers ?? []}
            onChange={(headers) => updateDestination({ headers })}
          />
          <StructuredValueEditor
            label="URL query parameters"
            value={destination.query_params ?? []}
            onChange={(query_params) => updateDestination({ query_params })}
            namePlaceholder="Parameter"
          />
        </>
      )}

      <button type="button" className="btn" onClick={onTest} disabled={testing}>
        {testing ? "Testing…" : "Test connection"}
      </button>

      {!isSyslog ? (
        <OutboundAuthentication
          methods={authMethods}
          value={auth}
          onChange={onAuthChange}
        />
      ) : null}
    </section>
  );
}

function TimeoutInput({
  destination,
  onChange,
}: {
  destination: DestinationConfig;
  onChange: (value: Partial<DestinationConfig>) => void;
}) {
  return (
    <div className="form-row">
      <label htmlFor="timeout">Timeout (seconds)</label>
      <input
        id="timeout"
        type="number"
        min={1}
        max={300}
        value={destination.timeout_seconds}
        onChange={(event) => onChange({ timeout_seconds: Number(event.target.value) })}
      />
    </div>
  );
}

function OutboundAuthentication({
  methods,
  value,
  onChange,
}: {
  methods: AuthMethodId[];
  value: DestinationAuthState;
  onChange: (value: Partial<DestinationAuthState>) => void;
}) {
  return (
    <section className="form-section" aria-labelledby="outbound-auth-heading">
      <div id="outbound-auth-heading" className="section-title">Authentication</div>
      <div className="form-row">
        <label htmlFor="auth">Auth type</label>
        <select
          id="auth"
          value={value.authMethodId}
          onChange={(event) => onChange({ authMethodId: event.target.value as AuthMethodId })}
        >
          {methods.map((method) => <option key={method} value={method}>{method}</option>)}
        </select>
      </div>
      {value.authMethodId === "basic" ? (
        <div className="grid-2">
          <div className="form-row">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              value={value.username}
              onChange={(event) => onChange({ username: event.target.value })}
            />
          </div>
          <div className="form-row">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              placeholder={value.hasPassword ? "Leave blank to keep existing" : ""}
              value={value.password}
              onChange={(event) => onChange({ password: event.target.value })}
              autoComplete="new-password"
            />
            {value.hasPassword ? (
              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={value.clearPassword}
                  onChange={(event) => onChange({ clearPassword: event.target.checked })}
                />
                Clear stored password
              </label>
            ) : null}
          </div>
        </div>
      ) : null}
      {value.authMethodId === "bearer" || value.authMethodId === "api_key_header" ? (
        <div className="grid-2">
          {value.authMethodId === "api_key_header" ? (
            <div className="form-row">
              <label htmlFor="auth-header-name">Header name</label>
              <input
                id="auth-header-name"
                value={value.headerName}
                onChange={(event) => onChange({ headerName: event.target.value })}
              />
              <label htmlFor="auth-header-prefix">Value prefix</label>
              <input
                id="auth-header-prefix"
                placeholder="Optional, e.g. Token "
                value={value.headerPrefix}
                onChange={(event) => onChange({ headerPrefix: event.target.value })}
              />
            </div>
          ) : null}
          <div className="form-row">
            <label htmlFor="outbound-token">Token / API key</label>
            <input
              id="outbound-token"
              type="password"
              placeholder={value.hasToken ? "Stored — enter to replace" : ""}
              value={value.token}
              onChange={(event) => onChange({ token: event.target.value })}
              autoComplete="new-password"
            />
            {value.hasToken ? (
              <label className="checkbox-item">
                <input
                  type="checkbox"
                  checked={value.clearToken}
                  onChange={(event) => onChange({ clearToken: event.target.checked })}
                />
                Clear stored token
              </label>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
