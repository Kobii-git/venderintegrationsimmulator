export type FidelityMode = "vendor_accurate" | "troubleshooting";
export type SimulationStatus = "stopped" | "running" | "completed" | "error";
export type EventInstanceStatus =
  "pending" | "delivered" | "failed" | "cancelled" | "partial";
export type PayloadSource =
  "generated" | "manual_override" | "replay_exact" | "replay_regenerate";
export type ScheduleType = "manual" | "continuous" | "finite";
export type SimulationMode = "push_webhook" | "pull_api";
export type SyslogProtocol = "udp" | "tcp" | "tls";
export type SyslogFormat = "rfc3164" | "rfc5424" | "raw";
export type TcpFraming = "newline" | "octet_counting";
export type TransportId = "http_webhook" | "syslog" | "azure_logs_ingestion" | "azure_function_app" | "cloudflare_logpush";
export type HttpMethod = "GET" | "POST" | "PUT" | "HEAD";
export type AuthMethodId = "none" | "basic" | "bearer" | "api_key_header";
export type InboundAuthMethodId =
  "none" | "api_key" | "basic" | "bearer" | "oauth2_client_credentials";
export type DeliveryErrorCategory =
  | "response_too_large"
  | "invalid_response"
  | "redirect_rejected"
  | "dns"
  | "connection"
  | "connection_timeout"
  | "read_timeout"
  | "timeout"
  | "tls"
  | "malformed_destination"
  | "auth"
  | "rate_limit"
  | "http_4xx"
  | "http_5xx"
  | "internal"
  | "unknown";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface VersionResponse {
  app_name: string;
  version: string;
  environment: string;
}

export interface ProductSummary {
  id: string;
  display_name: string;
  version: string;
  description: string | null;
  supported_modes: SimulationMode[];
  supported_transports: string[];
  supported_auth_methods: AuthMethodId[];
  supported_inbound_auth_methods: InboundAuthMethodId[];
  scenario_count: number;
  has_plugin: boolean;
  formats?: string[];
  field_references?: string[];
  schema_version?: string | null;
  compatibility?: string | null;
}

export interface ScenarioSummary {
  id: string;
  display_name: string;
  description: string | null;
  default_transport: string;
  config_schema: Record<string, unknown>;
  supported_modes?: SimulationMode[];
  delivery_policy?: Record<string, unknown>;
}

export interface JsonSchemaProperty {
  hidden?: boolean;
  deprecated?: boolean;
  type?: "string" | "integer" | "number" | "boolean";
  title?: string;
  description?: string;
  default?: string | number | boolean;
  enum?: Array<string | number>;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  format?: string;
}

export interface ObjectJsonSchema {
  type?: "object";
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  additionalProperties?: boolean;
}

export interface ProductActionSummary {
  id: string;
  display_name: string;
  description?: string | null;
  supported_modes: SimulationMode[];
}

export interface MockRouteSummary {
  id: string;
  path: string;
  methods: string[];
  scenario_id: string;
  description?: string | null;
  response_type?: string;
  supports_pagination?: boolean;
  supports_time_filter?: boolean;
  handler?: "dataset_list" | "dataset_single" | "static" | "oauth_token";
  required_oauth_scopes?: string[];
  response_profile?: Record<string, unknown>;
}

export interface ScenarioVariable {
  name: string;
  type?: string;
  description?: string;
  default?: unknown;
  required?: boolean;
}

export interface ScenarioDetail extends ScenarioSummary {
  product_id: string;
  template_path: string;
  variables: ScenarioVariable[];
  template_metadata: Record<string, unknown>;
}

export interface ProductDetail extends ProductSummary {
  connection_profiles?: Array<{ id: string; display_name: string; mode: SimulationMode; transport_id?: string | null }>;
  diagnostic_merge: string;
  inbound_options_schema?: ObjectJsonSchema;
  scenarios: ScenarioSummary[];
  mock_routes?: MockRouteSummary[];
  actions?: ProductActionSummary[];
}

export interface DestinationConfig {
  transport_id?: TransportId;
  url?: string | null;
  method?: string;
  headers?: ConfiguredValue[];
  query_params?: ConfiguredValue[];
  timeout_seconds?: number;
  verify_tls?: boolean;
  follow_redirects?: boolean;
  ca_file?: string | null;
  endpoint?: string | null;
  dcr_immutable_id?: string | null;
  stream?: string | null;
  tenant_id?: string | null;
  batch_max_bytes?: number;
  max_retries?: number;
  host?: string | null;
  port?: number;
  protocol?: SyslogProtocol;
  format?: SyslogFormat;
  facility?: number;
  severity?: number;
  syslog_hostname?: string | null;
  app_name?: string;
  proc_id?: string;
  msg_id?: string;
  tcp_framing?: TcpFraming;
  rate_limit_per_second?: number | null;
}

export interface ConfiguredValue {
  name: string;
  value?: string;
  sensitive: boolean;
  has_value?: boolean;
}

export interface AuthConfigInput {
  auth_method_id?: AuthMethodId;
  username?: string | null;
  password?: string | null;
  oauth_client_id?: string | null;
  oauth_client_secret?: string | null;
  token?: string | null;
  header_name?: string | null;
  header_prefix?: string | null;
}

export interface AuthConfigResponse {
  auth_method_id: AuthMethodId;
  username?: string | null;
  header_name?: string | null;
  header_prefix?: string | null;
  has_password: boolean;
  has_token: boolean;
  oauth_client_id?: string | null;
  has_oauth_client_secret?: boolean;
}

export interface ScheduleConfig {
  type: ScheduleType;
  interval_seconds?: number | null;
  event_count?: number | null;
  events_per_second?: number | null;
  scenario_weights?: Record<string, number>;
  user_pool?: string[];
  incident_preset?:
    | "password_spray"
    | "privileged_logon"
    | "firewall_scan"
    | "malware_detection"
    | null;
  next_run_at?: string | null;
}

export interface SimulationRuntimeStats {
  events_generated: number;
  events_attempted: number;
  events_successful: number;
  events_failed: number;
  last_delivery_at: string | null;
  last_http_status: number | null;
  last_latency_ms: number | null;
  last_error_message: string | null;
  last_event_id: string | null;
  started_at: string | null;
  stopped_at: string | null;
  last_error_at: string | null;
  interrupted_on_restart: boolean;
  inbound_requests_total?: number;
  inbound_requests_successful?: number;
  inbound_requests_failed?: number;
  inbound_items_returned_total?: number;
  last_inbound_at?: string | null;
  last_inbound_items?: number | null;
  pull_dataset_activation_id?: string | null;
  pull_dataset_item_count?: number;
}

export type DuplicateMode =
  | "none"
  | "exact_payload"
  | "duplicate_correlation_id"
  | "repeat_scenario_new_ids";

export interface TimestampFault {
  mode?: "current" | "fixed" | "offset";
  fixed_value?: string | null;
  offset_amount?: number | null;
  offset_unit?: "minutes" | "hours" | "days" | null;
  offset_direction?: "past" | "future";
  field_paths?: string[];
}

export interface PayloadFaults {
  remove_timestamp?: boolean;
  invalid_timestamp?: boolean;
  timestamp?: TimestampFault;
  remove_fields?: string[];
  null_fields?: string[];
  extra_fields?: Record<string, unknown>;
  large_field_path?: string | null;
  large_field_size_kb?: number;
  malformed_json?: boolean;
}

export interface DuplicateTesting {
  mode?: DuplicateMode;
  source_event_id?: string | null;
  correlation_id?: string | null;
}

export interface DeliveryBehaviour {
  pre_delay_ms?: number;
  timeout_seconds?: number | null;
  duplicate_send_count?: number;
  retry_count?: number;
  retry_delay_ms?: number;
}

export interface InboundFaultConfig {
  enabled?: boolean;
  response_status?: number | null;
  delay_ms?: number;
  malformed_json?: boolean;
  force_empty?: boolean;
  pagination_inconsistent?: boolean;
}

export interface OAuthFaultConfig {
  enabled?: boolean;
  invalid_client?: boolean;
  token_endpoint_failure?: boolean;
  token_endpoint_status?: number | null;
  wrong_scope?: boolean;
  reject_tokens_as_expired?: boolean;
}

export interface InboundConfig {
  auth_method_id?: InboundAuthMethodId;
  api_key_header?: string;
  api_key_query_param?: string | null;
  api_key_prefix?: string;
  vendor_options?: Record<string, string | number | boolean>;
  dataset_size?: number;
  item_interval_seconds?: number;
  default_page_size?: number;
  max_page_size?: number;
  pagination_style?: "cursor" | "page";
  oauth_token_ttl_seconds?: number;
  oauth_allowed_scopes?: string[];
  oauth_fault_config?: OAuthFaultConfig;
  fault_config?: InboundFaultConfig;
}

export interface FaultConfig {
  enabled?: boolean;
  payload?: PayloadFaults;
  duplicate?: DuplicateTesting;
  delivery?: DeliveryBehaviour;
}

export interface SimulationBurstRequest {
  count: number;
  interval_ms?: number;
  events_per_second?: number | null;
  scenario_id?: string | null;
  confirm_large_run?: boolean;
}

export interface SimulationBurstResponse {
  simulation_id: string;
  requested: number;
  generated: number;
  successful: number;
  failed: number;
  event_ids: string[];
  faults_enabled: boolean;
}

export interface SimulationCreate {
  name: string;
  product_id: string;
  scenario_id?: string | null;
  scenario_ids?: string[];
  simulation_mode?: SimulationMode;
  fidelity_mode?: FidelityMode;
  destination?: DestinationConfig;
  auth_config?: AuthConfigInput;
  scenario_overrides?: Record<string, Record<string, unknown>>;
  targets?: TargetInput[];
  devices?: SimulatedDevice[];
  replay_config?: ReplayConfig | Record<string, never>;
  schedule?: ScheduleConfig;
  random_seed?: number | null;
  fault_config?: FaultConfig;
  inbound_config?: InboundConfig;
}

export interface SimulationUpdate {
  name?: string;
  scenario_id?: string;
  scenario_ids?: string[];
  simulation_mode?: SimulationMode;
  fidelity_mode?: FidelityMode;
  destination?: DestinationConfig;
  auth_config?: AuthConfigInput;
  scenario_overrides?: Record<string, Record<string, unknown>>;
  targets?: TargetInput[];
  devices?: SimulatedDevice[];
  replay_config?: ReplayConfig | Record<string, never>;
  schedule?: ScheduleConfig;
  random_seed?: number | null;
  fault_config?: FaultConfig;
  inbound_config?: InboundConfig;
}

export interface SimulationResponse {
  id: string;
  name: string;
  product_id: string;
  scenario_id: string;
  scenario_ids: string[];
  simulation_mode: string;
  fidelity_mode: string;
  status: SimulationStatus;
  destination: DestinationConfig;
  auth_config: AuthConfigResponse;
  scenario_overrides: Record<string, Record<string, unknown>>;
  schedule: ScheduleConfig;
  fault_config: FaultConfig;
  inbound_config: InboundConfig;
  random_seed: number | null;
  missing_secrets: string[];
  targets?: TargetResponse[];
  devices?: SimulatedDevice[];
  replay_config?: ReplayConfig | Record<string, never>;
  runtime_stats: SimulationRuntimeStats;
  created_at: string;
  updated_at: string;
}

export interface SimulationSendResponse {
  simulation_id: string;
  event_id: string;
  correlation_id: string;
  scenario_id: string;
  payload: Record<string, unknown>;
  payload_source: PayloadSource;
  delivery_success: boolean;
  response_status_code: number | null;
  latency_ms: number | null;
  error_message: string | null;
}

export interface DeliveryAttemptResponse {
  id: string;
  attempt_number: number;
  target_id?: string | null;
  delivery_confirmation?: string | null;
  delivery_note?: string | null;
  started_at: string;
  completed_at: string | null;
  transport_id: string;
  destination_summary: string;
  request_url_redacted: string | null;
  request_method: string | null;
  request_headers_redacted: Record<string, string>;
  request_query_params_redacted: Record<string, string>;
  request_body: string | null;
  response_status_code: number | null;
  response_headers_redacted: Record<string, string>;
  response_body: string | null;
  latency_ms: number | null;
  success: boolean;
  error_message: string | null;
  error_category: DeliveryErrorCategory | null;
  error_explanation: string | null;
}

export interface EventInstanceSummary {
  id: string;
  simulation_id: string;
  product_id: string;
  scenario_id: string;
  event_kind?: "scenario" | "workflow_action";
  action_id?: string | null;
  correlation_id: string;
  status: EventInstanceStatus;
  payload_source: PayloadSource;
  generated_at: string;
  delivery_success: boolean | null;
  response_status_code: number | null;
  latency_ms: number | null;
  fault_modified?: boolean;
}

export interface EventInstanceDetail extends EventInstanceSummary {
  fidelity_mode: string;
  payload: Record<string, unknown>;
  replayed_from_event_id: string | null;
  simulator_metadata: Record<string, unknown>;
  delivery_attempts: DeliveryAttemptResponse[];
}

export interface EventListFilters {
  limit?: number;
  scenario_id?: string;
  success?: boolean;
  http_status?: number;
  correlation_id?: string;
}

export interface ReplayEventRequest {
  mode: "exact" | "regenerate";
}

export interface ReplayEventResponse {
  simulation_id: string;
  source_event_id: string;
  new_event_id: string;
  correlation_id: string;
  scenario_id: string;
  payload_source: PayloadSource;
  payload: Record<string, unknown>;
  delivery_success: boolean;
  response_status_code: number | null;
  latency_ms: number | null;
  error_message: string | null;
}

export interface CurlResponse {
  attempt_id: string;
  exact: boolean;
  command: string;
  warnings: string[];
  secrets_redacted: boolean;
}

export interface InboundEndpointRoute {
  id: string;
  path: string;
  url: string;
  methods: string[];
  handler: string;
}

export interface InboundEndpointInfo {
  simulation_id: string;
  product_id: string;
  simulation_mode: string;
  status: string;
  auth_method_id: string;
  routes: InboundEndpointRoute[];
  oauth_token_url?: string | null;
  discovery_urls?: string[];
  api_urls?: string[];
  oauth_token_ttl_seconds?: number | null;
  oauth_allowed_scopes?: string[];
  vendor_options?: Record<string, string | number | boolean>;
  query_hint: string;
}

export interface InboundRequestSummary {
  id: string;
  simulation_id: string | null;
  product_id: string;
  route_id: string;
  received_at: string;
  request_method: string;
  request_path: string;
  response_status_code: number;
  auth_method_id: string;
  auth_result: string;
  latency_ms: number;
  items_returned: number;
  error_message?: string | null;
  request_kind?: string;
  token_metadata?: Record<string, unknown> | null;
}

export interface InboundRequestDetail extends InboundRequestSummary {
  request_query_params: Record<string, unknown>;
  request_headers_redacted: Record<string, string>;
  request_body: string | null;
  response_headers: Record<string, string>;
  response_body: string | null;
}

export interface IssuedOAuthToken {
  id: string;
  client_id: string;
  scope: string | null;
  issued_at: string;
  expires_at: string;
  revoked: boolean;
  is_expired: boolean;
}

export interface SimulationSendRequestBody {
  payload_override?: Record<string, unknown> | null;
  scenario_id?: string | null;
  preview_correlation_id?: string | null;
  payload_edited?: boolean;
}

export interface WorkflowActionResponse {
  simulation_id: string;
  action_id: string;
  event_id: string;
  assertion_passed: boolean;
  delivery_success: boolean;
  response_status_code: number | null;
  error_message: string | null;
}

export interface ScenarioEventRequest {
  fidelity_mode?: FidelityMode;
  scenario_overrides?: Record<string, unknown>;
  correlation_id?: string | null;
}

export interface ScenarioPreviewResponse {
  product_id: string;
  scenario_id: string;
  scenario_display_name: string;
  scenario_description: string | null;
  correlation_id: string;
  fidelity_mode: FidelityMode;
  content_type: string;
  method: string;
  payload: Record<string, unknown>;
}

export interface ScenarioRawPreviewResponse {
  product_id: string;
  scenario_id: string;
  fidelity_mode: FidelityMode;
  content_type: string;
  raw_log: string;
}

export interface ScenarioSendRequest extends ScenarioEventRequest {
  destination: DestinationConfig;
  auth_config?: AuthConfigInput;
  payload_override?: Record<string, unknown> | null;
}

export interface ScenarioSendResponse {
  event: {
    correlation_id: string;
    product_id: string;
    scenario_id: string;
    fidelity_mode: FidelityMode;
    content_type: string;
    method: string;
    payload: Record<string, unknown>;
    payload_source: string;
  };
  delivery: HttpDeliveryResultResponse;
}

export interface HttpTransportRequest {
  url: string;
  method?: HttpMethod;
  headers?: Record<string, string>;
  query_params?: Record<string, unknown>;
  body?: unknown;
  content_type?: string;
  auth_config?: AuthConfigInput;
  timeout_seconds?: number;
  verify_tls?: boolean;
  follow_redirects?: boolean;
  ca_file?: string | null;
  endpoint?: string | null;
  dcr_immutable_id?: string | null;
  stream?: string | null;
  tenant_id?: string | null;
  batch_max_bytes?: number;
  max_retries?: number;
  sensitive_header_names?: string[];
  sensitive_query_names?: string[];
}

export interface HttpDeliveryResultResponse {
  success: boolean;
  reached_server: boolean;
  started_at: string;
  completed_at: string;
  latency_ms: number;
  destination: string;
  method: string;
  request_headers_redacted: Record<string, string>;
  request_body: string | null;
  response_status_code: number | null;
  response_headers_redacted: Record<string, string>;
  response_body: string | null;
  error_message: string | null;
  error_category: DeliveryErrorCategory | null;
  delivery_confirmation?: "confirmed" | "transport_accepted" | "best_effort";
  delivery_note?: string | null;
}

export interface SyslogTransportRequest {
  host: string;
  port?: number;
  protocol?: SyslogProtocol;
  format?: SyslogFormat;
  facility?: number;
  severity?: number;
  syslog_hostname?: string | null;
  app_name?: string;
  proc_id?: string;
  msg_id?: string;
  tcp_framing?: TcpFraming;
  rate_limit_per_second?: number | null;
  timeout_seconds?: number;
  verify_tls?: boolean;
  message?: string;
  content_type?: string;
}

export interface SimulatedDevice {
  id: string;
  hostname: string;
  ip_address: string;
  vendor?: string | null;
}
export interface TargetInput {
  id: string;
  name: string;
  enabled: boolean;
  destination: DestinationConfig;
  auth_config: AuthConfigInput;
  payload_format: string;
  device_ids: string[];
  scenario_ids: string[];
  queue_limit: number;
}
export interface TargetResponse extends Omit<TargetInput, "auth_config"> {
  auth_config: AuthConfigResponse;
  stats: Record<string, string | number | null>;
}
export interface ReplayConfig {
  dataset_id: string;
  loop: boolean;
  timing: "fixed" | "original";
  rewrite_timestamps: boolean;
  timestamp_fields?: string[];
}
export interface Dataset {
  id: string;
  name: string;
  format: string;
  size_bytes: number;
  record_count: number;
  timestamp_fields: string[];
}
