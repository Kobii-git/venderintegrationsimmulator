import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { del, get, post, request } from "../api/client";
import { getProduct, listProducts } from "../api/products";
import {
  createSimulation,
  getSimulation,
  updateSimulation,
} from "../api/simulations";
import { AzureDestinationEditor } from "../components/AzureDestinationEditor";
import { ErrorAlert } from "../components/ErrorAlert";
import { StructuredValueEditor } from "../components/StructuredValueEditor";
import { ScenarioOverridesSection } from "../components/ScenarioOverridesSection";
import type {
  AuthMethodId,
  Dataset,
  DestinationConfig,
  ProductDetail,
  ProductSummary,
  ReplayConfig,
  ScheduleConfig,
  SimulatedDevice,
  TargetInput,
  TargetResponse,
  TransportId,
} from "../types/api";
import { formatApiError } from "../utils/format";
import { createUuid } from "../utils/uuid";

const newTarget = (): TargetInput => ({
  id: createUuid(),
  name: "Collector",
  enabled: true,
  payload_format: "default",
  device_ids: [],
  scenario_ids: [],
  queue_limit: 10000,
  destination: {
    transport_id: "syslog",
    host: "",
    port: 514,
    protocol: "udp",
    format: "rfc5424",
    app_name: "log-simulator",
    tcp_framing: "newline",
    verify_tls: true,
    timeout_seconds: 10,
  },
  auth_config: { auth_method_id: "none" },
});
function editable(t: TargetResponse): TargetInput {
  return {
    id: t.id,
    name: t.name,
    enabled: t.enabled,
    destination: {
      ...t.destination,
      headers: t.destination.headers?.map((v) => ({
        name: v.name,
        value: v.value,
        sensitive: v.sensitive,
      })),
      query_params: t.destination.query_params?.map((v) => ({
        name: v.name,
        value: v.value,
        sensitive: v.sensitive,
      })),
    },
    payload_format: t.payload_format,
    device_ids: t.device_ids,
    scenario_ids: t.scenario_ids,
    queue_limit: t.queue_limit,
    auth_config: {
      auth_method_id: t.auth_config.auth_method_id,
      username: t.auth_config.username,
      header_name: t.auth_config.header_name,
      header_prefix: t.auth_config.header_prefix,
      oauth_client_id: t.auth_config.oauth_client_id,
    },
  };
}

export function LogLabPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [productId, setProductId] = useState("");
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("Sentinel lab");
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<
    Record<string, Record<string, unknown>>
  >({});
  const [targets, setTargets] = useState<TargetInput[]>(() => [newTarget()]);
  const [devices, setDevices] = useState<SimulatedDevice[]>([]);
  const [schedule, setSchedule] = useState<ScheduleConfig>({ type: "manual" });
  const [rateMode, setRateMode] = useState(true);
  const [rate, setRate] = useState(10);
  const [interval, setInterval] = useState(1);
  const [count, setCount] = useState(100);
  const [seed, setSeed] = useState(42);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [uploadFormat, setUploadFormat] = useState("ndjson");
  const [replay, setReplay] = useState<ReplayConfig>({
    dataset_id: "",
    loop: false,
    timing: "fixed",
    rewrite_timestamps: false,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    void Promise.all([listProducts(), get<Dataset[]>("/datasets")])
      .then(([p, d]) => {
        setProducts(p);
        setDatasets(d);
      })
      .catch((e) => setError(formatApiError(e)));
    if (id)
      void getSimulation(id)
        .then((s) => {
          setName(s.name);
          setProductId(s.product_id);
          setScenarios(s.scenario_ids);
          setOverrides(s.scenario_overrides);
          setTargets(s.targets?.map(editable) ?? [newTarget()]);
          setDevices(s.devices ?? []);
          setSchedule(s.schedule);
          setRateMode(s.schedule.events_per_second != null);
          setRate(s.schedule.events_per_second ?? 10);
          setInterval(s.schedule.interval_seconds ?? 1);
          setCount(s.schedule.event_count ?? 100);
          setSeed(s.random_seed ?? 42);
          if (s.replay_config && "dataset_id" in s.replay_config)
            setReplay(s.replay_config as ReplayConfig);
          setLocked(s.status === "running" || s.simulation_mode === "pull_api");
        })
        .catch((e) => setError(formatApiError(e)));
  }, [id]);
  useEffect(() => {
    if (productId)
      void getProduct(productId)
        .then(setProduct)
        .catch((e) => setError(formatApiError(e)));
  }, [productId]);
  const changeTarget = (index: number, update: Partial<TargetInput>) =>
    setTargets((ts) =>
      ts.map((t, i) => (i === index ? { ...t, ...update } : t)),
    );
  const destination = (index: number, update: Partial<DestinationConfig>) =>
    changeTarget(index, {
      destination: { ...targets[index].destination, ...update },
    });
  const formats = [
    ...new Set([
      "default",
      "json",
      ...(product?.formats ?? []),
      ...(productId === "windows-dc"
        ? ["SecurityEvent", "WindowsEvent"]
        : productId === "windows-sysmon"
          ? ["WindowsEvent"]
          : []),
      ...(product?.formats?.includes("cef") ? ["CommonSecurityLog"] : []),
    ]),
  ];
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const scheduled: ScheduleConfig =
        schedule.type === "manual"
          ? {
              ...schedule,
              type: "manual",
              events_per_second: null,
              interval_seconds: null,
              event_count: null,
            }
          : {
              ...schedule,
              ...(rateMode
                ? { events_per_second: rate, interval_seconds: null }
                : { interval_seconds: interval, events_per_second: null }),
              event_count: schedule.type === "finite" ? count : null,
            };
      const data = {
        name,
        scenario_ids: scenarios,
        targets,
        devices,
        scenario_overrides: overrides,
        schedule: {
          ...scheduled,
          user_pool: scheduled.user_pool?.filter((name) => name.trim()),
          scenario_weights: Object.fromEntries(
            Object.entries(scheduled.scenario_weights ?? {}).filter(
              ([scenarioId]) => scenarios.includes(scenarioId),
            ),
          ),
        },
        random_seed: seed,
        replay_config: replay.dataset_id ? replay : {},
      };
      const result = id
        ? await updateSimulation(id, data)
        : await createSimulation({
            ...data,
            product_id: productId,
            fidelity_mode: "vendor_accurate",
          });
      navigate(`/simulations/${result.id}`);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  const upload = async (file: File) => {
    setBusy(true);
    setError(null);
    try {
      const d = await request<Dataset>(
        `/datasets?name=${encodeURIComponent(file.name)}&format=${uploadFormat}`,
        {
          method: "POST",
          body: file,
          headers: { "Content-Type": "application/octet-stream" },
        },
      );
      setDatasets((ds) => [...ds, d]);
      setReplay((r) => ({ ...r, dataset_id: d.id }));
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setBusy(false);
    }
  };
  const inspectDataset = async () => {
    try {
      setPreview(
        JSON.stringify(
          await get(
            `/datasets/${replay.dataset_id}/preview?rewrite=${replay.rewrite_timestamps}`,
          ),
          null,
          2,
        ),
      );
    } catch (e) {
      setError(formatApiError(e));
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>{id ? "Edit log lab" : "Build a log lab"}</h1>
        <Link className="btn" to={id ? `/simulations/${id}` : "/"}>
          Back
        </Link>
      </div>
      <p>
        Generate synthetic events for Sentinel collectors or ingestion APIs.
        Device addresses appear in payloads; collector addresses control
        delivery.
      </p>
      {error && <ErrorAlert message={error} />}
      {locked && (
        <p>
          Stop the simulation before editing. Polling mock configuration is
          available in the original simulation editor.
        </p>
      )}
      <form onSubmit={(e) => void save(e)}>
        <fieldset disabled={busy || locked} style={{ border: 0, padding: 0 }}>
          <div className="card">
            <div className="grid-2">
              <div className="form-row">
                <label htmlFor="lab-name">Name</label>
                <input
                  id="lab-name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="form-row">
                <label htmlFor="source-search">Find a source</label>
                <input
                  id="source-search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Windows, firewall, identity…"
                />
              </div>
            </div>
            <div className="form-row">
              <label htmlFor="lab-product">Source</label>
              <select
                id="lab-product"
                required
                disabled={!!id}
                value={productId}
                onChange={(e) => {
                  setProductId(e.target.value);
                  setScenarios([]);
                  setOverrides({});
                }}
              >
                <option value="">Select source…</option>
                {products
                  .filter(
                    (p) =>
                      p.id === productId ||
                      `${p.display_name} ${p.description}`
                        .toLowerCase()
                        .includes(search.toLowerCase()),
                  )
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
              </select>
            </div>
            {product && (
              <>
                <p>
                  {product.schema_version} ·{" "}
                  {(product.formats ?? []).join(", ")}
                </p>
                <p className="form-hint">{product.compatibility}</p>
                <div>
                  {product.field_references?.map((ref) => (
                    <a key={ref} href={ref} target="_blank" rel="noreferrer">
                      Field reference{" "}
                    </a>
                  ))}
                </div>
                <div className="section-title">Event families</div>
                {product.scenarios
                  .filter(
                    (s) =>
                      !s.supported_modes?.length ||
                      s.supported_modes.includes("push_webhook"),
                  )
                  .map((s) => (
                    <label key={s.id} style={{ display: "block" }}>
                      <input
                        type="checkbox"
                        checked={scenarios.includes(s.id)}
                        onChange={(e) =>
                          setScenarios((ids) =>
                            e.target.checked
                              ? [...ids, s.id]
                              : ids.filter((i) => i !== s.id),
                          )
                        }
                      />{" "}
                      {s.display_name}
                    </label>
                  ))}
                <ScenarioOverridesSection
                  scenarios={product.scenarios}
                  selectedIds={scenarios}
                  value={overrides}
                  onChange={setOverrides}
                />
              </>
            )}
          </div>
          <div className="card">
            <div className="section-title">Simulated devices</div>
            {devices.map((d, i) => (
              <div className="grid-2" key={d.id}>
                <div className="form-row">
                  <label>Hostname</label>
                  <input
                    aria-label={`Device ${i + 1} hostname`}
                    required
                    value={d.hostname}
                    onChange={(e) =>
                      setDevices((ds) =>
                        ds.map((v, n) =>
                          n === i ? { ...v, hostname: e.target.value } : v,
                        ),
                      )
                    }
                  />
                </div>
                <div className="form-row">
                  <label>Device IP</label>
                  <input
                    aria-label={`Device ${i + 1} IP`}
                    required
                    value={d.ip_address}
                    onChange={(e) =>
                      setDevices((ds) =>
                        ds.map((v, n) =>
                          n === i ? { ...v, ip_address: e.target.value } : v,
                        ),
                      )
                    }
                  />
                  <button
                    type="button"
                    className="btn"
                    onClick={() =>
                      setDevices((ds) => ds.filter((_, n) => n !== i))
                    }
                  >
                    Remove device
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="btn"
              onClick={() =>
                setDevices((ds) => [
                  ...ds,
                  {
                    id: createUuid(),
                    hostname: `lab-device-${ds.length + 1}`,
                    ip_address: `192.0.2.${ds.length + 10}`,
                    vendor: productId,
                  },
                ])
              }
            >
              Add device
            </button>
          </div>
          <div className="section-title">Collectors and APIs</div>
          {targets.map((t, i) => (
            <div className="card" key={t.id}>
              <div className="grid-2">
                <div className="form-row">
                  <label>Collector name</label>
                  <input
                    aria-label={`Collector ${i + 1} name`}
                    required
                    value={t.name}
                    onChange={(e) => changeTarget(i, { name: e.target.value })}
                  />
                </div>
                <div className="form-row">
                  <label>Transport</label>
                  <select
                    aria-label={`Collector ${i + 1} transport`}
                    value={t.destination.transport_id}
                    onChange={(e) =>
                      destination(i, {
                        transport_id: e.target.value as TransportId,
                      })
                    }
                  >
                    <option value="syslog">Syslog UDP / TCP / TLS</option>
                    <option value="http_webhook">HTTP webhook</option>
                    {productId === "cloudflare" && <option value="cloudflare_logpush">Cloudflare Logpush (gzip NDJSON)</option>}
                    <option value="azure_logs_ingestion">
                      Azure Logs Ingestion API
                    </option>
                    <option value="azure_function_app">
                      Azure Function App relay
                    </option>
                  </select>
                </div>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={t.enabled}
                  onChange={(e) =>
                    changeTarget(i, { enabled: e.target.checked })
                  }
                />{" "}
                Enabled
              </label>
              <div className="form-row">
                <label>Payload format</label>
                <select
                  aria-label={`Collector ${i + 1} payload format`}
                  value={t.payload_format}
                  onChange={(e) =>
                    changeTarget(i, { payload_format: e.target.value })
                  }
                >
                  {formats.map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </div>
              {t.destination.transport_id === "syslog" ? (
                <>
                  <div className="grid-2">
                    <div className="form-row">
                      <label>Collector host / IP</label>
                      <input
                        aria-label={`Collector ${i + 1} host`}
                        required
                        value={t.destination.host ?? ""}
                        onChange={(e) =>
                          destination(i, { host: e.target.value })
                        }
                      />
                    </div>
                    <div className="form-row">
                      <label>Port</label>
                      <input
                        type="number"
                        min={1}
                        max={65535}
                        required
                        value={t.destination.port ?? 514}
                        onChange={(e) =>
                          destination(i, { port: Number(e.target.value) })
                        }
                      />
                    </div>
                  </div>
                  <div className="grid-2">
                    <div className="form-row">
                      <label>Protocol</label>
                      <select
                        value={t.destination.protocol ?? "udp"}
                        onChange={(e) =>
                          destination(i, {
                            protocol: e.target.value as "udp" | "tcp" | "tls",
                          })
                        }
                      >
                        <option>udp</option>
                        <option>tcp</option>
                        <option>tls</option>
                      </select>
                    </div>
                    <div className="form-row">
                      <label>Envelope</label>
                      <select
                        value={t.destination.format ?? "rfc5424"}
                        onChange={(e) =>
                          destination(i, {
                            format: e.target.value as
                              "rfc5424" | "rfc3164" | "raw",
                          })
                        }
                      >
                        <option>rfc5424</option>
                        <option>rfc3164</option>
                        <option>raw</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-row">
                    <label>TCP framing</label>
                    <select
                      value={t.destination.tcp_framing ?? "newline"}
                      onChange={(e) =>
                        destination(i, {
                          tcp_framing: e.target.value as
                            "newline" | "octet_counting",
                        })
                      }
                    >
                      <option value="newline">Newline</option>
                      <option value="octet_counting">
                        Octet counting (supports embedded newlines)
                      </option>
                    </select>
                  </div>
                </>
              ) : ["http_webhook", "cloudflare_logpush"].includes(t.destination.transport_id ?? "http_webhook") ? (
                <>
                  <div className="form-row">
                    <label>URL</label>
                    <input
                      type="url"
                      required
                      value={t.destination.url ?? ""}
                      onChange={(e) => destination(i, { url: e.target.value })}
                    />
                  </div>
                  <StructuredValueEditor
                    label="Headers"
                    value={t.destination.headers ?? []}
                    onChange={(v) => destination(i, { headers: v })}
                  />
                  <StructuredValueEditor
                    label="Query parameters"
                    value={t.destination.query_params ?? []}
                    onChange={(v) => destination(i, { query_params: v })}
                  />
                  <div className="form-row">
                    <label>Authentication</label>
                    <select
                      value={t.auth_config.auth_method_id}
                      onChange={(e) =>
                        changeTarget(i, {
                          auth_config: {
                            ...t.auth_config,
                            auth_method_id: e.target.value as AuthMethodId,
                          },
                        })
                      }
                    >
                      {["none", "basic", "bearer", "api_key_header"].map(
                        (a) => (
                          <option key={a}>{a}</option>
                        ),
                      )}
                    </select>
                  </div>
                  {t.auth_config.auth_method_id === "basic" ? (
                    <div className="grid-2">
                      <input
                        aria-label="Username"
                        placeholder="Username"
                        value={t.auth_config.username ?? ""}
                        onChange={(e) =>
                          changeTarget(i, {
                            auth_config: {
                              ...t.auth_config,
                              username: e.target.value,
                            },
                          })
                        }
                      />
                      <input
                        type="password"
                        aria-label="Password"
                        placeholder="Blank keeps stored password"
                        value={t.auth_config.password ?? ""}
                        onChange={(e) =>
                          changeTarget(i, {
                            auth_config: {
                              ...t.auth_config,
                              password: e.target.value || undefined,
                            },
                          })
                        }
                      />
                    </div>
                  ) : t.auth_config.auth_method_id !== "none" ? (
                    <>
                      <input
                        type="password"
                        aria-label="Token"
                        placeholder="Blank keeps stored token"
                        value={t.auth_config.token ?? ""}
                        onChange={(e) =>
                          changeTarget(i, {
                            auth_config: {
                              ...t.auth_config,
                              token: e.target.value || undefined,
                            },
                          })
                        }
                      />
                      {t.auth_config.auth_method_id === "api_key_header" && (
                        <input
                          aria-label="API key header"
                          placeholder="X-API-Key"
                          value={t.auth_config.header_name ?? ""}
                          onChange={(e) =>
                            changeTarget(i, {
                              auth_config: {
                                ...t.auth_config,
                                header_name: e.target.value,
                              },
                            })
                          }
                        />
                      )}
                    </>
                  ) : null}
                </>
              ) : (
                <AzureDestinationEditor
                  destination={t.destination}
                  auth={t.auth_config}
                  onChange={(d, a) =>
                    changeTarget(i, { destination: d, auth_config: a })
                  }
                />
              )}
              <div className="grid-2">
                <div className="form-row">
                  <label>Timeout (seconds)</label>
                  <input
                    type="number"
                    min={1}
                    max={300}
                    value={t.destination.timeout_seconds ?? 30}
                    onChange={(e) =>
                      destination(i, {
                        timeout_seconds: Number(e.target.value),
                      })
                    }
                  />
                </div>
                <div className="form-row">
                  <label>Queue capacity (events)</label>
                  <input
                    type="number"
                    min={1}
                    max={100000}
                    value={t.queue_limit}
                    onChange={(e) =>
                      changeTarget(i, { queue_limit: Number(e.target.value) })
                    }
                  />
                </div>
              </div>
              <label>
                <input
                  type="checkbox"
                  checked={t.destination.verify_tls ?? true}
                  onChange={(e) =>
                    destination(i, { verify_tls: e.target.checked })
                  }
                />{" "}
                Verify TLS certificate
              </label>
              <div className="form-row">
                <label>Mounted CA file (optional)</label>
                <input
                  placeholder="/certs/collector-ca.pem"
                  value={t.destination.ca_file ?? ""}
                  onChange={(e) =>
                    destination(i, { ca_file: e.target.value || null })
                  }
                />
              </div>
              <div className="grid-2">
                <div className="form-row">
                  <label>Device filter (empty selects all)</label>
                  <select
                    multiple
                    value={t.device_ids}
                    onChange={(e) =>
                      changeTarget(i, {
                        device_ids: Array.from(
                          e.target.selectedOptions,
                          (o) => o.value,
                        ),
                      })
                    }
                  >
                    {devices.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.hostname}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-row">
                  <label>Scenario filter (empty selects all)</label>
                  <select
                    multiple
                    value={t.scenario_ids}
                    onChange={(e) =>
                      changeTarget(i, {
                        scenario_ids: Array.from(
                          e.target.selectedOptions,
                          (o) => o.value,
                        ),
                      })
                    }
                  >
                    {scenarios.map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>
              {id && (
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    void post(
                      `/simulations/${id}/wire-preview?target_id=${encodeURIComponent(t.id)}`,
                    )
                      .then((v) => setPreview(JSON.stringify(v, null, 2)))
                      .catch((e) => setError(formatApiError(e)));
                  }}
                >
                  Preview saved wire bytes
                </button>
              )}{" "}
              <button
                type="button"
                className="btn"
                disabled={targets.length === 1}
                onClick={() => setTargets((ts) => ts.filter((_, n) => n !== i))}
              >
                Remove collector
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn"
            disabled={targets.length >= 16}
            onClick={() => setTargets((ts) => [...ts, newTarget()])}
          >
            Add collector
          </button>
          <div className="card">
            <div className="section-title">Traffic</div>
            <div className="form-row">
              <label>Schedule</label>
              <select
                value={schedule.type}
                onChange={(e) =>
                  setSchedule((s) => ({
                    ...s,
                    type: e.target.value as ScheduleConfig["type"],
                  }))
                }
              >
                <option value="manual">Manual send</option>
                <option value="continuous">Continuous</option>
                <option value="finite">Finite</option>
              </select>
            </div>
            {schedule.type !== "manual" && (
              <>
                <label>
                  <input
                    type="checkbox"
                    checked={rateMode}
                    onChange={(e) => setRateMode(e.target.checked)}
                  />{" "}
                  Generate at an event rate
                </label>
                <div className="form-row">
                  <label>
                    {rateMode
                      ? "Events per second (100 combined maximum)"
                      : "Interval (seconds)"}
                  </label>
                  <input
                    type="number"
                    required
                    min={rateMode ? 0.1 : 1}
                    max={rateMode ? 100 : 86400}
                    step={rateMode ? 0.1 : 1}
                    value={rateMode ? rate : interval}
                    onChange={(e) =>
                      rateMode
                        ? setRate(Number(e.target.value))
                        : setInterval(Number(e.target.value))
                    }
                  />
                </div>
                {schedule.type === "finite" && (
                  <div className="form-row">
                    <label>Event count</label>
                    <input
                      type="number"
                      min={1}
                      max={10000}
                      value={count}
                      onChange={(e) => setCount(Number(e.target.value))}
                    />
                  </div>
                )}
              </>
            )}
            <div className="form-row">
              <label>Random seed</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
              />
            </div>
            <div className="form-row">
              <label htmlFor="user-pool">User pool (one name per line)</label>
              <textarea
                id="user-pool"
                value={(schedule.user_pool ?? []).join("\n")}
                onChange={(e) =>
                  setSchedule((v) => ({
                    ...v,
                    user_pool: e.target.value.split("\n"),
                  }))
                }
              />
            </div>
            <div className="form-row">
              <label htmlFor="incident-preset">
                Correlated incident preset
              </label>
              <select
                id="incident-preset"
                value={schedule.incident_preset ?? ""}
                onChange={(e) =>
                  setSchedule((s) => ({
                    ...s,
                    incident_preset: (e.target.value ||
                      null) as ScheduleConfig["incident_preset"],
                  }))
                }
              >
                <option value="">None</option>
                <option value="password_spray">Password spray</option>
                <option value="privileged_logon">Privileged logon</option>
                <option value="firewall_scan">Firewall scan</option>
                <option value="malware_detection">Malware detection</option>
              </select>
            </div>
            {scenarios.map((s) => (
              <div className="form-row" key={s}>
                <label>{s} weight</label>
                <input
                  type="number"
                  min={0.01}
                  step="any"
                  value={schedule.scenario_weights?.[s] ?? 1}
                  onChange={(e) =>
                    setSchedule((v) => ({
                      ...v,
                      scenario_weights: {
                        ...v.scenario_weights,
                        [s]: Number(e.target.value),
                      },
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <div className="card">
            <div className="section-title">Uploaded log replay</div>
            <div className="form-row">
              <label>Dataset</label>
              <select
                value={replay.dataset_id}
                onChange={(e) =>
                  setReplay((r) => ({ ...r, dataset_id: e.target.value }))
                }
              >
                <option value="">Generate scenario events</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.record_count} records)
                  </option>
                ))}
              </select>
            </div>
            <div className="grid-2">
              <select
                aria-label="Upload format"
                value={uploadFormat}
                onChange={(e) => setUploadFormat(e.target.value)}
              >
                {["text", "ndjson", "json", "csv"].map((f) => (
                  <option key={f}>{f}</option>
                ))}
              </select>
              <input
                aria-label="Upload log dataset"
                type="file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void upload(file);
                }}
              />
            </div>
            <p className="form-hint">
              UTF-8, up to 100 MiB. Text lines, NDJSON, JSON array, or CSV with
              a header. Unknown timestamp fields remain unchanged.
            </p>
            {replay.dataset_id && (
              <>
                <label>
                  <input
                    type="checkbox"
                    checked={replay.loop}
                    onChange={(e) =>
                      setReplay((r) => ({ ...r, loop: e.target.checked }))
                    }
                  />{" "}
                  Loop dataset
                </label>
                <div className="form-row">
                  <label>Timing</label>
                  <select
                    value={replay.timing}
                    onChange={(e) =>
                      setReplay((r) => ({
                        ...r,
                        timing: e.target.value as ReplayConfig["timing"],
                      }))
                    }
                  >
                    <option value="fixed">Configured traffic rate</option>
                    <option value="original">Original timestamp gaps</option>
                  </select>
                </div>
                <label>
                  <input
                    type="checkbox"
                    checked={replay.rewrite_timestamps}
                    onChange={(e) =>
                      setReplay((r) => ({
                        ...r,
                        rewrite_timestamps: e.target.checked,
                      }))
                    }
                  />{" "}
                  Rewrite recognized timestamps to current time
                </label>
                <div className="page-actions">
                  <button
                    type="button"
                    className="btn"
                    onClick={() => void inspectDataset()}
                  >
                    Preview dataset
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      void del(`/datasets/${replay.dataset_id}`)
                        .then(() => {
                          setDatasets((ds) =>
                            ds.filter((d) => d.id !== replay.dataset_id),
                          );
                          setReplay((r) => ({ ...r, dataset_id: "" }));
                        })
                        .catch((e) => setError(formatApiError(e)));
                    }}
                  >
                    Delete dataset
                  </button>
                </div>
              </>
            )}
          </div>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={!scenarios.length || busy || locked}
          >
            {busy ? "Saving…" : id ? "Save lab" : "Create lab"}
          </button>
        </fieldset>
      </form>
      {preview && (
        <div className="card">
          <h2>Preview</h2>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
              maxHeight: "32rem",
              overflow: "auto",
            }}
          >
            {preview}
          </pre>
        </div>
      )}
    </div>
  );
}
