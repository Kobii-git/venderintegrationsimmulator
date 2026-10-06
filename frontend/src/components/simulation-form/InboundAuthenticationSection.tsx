import type { InboundAuthMethodId } from "../../types/api";

export interface InboundAuthenticationState {
  methodId: InboundAuthMethodId;
  apiKeyHeader: string;
  apiKeyQueryParam: string;
  apiKeyPrefix: string;
  token: string;
  username: string;
  password: string;
  oauthClientId: string;
  oauthClientSecret: string;
  oauthTokenTtlSeconds: number;
  oauthAllowedScopes: string;
  clearPassword: boolean;
  clearToken: boolean;
  clearOAuthSecret: boolean;
  hasPassword: boolean;
  hasToken: boolean;
  hasOAuthSecret: boolean;
}

interface InboundAuthenticationSectionProps {
  methods: InboundAuthMethodId[];
  value: InboundAuthenticationState;
  onChange: (value: Partial<InboundAuthenticationState>) => void;
}

export function InboundAuthenticationSection({
  methods,
  value,
  onChange,
}: InboundAuthenticationSectionProps) {
  return (
    <section className="form-section" aria-labelledby="inbound-auth-heading">
      <div id="inbound-auth-heading" className="section-title">Inbound authentication</div>
      <div className="grid-2">
        <div className="form-row">
          <label htmlFor="inbound-auth">Inbound auth</label>
          <select
            id="inbound-auth"
            value={value.methodId}
            onChange={(event) => onChange({ methodId: event.target.value as InboundAuthMethodId })}
          >
            {methods.map((method) => (
              <option key={method} value={method}>
                {method === "oauth2_client_credentials"
                  ? "OAuth2 client credentials"
                  : method.replaceAll("_", " ")}
              </option>
            ))}
          </select>
        </div>
        {value.methodId === "api_key" ? (
          <>
            <div className="form-row">
              <label htmlFor="api-key-header">API key header</label>
              <input
                id="api-key-header"
                value={value.apiKeyHeader}
                onChange={(event) => onChange({ apiKeyHeader: event.target.value })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="api-key-query">API key query parameter</label>
              <input
                id="api-key-query"
                placeholder="Optional alternative, e.g. api_key"
                value={value.apiKeyQueryParam}
                onChange={(event) => onChange({ apiKeyQueryParam: event.target.value })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="api-key-prefix">API key prefix</label>
              <input
                id="api-key-prefix"
                placeholder="Optional, e.g. SSWS or ApiKey"
                value={value.apiKeyPrefix}
                onChange={(event) => onChange({ apiKeyPrefix: event.target.value })}
              />
              <span className="form-hint">Include any required trailing space.</span>
            </div>
          </>
        ) : null}
      </div>
      {value.methodId === "basic" ? (
        <div className="grid-2">
          <div className="form-row">
            <label htmlFor="inbound-username">Username</label>
            <input
              id="inbound-username"
              value={value.username}
              onChange={(event) => onChange({ username: event.target.value })}
            />
          </div>
          <div className="form-row">
            <label htmlFor="inbound-password">Password</label>
            <input
              id="inbound-password"
              type="password"
              placeholder={value.hasPassword ? "Leave blank to keep existing" : ""}
              value={value.password}
              onChange={(event) => onChange({ password: event.target.value })}
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
      {value.methodId === "api_key" || value.methodId === "bearer" ? (
        <div className="form-row">
          <label htmlFor="inbound-token">Token / API key</label>
          <input
            id="inbound-token"
            type="password"
            placeholder="Leave blank to keep existing on edit"
            value={value.token}
            onChange={(event) => onChange({ token: event.target.value })}
          />
          {value.hasToken ? (
            <label className="checkbox-item">
              <input
                type="checkbox"
                checked={value.clearToken}
                onChange={(event) => onChange({ clearToken: event.target.checked })}
              />
              Clear stored token / key
            </label>
          ) : null}
        </div>
      ) : null}
      {value.methodId === "oauth2_client_credentials" ? (
        <>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="oauth-client-id">Client ID</label>
              <input
                id="oauth-client-id"
                required
                value={value.oauthClientId}
                onChange={(event) => onChange({ oauthClientId: event.target.value })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="oauth-client-secret">Client secret</label>
              <input
                id="oauth-client-secret"
                type="password"
                placeholder={value.hasOAuthSecret ? "Leave blank to keep existing" : ""}
                value={value.oauthClientSecret}
                onChange={(event) => onChange({ oauthClientSecret: event.target.value })}
              />
              {value.hasOAuthSecret ? (
                <label className="checkbox-item">
                  <input
                    type="checkbox"
                    checked={value.clearOAuthSecret}
                    onChange={(event) => onChange({ clearOAuthSecret: event.target.checked })}
                  />
                  Clear stored client secret
                </label>
              ) : null}
            </div>
          </div>
          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="oauth-token-ttl">Token TTL (seconds)</label>
              <input
                id="oauth-token-ttl"
                type="number"
                min={60}
                max={86400}
                value={value.oauthTokenTtlSeconds}
                onChange={(event) => onChange({ oauthTokenTtlSeconds: Number(event.target.value) })}
              />
            </div>
            <div className="form-row">
              <label htmlFor="oauth-scopes">Allowed scopes (comma-separated)</label>
              <input
                id="oauth-scopes"
                placeholder="read, events.read"
                value={value.oauthAllowedScopes}
                onChange={(event) => onChange({ oauthAllowedScopes: event.target.value })}
              />
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}
