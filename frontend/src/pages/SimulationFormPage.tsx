import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  createSimulation,
  getSimulation,
  updateSimulation,
} from "../api/simulations";
import { testHttpConnection, testSyslogConnection } from "../api/transport";
import { ErrorAlert } from "../components/ErrorAlert";
import { InfoAlert } from "../components/ErrorAlert";
import { LoadingState } from "../components/LoadingState";
import { ScenarioOverridesSection } from "../components/ScenarioOverridesSection";
import { DestinationSection } from "../components/simulation-form/DestinationSection";
import {
  FaultControlsSection,
  type FaultControlsState,
} from "../components/simulation-form/FaultControlsSection";
import { InboundAuthenticationSection } from "../components/simulation-form/InboundAuthenticationSection";
import { InboundFaultSection } from "../components/simulation-form/InboundFaultSection";
import { ScenarioSelectionSection } from "../components/simulation-form/ScenarioSelectionSection";
import { SchedulingSection } from "../components/simulation-form/SchedulingSection";
import { VendorOptionsSection } from "../components/simulation-form/VendorOptionsSection";
import { defaultsFromSchema } from "../components/simulation-form/vendorOptions";
import { useProductCatalog } from "../hooks/useProductCatalog";
import type {
  AuthConfigInput,
  AuthMethodId,
  DestinationConfig,
  DuplicateMode,
  FaultConfig,
  FidelityMode,
  InboundAuthMethodId,
  InboundConfig,
  ScheduleConfig,
  ScheduleType,
  SimulationCreate,
  SimulationMode,
  TransportId,
  SimulationResponse,
  SimulationUpdate,
  ConfiguredValue,
} from "../types/api";
import { formatApiError } from "../utils/format";

interface FormState {
  name: string;
  product_id: string;
  scenario_ids: string[];
  simulation_mode: SimulationMode;
  fidelity_mode: FidelityMode;
  destination: DestinationConfig;
  scenario_overrides: Record<string, Record<string, unknown>>;
  random_seed: number | "";
  auth_method_id: AuthMethodId;
  username: string;
  password: string;
  token: string;
  auth_header_name: string;
  auth_header_prefix: string;
  clear_password: boolean;
  clear_token: boolean;
  clear_oauth_secret: boolean;
  inbound_auth_method_id: InboundAuthMethodId;
  inbound_api_key_header: string;
  inbound_api_key_query_param: string;
  inbound_api_key_prefix: string;
  vendor_options: Record<string, string | number | boolean>;
  inbound_token: string;
  inbound_dataset_size: number;
  inbound_item_interval_seconds: number;
  inbound_default_page_size: number;
  inbound_max_page_size: number;
  inbound_fault_enabled: boolean;
  inbound_fault_response_status: number | "";
  inbound_fault_delay_ms: number;
  inbound_fault_force_empty: boolean;
  inbound_fault_malformed_json: boolean;
  inbound_fault_pagination_inconsistent: boolean;
  oauth_client_id: string;
  oauth_client_secret: string;
  oauth_token_ttl_seconds: number;
  oauth_allowed_scopes: string;
  oauth_fault_enabled: boolean;
  oauth_fault_invalid_client: boolean;
  oauth_fault_token_endpoint_failure: boolean;
  oauth_fault_token_endpoint_status: number | "";
  oauth_fault_wrong_scope: boolean;
  oauth_fault_reject_tokens_as_expired: boolean;
  schedule_type: ScheduleType;
  interval_seconds: number;
  event_count: number;
  fault_enabled: boolean;
  fault_remove_timestamp: boolean;
  fault_invalid_timestamp: boolean;
  fault_timestamp_mode: "current" | "fixed" | "offset";
  fault_timestamp_fixed_value: string;
  fault_timestamp_field_paths: string;
  fault_offset_amount: number;
  fault_offset_unit: "minutes" | "hours" | "days";
  fault_offset_direction: "past" | "future";
  fault_remove_fields: string;
  fault_null_fields: string;
  fault_extra_field_key: string;
  fault_extra_field_value: string;
  fault_large_field_path: string;
  fault_large_field_size_kb: number;
  fault_malformed_json: boolean;
  fault_duplicate_mode: DuplicateMode;
  fault_source_event_id: string;
  fault_correlation_id: string;
  fault_pre_delay_ms: number;
  fault_timeout_seconds: number;
  fault_duplicate_send_count: number;
  fault_retry_count: number;
  fault_retry_delay_ms: number;
}

const FAULT_FORM_FIELDS: { [K in keyof FaultControlsState]: keyof FormState } = {
  enabled: "fault_enabled",
  removeTimestamp: "fault_remove_timestamp",
  invalidTimestamp: "fault_invalid_timestamp",
  malformedJson: "fault_malformed_json",
  timestampMode: "fault_timestamp_mode",
  timestampFixedValue: "fault_timestamp_fixed_value",
  timestampFieldPaths: "fault_timestamp_field_paths",
  offsetAmount: "fault_offset_amount",
  offsetUnit: "fault_offset_unit",
  offsetDirection: "fault_offset_direction",
  removeFields: "fault_remove_fields",
  nullFields: "fault_null_fields",
  extraFieldKey: "fault_extra_field_key",
  extraFieldValue: "fault_extra_field_value",
  largeFieldPath: "fault_large_field_path",
  largeFieldSizeKb: "fault_large_field_size_kb",
  duplicateMode: "fault_duplicate_mode",
  sourceEventId: "fault_source_event_id",
  preDelayMs: "fault_pre_delay_ms",
  timeoutSeconds: "fault_timeout_seconds",
  duplicateSendCount: "fault_duplicate_send_count",
  retryCount: "fault_retry_count",
  retryDelayMs: "fault_retry_delay_ms",
};

const DEFAULT_FORM: FormState = {
  name: "",
  product_id: "",
  scenario_ids: [],
  simulation_mode: "push_webhook",
  fidelity_mode: "troubleshooting",
  destination: {
    transport_id: "http_webhook",
    url: "",
    method: "POST",
    headers: [],
    query_params: [],
    timeout_seconds: 30,
    verify_tls: true,
    follow_redirects: true,
    host: "127.0.0.1",
    port: 514,
    protocol: "udp",
    format: "rfc5424",
    facility: 16,
    severity: 6,
    app_name: "integration-simulator",
    proc_id: "-",
    msg_id: "-",
    tcp_framing: "newline",
    rate_limit_per_second: null,
  },
  scenario_overrides: {},
  random_seed: "",
  auth_method_id: "none",
  username: "",
  password: "",
  token: "",
  auth_header_name: "X-Api-Key",
  auth_header_prefix: "",
  clear_password: false,
  clear_token: false,
  clear_oauth_secret: false,
  inbound_auth_method_id: "none",
  inbound_api_key_header: "X-Api-Key",
  inbound_api_key_query_param: "",
  inbound_api_key_prefix: "",
  vendor_options: {},
  inbound_token: "",
  inbound_dataset_size: 100,
  inbound_item_interval_seconds: 60,
  inbound_default_page_size: 50,
  inbound_max_page_size: 100,
  inbound_fault_enabled: false,
  inbound_fault_response_status: "",
  inbound_fault_delay_ms: 0,
  inbound_fault_force_empty: false,
  inbound_fault_malformed_json: false,
  inbound_fault_pagination_inconsistent: false,
  oauth_client_id: "",
  oauth_client_secret: "",
  oauth_token_ttl_seconds: 3600,
  oauth_allowed_scopes: "",
  oauth_fault_enabled: false,
  oauth_fault_invalid_client: false,
  oauth_fault_token_endpoint_failure: false,
  oauth_fault_token_endpoint_status: "",
  oauth_fault_wrong_scope: false,
  oauth_fault_reject_tokens_as_expired: false,
  schedule_type: "manual",
  interval_seconds: 10,
  event_count: 100,
  fault_enabled: false,
  fault_remove_timestamp: false,
  fault_invalid_timestamp: false,
  fault_timestamp_mode: "current",
  fault_timestamp_fixed_value: "",
  fault_timestamp_field_paths: "",
  fault_offset_amount: 7,
  fault_offset_unit: "days",
  fault_offset_direction: "past",
  fault_remove_fields: "",
  fault_null_fields: "",
  fault_extra_field_key: "",
  fault_extra_field_value: "",
  fault_large_field_path: "",
  fault_large_field_size_kb: 64,
  fault_malformed_json: false,
  fault_duplicate_mode: "none",
  fault_source_event_id: "",
  fault_correlation_id: "",
  fault_pre_delay_ms: 0,
  fault_timeout_seconds: 30,
  fault_duplicate_send_count: 1,
  fault_retry_count: 0,
  fault_retry_delay_ms: 0,
};

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function cleanConfiguredValues(values: ConfiguredValue[] = []): ConfiguredValue[] {
  return values
    .filter((entry) => entry.name.trim())
    .map((entry) => {
      const clean: ConfiguredValue = {
        name: entry.name.trim(),
        sensitive: entry.sensitive,
      };
      if (entry.value !== undefined && (entry.value !== "" || !entry.sensitive)) {
        clean.value = entry.value;
      }
      return clean;
    });
}

function configuredValuesToMap(values: ConfiguredValue[] = []): Record<string, string> {
  return Object.fromEntries(
    values
      .filter((entry) => entry.name.trim() && entry.value !== undefined)
      .map((entry) => [entry.name.trim(), entry.value ?? ""]),
  );
}

function toSimulationUpdate(payload: SimulationCreate): SimulationUpdate {
  const updatePayload: Record<string, unknown> = { ...payload };
  delete updatePayload.product_id;
  return updatePayload as SimulationUpdate;
}

function buildFaultConfig(form: FormState): FaultConfig {
  const extra_fields: Record<string, unknown> = {};
  if (form.fault_extra_field_key.trim()) {
    extra_fields[form.fault_extra_field_key.trim()] = form.fault_extra_field_value;
  }
  return {
    enabled: form.fault_enabled,
    payload: {
      remove_timestamp: form.fault_remove_timestamp,
      invalid_timestamp: form.fault_invalid_timestamp,
      timestamp: {
        mode: form.fault_timestamp_mode,
        fixed_value: form.fault_timestamp_fixed_value || null,
        offset_amount: form.fault_offset_amount,
        offset_unit: form.fault_offset_unit,
        offset_direction: form.fault_offset_direction,
        field_paths: splitCsv(form.fault_timestamp_field_paths),
      },
      remove_fields: splitCsv(form.fault_remove_fields),
      null_fields: splitCsv(form.fault_null_fields),
      extra_fields,
      large_field_path: form.fault_large_field_path || null,
      large_field_size_kb: form.fault_large_field_size_kb,
      malformed_json: form.fault_malformed_json,
    },
    duplicate: {
      mode: form.fault_duplicate_mode,
      source_event_id: form.fault_source_event_id || null,
      correlation_id: form.fault_correlation_id || null,
    },
    delivery: {
      pre_delay_ms: form.fault_pre_delay_ms,
      timeout_seconds: form.fault_timeout_seconds || null,
      duplicate_send_count: form.fault_duplicate_send_count,
      retry_count: form.fault_retry_count,
      retry_delay_ms: form.fault_retry_delay_ms,
    },
  };
}

function simulationToForm(sim: SimulationResponse): FormState {
  const fault = sim.fault_config ?? {};
  const payload = fault.payload ?? {};
  const duplicate = fault.duplicate ?? {};
  const delivery = fault.delivery ?? {};
  const extraEntries = Object.entries(payload.extra_fields ?? {});
  return {
    name: sim.name,
    product_id: sim.product_id,
    scenario_ids: sim.scenario_ids,
    simulation_mode: (sim.simulation_mode as SimulationMode) ?? "push_webhook",
    fidelity_mode: sim.fidelity_mode as FidelityMode,
    destination: {
      transport_id: (sim.destination.transport_id ?? "http_webhook") as TransportId,
      url: sim.destination.url ?? "",
      method: sim.destination.method ?? "POST",
      headers: sim.destination.headers ?? [],
      query_params: sim.destination.query_params ?? [],
      timeout_seconds: sim.destination.timeout_seconds ?? 30,
      verify_tls: sim.destination.verify_tls ?? true,
      follow_redirects: sim.destination.follow_redirects ?? true,
      host: sim.destination.host ?? "127.0.0.1",
      port: sim.destination.port ?? 514,
      protocol: sim.destination.protocol ?? "udp",
      format: sim.destination.format ?? "rfc5424",
      facility: sim.destination.facility ?? 16,
      severity: sim.destination.severity ?? 6,
      syslog_hostname: sim.destination.syslog_hostname ?? "",
      app_name: sim.destination.app_name ?? "integration-simulator",
      proc_id: sim.destination.proc_id ?? "-",
      msg_id: sim.destination.msg_id ?? "-",
      tcp_framing: sim.destination.tcp_framing ?? "newline",
      rate_limit_per_second: sim.destination.rate_limit_per_second ?? null,
    },
    scenario_overrides: sim.scenario_overrides ?? {},
    random_seed: sim.random_seed ?? "",
    auth_method_id: sim.auth_config.auth_method_id,
    username: sim.auth_config.username ?? "",
    password: "",
    token: "",
    auth_header_name: sim.auth_config.header_name ?? "X-Api-Key",
    auth_header_prefix: sim.auth_config.header_prefix ?? "",
    clear_password: false,
    clear_token: false,
    clear_oauth_secret: false,
    inbound_auth_method_id:
      (sim.inbound_config?.auth_method_id as InboundAuthMethodId) ?? "none",
    inbound_api_key_header: sim.inbound_config?.api_key_header ?? "X-Api-Key",
    inbound_api_key_query_param: sim.inbound_config?.api_key_query_param ?? "",
    inbound_api_key_prefix: sim.inbound_config?.api_key_prefix ?? "",
    vendor_options: sim.inbound_config?.vendor_options ?? {},
    inbound_token: "",
    inbound_dataset_size: sim.inbound_config?.dataset_size ?? 100,
    inbound_item_interval_seconds: sim.inbound_config?.item_interval_seconds ?? 60,
    inbound_default_page_size: sim.inbound_config?.default_page_size ?? 50,
    inbound_max_page_size: sim.inbound_config?.max_page_size ?? 100,
    inbound_fault_enabled: sim.inbound_config?.fault_config?.enabled ?? false,
    inbound_fault_response_status:
      sim.inbound_config?.fault_config?.response_status ?? "",
    inbound_fault_delay_ms: sim.inbound_config?.fault_config?.delay_ms ?? 0,
    inbound_fault_force_empty: sim.inbound_config?.fault_config?.force_empty ?? false,
    inbound_fault_malformed_json: sim.inbound_config?.fault_config?.malformed_json ?? false,
    inbound_fault_pagination_inconsistent:
      sim.inbound_config?.fault_config?.pagination_inconsistent ?? false,
    oauth_client_id: sim.auth_config.oauth_client_id ?? "",
    oauth_client_secret: "",
    oauth_token_ttl_seconds: sim.inbound_config?.oauth_token_ttl_seconds ?? 3600,
    oauth_allowed_scopes: (sim.inbound_config?.oauth_allowed_scopes ?? []).join(", "),
    oauth_fault_enabled: sim.inbound_config?.oauth_fault_config?.enabled ?? false,
    oauth_fault_invalid_client: sim.inbound_config?.oauth_fault_config?.invalid_client ?? false,
    oauth_fault_token_endpoint_failure:
      sim.inbound_config?.oauth_fault_config?.token_endpoint_failure ?? false,
    oauth_fault_token_endpoint_status:
      sim.inbound_config?.oauth_fault_config?.token_endpoint_status ?? "",
    oauth_fault_wrong_scope: sim.inbound_config?.oauth_fault_config?.wrong_scope ?? false,
    oauth_fault_reject_tokens_as_expired:
      sim.inbound_config?.oauth_fault_config?.reject_tokens_as_expired ?? false,
    schedule_type: (sim.schedule?.type as ScheduleType) ?? "manual",
    interval_seconds: sim.schedule?.interval_seconds ?? 10,
    event_count: sim.schedule?.event_count ?? 100,
    fault_enabled: fault.enabled ?? false,
    fault_remove_timestamp: payload.remove_timestamp ?? false,
    fault_invalid_timestamp: payload.invalid_timestamp ?? false,
    fault_timestamp_mode: payload.timestamp?.mode ?? "current",
    fault_timestamp_fixed_value: payload.timestamp?.fixed_value ?? "",
    fault_timestamp_field_paths: (payload.timestamp?.field_paths ?? []).join(", "),
    fault_offset_amount: payload.timestamp?.offset_amount ?? 7,
    fault_offset_unit: payload.timestamp?.offset_unit ?? "days",
    fault_offset_direction: payload.timestamp?.offset_direction ?? "past",
    fault_remove_fields: (payload.remove_fields ?? []).join(", "),
    fault_null_fields: (payload.null_fields ?? []).join(", "),
    fault_extra_field_key: extraEntries[0]?.[0] ?? "",
    fault_extra_field_value: String(extraEntries[0]?.[1] ?? ""),
    fault_large_field_path: payload.large_field_path ?? "",
    fault_large_field_size_kb: payload.large_field_size_kb ?? 64,
    fault_malformed_json: payload.malformed_json ?? false,
    fault_duplicate_mode: duplicate.mode ?? "none",
    fault_source_event_id: duplicate.source_event_id ?? "",
    fault_correlation_id: duplicate.correlation_id ?? "",
    fault_pre_delay_ms: delivery.pre_delay_ms ?? 0,
    fault_timeout_seconds: delivery.timeout_seconds ?? 30,
    fault_duplicate_send_count: delivery.duplicate_send_count ?? 1,
    fault_retry_count: delivery.retry_count ?? 0,
    fault_retry_delay_ms: delivery.retry_delay_ms ?? 0,
  };
}

export function SimulationFormPage() {
  const { id } = useParams();
  const isEdit = Boolean(id);
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const { products, productDetail, catalogError } = useProductCatalog(form.product_id);
  const [hasPassword, setHasPassword] = useState(false);
  const [hasToken, setHasToken] = useState(false);
  const [hasOAuthSecret, setHasOAuthSecret] = useState(false);
  const [missingSecrets, setMissingSecrets] = useState<string[]>([]);
  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    if (!isEdit || !id) return;
    void getSimulation(id)
      .then((sim) => {
        setForm(simulationToForm(sim));
        setHasPassword(sim.auth_config.has_password);
        setHasToken(sim.auth_config.has_token);
        setHasOAuthSecret(Boolean(sim.auth_config.has_oauth_client_secret));
        setMissingSecrets(sim.missing_secrets ?? []);
      })
      .catch((err) => setError(formatApiError(err)))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  useEffect(() => {
    if (catalogError) setError(catalogError);
  }, [catalogError]);

  useEffect(() => {
    if (!productDetail) return;
    setForm((previous) => ({
      ...previous,
      vendor_options:
        Object.keys(previous.vendor_options).length > 0
          ? previous.vendor_options
          : defaultsFromSchema(productDetail.inbound_options_schema),
    }));
  }, [productDetail]);

  const authMethods = useMemo<AuthMethodId[]>(
    () => productDetail?.supported_auth_methods ?? ["none"],
    [productDetail],
  );

  const supportedTransports = useMemo(
    () => productDetail?.supported_transports ?? ["http_webhook"],
    [productDetail],
  );

  const supportedModes = useMemo(
    () => productDetail?.supported_modes ?? ["push_webhook"],
    [productDetail],
  );

  const inboundAuthMethods = useMemo<InboundAuthMethodId[]>(
    () => productDetail?.supported_inbound_auth_methods ?? ["none"],
    [productDetail],
  );

  const isPull = form.simulation_mode === "pull_api";
  const isSyslog = !isPull && form.destination.transport_id === "syslog";

  useEffect(() => {
    if (!productDetail) return;
    const defaultTransport = productDetail.supported_transports[0] as TransportId;
    setForm((prev) => {
      if (prev.product_id !== productDetail.id) {
        return prev;
      }
      if (prev.destination.transport_id === defaultTransport) {
        return prev;
      }
      if (!productDetail.supported_transports.includes(prev.destination.transport_id ?? "http_webhook")) {
        return {
          ...prev,
          destination: { ...prev.destination, transport_id: defaultTransport },
        };
      }
      return prev;
    });
  }, [productDetail]);

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleScenario = (scenarioId: string) => {
    setForm((prev) => {
      const selected = prev.scenario_ids.includes(scenarioId)
        ? prev.scenario_ids.filter((s) => s !== scenarioId)
        : [...prev.scenario_ids, scenarioId];
      return { ...prev, scenario_ids: selected };
    });
  };

  const buildPayload = useCallback((): SimulationCreate => {
    const inbound_config: InboundConfig = {
      auth_method_id: form.inbound_auth_method_id,
      api_key_header: form.inbound_api_key_header,
      api_key_query_param: form.inbound_api_key_query_param || null,
      api_key_prefix: form.inbound_api_key_prefix,
      vendor_options: form.vendor_options,
      dataset_size: form.inbound_dataset_size,
      item_interval_seconds: form.inbound_item_interval_seconds,
      default_page_size: form.inbound_default_page_size,
      max_page_size: form.inbound_max_page_size,
      fault_config: {
        enabled: form.inbound_fault_enabled,
        response_status: form.inbound_fault_response_status || null,
        delay_ms: form.inbound_fault_delay_ms,
        force_empty: form.inbound_fault_force_empty,
        malformed_json: form.inbound_fault_malformed_json,
        pagination_inconsistent: form.inbound_fault_pagination_inconsistent,
      },
      oauth_token_ttl_seconds: form.oauth_token_ttl_seconds,
      oauth_allowed_scopes: splitCsv(form.oauth_allowed_scopes),
      oauth_fault_config: {
        enabled: form.oauth_fault_enabled,
        invalid_client: form.oauth_fault_invalid_client,
        token_endpoint_failure: form.oauth_fault_token_endpoint_failure,
        token_endpoint_status: form.oauth_fault_token_endpoint_status || null,
        wrong_scope: form.oauth_fault_wrong_scope,
        reject_tokens_as_expired: form.oauth_fault_reject_tokens_as_expired,
      },
    };

    const auth_config: Record<string, unknown> = isPull
      ? { auth_method_id: "none" }
      : { auth_method_id: form.auth_method_id };

    if (isPull) {
      if (form.inbound_auth_method_id === "basic") {
        auth_config.auth_method_id = "basic";
        auth_config.username = form.username;
        if (form.clear_password) auth_config.password = null;
        else if (form.password) auth_config.password = form.password;
      } else if (form.inbound_auth_method_id === "bearer") {
        auth_config.auth_method_id = "bearer";
        if (form.clear_token) auth_config.token = null;
        else if (form.inbound_token) auth_config.token = form.inbound_token;
      } else if (form.inbound_auth_method_id === "api_key") {
        auth_config.auth_method_id = "api_key_header";
        if (form.clear_token) auth_config.token = null;
        else if (form.inbound_token) auth_config.token = form.inbound_token;
      } else if (form.inbound_auth_method_id === "oauth2_client_credentials") {
        auth_config.oauth_client_id = form.oauth_client_id;
        if (form.clear_oauth_secret) {
          auth_config.oauth_client_secret = null;
        } else if (form.oauth_client_secret) {
          auth_config.oauth_client_secret = form.oauth_client_secret;
        }
      }
    } else if (form.auth_method_id === "basic") {
      auth_config.username = form.username;
      if (form.clear_password) auth_config.password = null;
      else if (form.password) auth_config.password = form.password;
    } else if (form.auth_method_id === "bearer") {
      if (form.clear_token) auth_config.token = null;
      else if (form.token) auth_config.token = form.token;
    } else if (form.auth_method_id === "api_key_header") {
      auth_config.header_name = form.auth_header_name;
      auth_config.header_prefix = form.auth_header_prefix;
      if (form.clear_token) auth_config.token = null;
      else if (form.token) auth_config.token = form.token;
    }

    const schedule: ScheduleConfig = { type: form.schedule_type };
    if (form.schedule_type !== "manual") {
      schedule.interval_seconds = form.interval_seconds;
    }
    if (form.schedule_type === "finite") {
      schedule.event_count = form.event_count;
    }

    return {
      name: form.name,
      product_id: form.product_id,
      scenario_ids: form.scenario_ids,
      simulation_mode: form.simulation_mode,
      fidelity_mode: form.fidelity_mode,
      destination: {
        ...form.destination,
        headers: cleanConfiguredValues(form.destination.headers),
        query_params: cleanConfiguredValues(form.destination.query_params),
      },
      auth_config: auth_config as AuthConfigInput,
      schedule,
      scenario_overrides: Object.fromEntries(
        form.scenario_ids.map((scenarioId) => [
          scenarioId,
          form.scenario_overrides[scenarioId] ?? {},
        ]),
      ),
      random_seed: form.random_seed === "" ? null : form.random_seed,
      fault_config: buildFaultConfig(form),
      inbound_config,
    };
  }, [form, isPull]);

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      if (isSyslog) {
        const result = await testSyslogConnection({
          host: form.destination.host ?? "127.0.0.1",
          port: form.destination.port,
          protocol: form.destination.protocol,
          format: form.destination.format,
          facility: form.destination.facility,
          severity: form.destination.severity,
          syslog_hostname: form.destination.syslog_hostname || null,
          app_name: form.destination.app_name,
          proc_id: form.destination.proc_id,
          msg_id: form.destination.msg_id,
          tcp_framing: form.destination.tcp_framing,
          rate_limit_per_second: form.destination.rate_limit_per_second,
          timeout_seconds: form.destination.timeout_seconds,
          verify_tls: form.destination.verify_tls,
        });
        setTestResult(
          result.success
            ? `${result.method} OK (${result.latency_ms} ms) — ${result.delivery_note ?? "connection test succeeded"}`
            : `Connection failed — ${result.error_message ?? result.error_category}`,
        );
        return;
      }

      const auth_config: Record<string, unknown> = { auth_method_id: form.auth_method_id };
      if (form.auth_method_id === "basic") {
        auth_config.username = form.username;
        if (form.password) auth_config.password = form.password;
      } else if (form.auth_method_id === "bearer" && form.token) {
        auth_config.token = form.token;
      } else if (form.auth_method_id === "api_key_header" && form.token) {
        auth_config.token = form.token;
        auth_config.header_name = form.auth_header_name;
        auth_config.header_prefix = form.auth_header_prefix;
      }
      const result = await testHttpConnection({
        url: form.destination.url ?? "",
        method: "HEAD",
        headers: configuredValuesToMap(form.destination.headers),
        query_params: configuredValuesToMap(form.destination.query_params),
        sensitive_header_names: (form.destination.headers ?? [])
          .filter((entry) => entry.sensitive)
          .map((entry) => entry.name.trim())
          .filter(Boolean),
        sensitive_query_names: (form.destination.query_params ?? [])
          .filter((entry) => entry.sensitive)
          .map((entry) => entry.name.trim())
          .filter(Boolean),
        auth_config: auth_config as never,
        timeout_seconds: form.destination.timeout_seconds,
        verify_tls: form.destination.verify_tls,
        follow_redirects: form.destination.follow_redirects,
      });
      setTestResult(
        result.success
          ? `Connection OK — HTTP ${result.response_status_code} (${result.latency_ms} ms)`
          : `Connection failed — ${result.error_message ?? result.error_category}`,
      );
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setTesting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = buildPayload();
      const saved = isEdit && id
        ? await updateSimulation(id, toSimulationUpdate(payload))
        : await createSimulation(payload);
      navigate(`/simulations/${saved.id}`);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingState label="Loading simulation…" />;

  return (
    <div>
      <div className="page-header">
        <h1>{isEdit ? "Edit Simulation" : "New Simulation"}</h1>
        <Link to="/" className="btn">
          Cancel
        </Link>
      </div>

      {error ? <ErrorAlert message={error} /> : null}
      {testResult ? <InfoAlert message={testResult} /> : null}
      {missingSecrets.length ? (
        <ErrorAlert
          message={`Credentials required before Start/Send: ${missingSecrets.join(", ")}`}
        />
      ) : null}

      <form onSubmit={(e) => void handleSubmit(e)} className="card">
        <div className="form-grid">
          <div className="form-row">
            <label htmlFor="name">Simulation name</label>
            <input
              id="name"
              required
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
            />
          </div>

          <div className="grid-2">
            <div className="form-row">
              <label htmlFor="product">Product</label>
              <select
                id="product"
                required
                value={form.product_id}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    product_id: e.target.value,
                    scenario_ids: [],
                    vendor_options: {},
                    simulation_mode: products.find((p) => p.id === e.target.value)
                      ?.supported_modes.includes("pull_api") &&
                    !products.find((p) => p.id === e.target.value)?.supported_modes.includes(
                      "push_webhook",
                    )
                      ? "pull_api"
                      : prev.simulation_mode,
                  }))
                }
              >
                <option value="">Select product…</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <label htmlFor="fidelity">Fidelity mode</label>
              <select
                id="fidelity"
                value={form.fidelity_mode}
                onChange={(e) => update("fidelity_mode", e.target.value as FidelityMode)}
              >
                <option value="troubleshooting">Troubleshooting (with diagnostics)</option>
                <option value="vendor_accurate">Vendor accurate</option>
              </select>
            </div>
          </div>

          {supportedModes.length > 1 ? (
            <div className="form-row">
              <label htmlFor="simulation-mode">Simulation mode</label>
              <select
                id="simulation-mode"
                value={form.simulation_mode}
                onChange={(e) => update("simulation_mode", e.target.value as SimulationMode)}
              >
                {supportedModes.includes("push_webhook") ? (
                  <option value="push_webhook">Push webhook (simulator sends events)</option>
                ) : null}
                {supportedModes.includes("pull_api") ? (
                  <option value="pull_api">Pull API (collector polls simulator)</option>
                ) : null}
              </select>
            </div>
          ) : null}

          {productDetail ? (
            <ScenarioSelectionSection
              scenarios={productDetail.scenarios}
              selectedIds={form.scenario_ids}
              onToggle={toggleScenario}
            />
          ) : null}

          {productDetail ? (
            <ScenarioOverridesSection
              scenarios={productDetail.scenarios}
              selectedIds={form.scenario_ids}
              value={form.scenario_overrides}
              onChange={(scenario_overrides) => update("scenario_overrides", scenario_overrides)}
            />
          ) : null}

          <div className="form-row">
            <label htmlFor="random-seed">Random seed (optional)</label>
            <input
              id="random-seed"
              type="number"
              value={form.random_seed}
              onChange={(event) =>
                update("random_seed", event.target.value ? Number(event.target.value) : "")
              }
            />
            <span className="form-hint">
              Repeats pseudo-random scenario/plugin values by event sequence. Correlation IDs and
              actual delivery times remain unique/current.
            </span>
          </div>

          {productDetail && <p><Link to={`/guides?vendor=${productDetail.id}`}>Deployment guides for {productDetail.display_name}</Link>{productDetail.connection_profiles?.map(profile => <span key={profile.id} className="form-hint"> · {profile.display_name}</span>)}</p>}
          {!isPull ? (
            <DestinationSection
              destination={form.destination}
              supportedTransports={supportedTransports}
              authMethods={authMethods}
              auth={{
                authMethodId: form.auth_method_id,
                username: form.username,
                password: form.password,
                token: form.token,
                headerName: form.auth_header_name,
                headerPrefix: form.auth_header_prefix,
                clearPassword: form.clear_password,
                clearToken: form.clear_token,
                hasPassword,
                hasToken,
              }}
              testing={testing}
              onDestinationChange={(destination) => update("destination", destination)}
              onAuthChange={(changes) =>
                setForm((previous) => ({
                  ...previous,
                  auth_method_id: changes.authMethodId ?? previous.auth_method_id,
                  username: changes.username ?? previous.username,
                  password: changes.password ?? previous.password,
                  token: changes.token ?? previous.token,
                  auth_header_name: changes.headerName ?? previous.auth_header_name,
                  auth_header_prefix: changes.headerPrefix ?? previous.auth_header_prefix,
                  clear_password: changes.clearPassword ?? previous.clear_password,
                  clear_token: changes.clearToken ?? previous.clear_token,
                }))
              }
              onTest={() => void handleTest()}
            />
          ) : null}

          {isPull ? (
            <>
              <div className="section-title">Inbound mock API</div>
              {productDetail?.mock_routes?.length ? (
                <div className="form-row">
                  <label>Product routes</label>
                  <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                    {productDetail.mock_routes.map((route) => (
                      <li key={route.id} style={{ fontFamily: "var(--mono)", fontSize: "0.8125rem" }}>
                        {route.methods.join(", ")} /api/v1/mock/{productDetail.id}/{route.path}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <VendorOptionsSection
                schema={productDetail?.inbound_options_schema}
                value={form.vendor_options}
                onChange={(vendor_options) => update("vendor_options", vendor_options)}
              />
              <InboundAuthenticationSection
                methods={inboundAuthMethods}
                value={{
                  methodId: form.inbound_auth_method_id,
                  apiKeyHeader: form.inbound_api_key_header,
                  apiKeyQueryParam: form.inbound_api_key_query_param,
                  apiKeyPrefix: form.inbound_api_key_prefix,
                  token: form.inbound_token,
                  username: form.username,
                  password: form.password,
                  oauthClientId: form.oauth_client_id,
                  oauthClientSecret: form.oauth_client_secret,
                  oauthTokenTtlSeconds: form.oauth_token_ttl_seconds,
                  oauthAllowedScopes: form.oauth_allowed_scopes,
                  clearPassword: form.clear_password,
                  clearToken: form.clear_token,
                  clearOAuthSecret: form.clear_oauth_secret,
                  hasPassword,
                  hasToken,
                  hasOAuthSecret,
                }}
                onChange={(changes) =>
                  setForm((previous) => ({
                    ...previous,
                    inbound_auth_method_id: changes.methodId ?? previous.inbound_auth_method_id,
                    inbound_api_key_header: changes.apiKeyHeader ?? previous.inbound_api_key_header,
                    inbound_api_key_query_param:
                      changes.apiKeyQueryParam ?? previous.inbound_api_key_query_param,
                    inbound_api_key_prefix: changes.apiKeyPrefix ?? previous.inbound_api_key_prefix,
                    inbound_token: changes.token ?? previous.inbound_token,
                    username: changes.username ?? previous.username,
                    password: changes.password ?? previous.password,
                    oauth_client_id: changes.oauthClientId ?? previous.oauth_client_id,
                    oauth_client_secret:
                      changes.oauthClientSecret ?? previous.oauth_client_secret,
                    oauth_token_ttl_seconds:
                      changes.oauthTokenTtlSeconds ?? previous.oauth_token_ttl_seconds,
                    oauth_allowed_scopes:
                      changes.oauthAllowedScopes ?? previous.oauth_allowed_scopes,
                    clear_password: changes.clearPassword ?? previous.clear_password,
                    clear_token: changes.clearToken ?? previous.clear_token,
                    clear_oauth_secret:
                      changes.clearOAuthSecret ?? previous.clear_oauth_secret,
                  }))
                }
              />
              <div className="grid-2">
                <div className="form-row">
                  <label htmlFor="default-page-size">Default page size</label>
                  <input
                    id="default-page-size"
                    type="number"
                    min={1}
                    max={500}
                    value={form.inbound_default_page_size}
                    onChange={(e) => update("inbound_default_page_size", Number(e.target.value))}
                  />
                </div>
                <div className="form-row">
                  <label htmlFor="max-page-size">Max page size</label>
                  <input
                    id="max-page-size"
                    type="number"
                    min={1}
                    max={1000}
                    value={form.inbound_max_page_size}
                    onChange={(e) => update("inbound_max_page_size", Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="section-title">Materialized pull dataset</div>
              <div className="grid-2">
                <div className="form-row">
                  <label htmlFor="dataset-size">Items per route</label>
                  <input
                    id="dataset-size"
                    type="number"
                    min={1}
                    max={10000}
                    value={form.inbound_dataset_size}
                    onChange={(event) =>
                      update("inbound_dataset_size", Number(event.target.value))
                    }
                  />
                </div>
                <div className="form-row">
                  <label htmlFor="item-interval">Item interval (seconds)</label>
                  <input
                    id="item-interval"
                    type="number"
                    min={1}
                    max={86400}
                    value={form.inbound_item_interval_seconds}
                    onChange={(event) =>
                      update("inbound_item_interval_seconds", Number(event.target.value))
                    }
                  />
                </div>
              </div>
              <p className="form-hint">
                Start materializes a new finite dataset. Stop/Start replaces it; safe process
                resume retains the active dataset and its cursors.
              </p>
              <InboundFaultSection
                value={{
                  enabled: form.inbound_fault_enabled,
                  responseStatus: form.inbound_fault_response_status,
                  delayMs: form.inbound_fault_delay_ms,
                  forceEmpty: form.inbound_fault_force_empty,
                  malformedJson: form.inbound_fault_malformed_json,
                  paginationInconsistent: form.inbound_fault_pagination_inconsistent,
                  oauthEnabled: form.oauth_fault_enabled,
                  oauthInvalidClient: form.oauth_fault_invalid_client,
                  oauthTokenEndpointFailure: form.oauth_fault_token_endpoint_failure,
                  oauthWrongScope: form.oauth_fault_wrong_scope,
                  oauthRejectExpired: form.oauth_fault_reject_tokens_as_expired,
                }}
                onChange={(changes) =>
                  setForm((previous) => ({
                    ...previous,
                    inbound_fault_enabled: changes.enabled ?? previous.inbound_fault_enabled,
                    inbound_fault_response_status:
                      changes.responseStatus ?? previous.inbound_fault_response_status,
                    inbound_fault_delay_ms: changes.delayMs ?? previous.inbound_fault_delay_ms,
                    inbound_fault_force_empty:
                      changes.forceEmpty ?? previous.inbound_fault_force_empty,
                    inbound_fault_malformed_json:
                      changes.malformedJson ?? previous.inbound_fault_malformed_json,
                    inbound_fault_pagination_inconsistent:
                      changes.paginationInconsistent ??
                      previous.inbound_fault_pagination_inconsistent,
                    oauth_fault_enabled: changes.oauthEnabled ?? previous.oauth_fault_enabled,
                    oauth_fault_invalid_client:
                      changes.oauthInvalidClient ?? previous.oauth_fault_invalid_client,
                    oauth_fault_token_endpoint_failure:
                      changes.oauthTokenEndpointFailure ??
                      previous.oauth_fault_token_endpoint_failure,
                    oauth_fault_wrong_scope:
                      changes.oauthWrongScope ?? previous.oauth_fault_wrong_scope,
                    oauth_fault_reject_tokens_as_expired:
                      changes.oauthRejectExpired ??
                      previous.oauth_fault_reject_tokens_as_expired,
                  }))
                }
              />
            </>
          ) : null}

          {!isPull ? (
            <SchedulingSection
              type={form.schedule_type}
              intervalSeconds={form.interval_seconds}
              eventCount={form.event_count}
              onTypeChange={(schedule_type) => update("schedule_type", schedule_type)}
              onIntervalChange={(interval_seconds) =>
                update("interval_seconds", interval_seconds)
              }
              onEventCountChange={(event_count) => update("event_count", event_count)}
            />
          ) : null}

          {!isPull ? (
            <FaultControlsSection
              value={{
                enabled: form.fault_enabled,
                removeTimestamp: form.fault_remove_timestamp,
                invalidTimestamp: form.fault_invalid_timestamp,
                malformedJson: form.fault_malformed_json,
                timestampMode: form.fault_timestamp_mode,
                timestampFixedValue: form.fault_timestamp_fixed_value,
                timestampFieldPaths: form.fault_timestamp_field_paths,
                offsetAmount: form.fault_offset_amount,
                offsetUnit: form.fault_offset_unit,
                offsetDirection: form.fault_offset_direction,
                removeFields: form.fault_remove_fields,
                nullFields: form.fault_null_fields,
                extraFieldKey: form.fault_extra_field_key,
                extraFieldValue: form.fault_extra_field_value,
                largeFieldPath: form.fault_large_field_path,
                largeFieldSizeKb: form.fault_large_field_size_kb,
                duplicateMode: form.fault_duplicate_mode,
                sourceEventId: form.fault_source_event_id,
                preDelayMs: form.fault_pre_delay_ms,
                timeoutSeconds: form.fault_timeout_seconds,
                duplicateSendCount: form.fault_duplicate_send_count,
                retryCount: form.fault_retry_count,
                retryDelayMs: form.fault_retry_delay_ms,
              }}
              onChange={(key, value) =>
                setForm((previous) => ({
                  ...previous,
                  [FAULT_FORM_FIELDS[key]]: value,
                }))
              }
            />
          ) : null}

          <div className="page-actions" style={{ marginTop: "1rem" }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={saving || form.scenario_ids.length === 0}
            >
              {saving ? "Saving…" : isEdit ? "Save changes" : "Create simulation"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
