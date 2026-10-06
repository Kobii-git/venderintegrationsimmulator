import { useEffect, useRef, useState } from "react";

import { generateRawLog, getProduct, listProducts } from "../api/products";
import { ErrorAlert, InfoAlert } from "../components/ErrorAlert";
import { ScenarioOverridesSection } from "../components/ScenarioOverridesSection";
import type {
  FidelityMode,
  ProductDetail,
  ProductSummary,
  ScenarioRawPreviewResponse,
} from "../types/api";
import { formatApiError } from "../utils/format";

export function RawLogPage() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [productId, setProductId] = useState("");
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [scenarioId, setScenarioId] = useState("");
  const [fidelity, setFidelity] = useState<FidelityMode>("vendor_accurate");
  const [overrides, setOverrides] = useState<
    Record<string, Record<string, unknown>>
  >({});
  const [result, setResult] = useState<ScenarioRawPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const generation = useRef(0);
  const output = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    let active = true;
    void listProducts()
      .then((catalog) => {
        if (!active) return;
        setProducts(catalog);
        setProductId(
          catalog.find((item) => item.id === "upguard")?.id ??
            catalog[0]?.id ??
            "",
        );
      })
      .catch((err) => {
        if (active) setError(formatApiError(err));
      });
    return () => {
      active = false;
      generation.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!productId) return;
    let active = true;
    void getProduct(productId)
      .then((detail) => {
        if (!active) return;
        setProduct(detail);
        setScenarioId(detail.scenarios[0]?.id ?? "");
      })
      .catch((err) => {
        if (active) setError(formatApiError(err));
      });
    return () => {
      active = false;
    };
  }, [productId]);

  const invalidate = () => {
    generation.current += 1;
    setResult(null);
    setError(null);
    setNotice(null);
    setGenerating(false);
  };

  const generate = async () => {
    if (!product || product.id !== productId || !scenarioId) return;
    invalidate();
    const requestId = generation.current;
    setGenerating(true);
    try {
      const raw = await generateRawLog(productId, scenarioId, {
        fidelity_mode: fidelity,
        scenario_overrides: overrides[scenarioId] ?? {},
      });
      if (requestId === generation.current) setResult(raw);
    } catch (err) {
      if (requestId === generation.current) setError(formatApiError(err));
    } finally {
      if (requestId === generation.current) setGenerating(false);
    }
  };

  const copy = async () => {
    if (!result) return;
    const requestId = generation.current;
    try {
      await navigator.clipboard.writeText(result.raw_log);
      if (requestId === generation.current) setNotice("Raw log copied.");
    } catch {
      output.current?.focus();
      output.current?.select();
      if (requestId === generation.current) {
        setNotice(
          "Select and copy the raw log below, or download it. Clipboard access is unavailable in this browser.",
        );
      }
    }
  };

  const download = () => {
    if (!result) return;
    const url = URL.createObjectURL(
      new Blob([result.raw_log], { type: result.content_type }),
    );
    const link = document.createElement("a");
    link.href = url;
    const extension =
      result.content_type === "application/json"
        ? "json"
        : result.content_type === "application/xml"
          ? "xml"
          : "log";
    link.download = `${result.product_id}-${result.scenario_id}.${extension}`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const ready = product?.id === productId && !!scenarioId;
  const selected = product?.scenarios.find(
    (scenario) => scenario.id === scenarioId,
  );

  return (
    <div>
      <div className="page-header">
        <h1>Generate raw log</h1>
      </div>
      <p className="form-hint">
        Generate one sample in the product’s default log format. No destination
        or saved simulation is needed; nothing is sent.
      </p>
      {error && <ErrorAlert message={error} />}
      {notice && <InfoAlert message={notice} />}
      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          void generate();
        }}
      >
        <div className="grid-2">
          <div className="form-row">
            <label htmlFor="raw-product">Product</label>
            <select
              id="raw-product"
              value={productId}
              disabled={!products.length}
              onChange={(event) => {
                invalidate();
                setProduct(null);
                setScenarioId("");
                setOverrides({});
                setProductId(event.target.value);
              }}
            >
              {!products.length && <option value="">Loading products…</option>}
              {products.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <label htmlFor="raw-scenario">Scenario</label>
            <select
              id="raw-scenario"
              value={scenarioId}
              disabled={!product}
              onChange={(event) => {
                invalidate();
                setScenarioId(event.target.value);
              }}
            >
              {!product && <option value="">Loading scenarios…</option>}
              {product?.scenarios.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.display_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        {selected?.description && (
          <p className="form-hint">{selected.description}</p>
        )}
        <div className="form-row">
          <label htmlFor="raw-fidelity">Payload mode</label>
          <select
            id="raw-fidelity"
            value={fidelity}
            onChange={(event) => {
              invalidate();
              setFidelity(event.target.value as FidelityMode);
            }}
          >
            <option value="vendor_accurate">Vendor payload</option>
            <option value="troubleshooting">
              Include simulator diagnostics
            </option>
          </select>
        </div>
        {productId === "upguard" && (
          <p className="form-hint">
            UpGuard score threshold uses a documented notification type. Data
            leak, identity breach and vulnerability schemas are inferred;
            validate them against real UpGuard samples.
          </p>
        )}
        <details key={`${productId}-${scenarioId}`}>
          <summary>Customize sample values</summary>
          <ScenarioOverridesSection
            scenarios={product?.scenarios ?? []}
            selectedIds={[scenarioId]}
            value={overrides}
            onChange={(next) => {
              invalidate();
              setOverrides(next);
            }}
          />
        </details>
        <div style={{ marginTop: "1rem" }}>
          <button
            className="btn btn-primary"
            type="submit"
            disabled={!ready || generating}
          >
            {generating ? "Generating…" : "Generate raw log"}
          </button>
        </div>
      </form>
      {result && (
        <section className="card" aria-label="Generated raw log">
          <div className="json-toolbar">
            <strong>Raw log · {result.content_type}</strong>
            <div className="inline-actions">
              <button
                className="btn btn-sm"
                type="button"
                onClick={() => void copy()}
              >
                Copy raw log
              </button>
              <button className="btn btn-sm" type="button" onClick={download}>
                Download raw log
              </button>
            </div>
          </div>
          <textarea
            ref={output}
            aria-label="Raw log output"
            className="raw-log-output"
            value={result.raw_log}
            readOnly
            spellCheck={false}
            rows={18}
          />
          <p className="form-hint">
            This is the generated body. JSON is formatted for readability;
            transport headers and framing are added during delivery.
          </p>
        </section>
      )}
    </div>
  );
}
