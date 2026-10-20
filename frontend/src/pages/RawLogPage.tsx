import { Link, useSearchParams } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { generateRawLog, getProduct, listProducts } from "../api/products";
import { Icon } from "../components/Icon";
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
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [productSearch, setProductSearch] = useState("");
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
  const resultHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!result) return;
    resultHeading.current?.focus({ preventScroll: true });
    resultHeading.current?.scrollIntoView?.({ block: "start", behavior: "instant" });
  }, [result]);

  useEffect(() => {
    let active = true;
    void listProducts()
      .then((catalog) => {
        if (!active) return;
        setProducts(catalog);
        setProductId(
          catalog.find((item) => item.id === searchParams.get("product"))?.id ?? catalog.find((item) => item.id === "upguard")?.id ??
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
  }, [searchParams]);

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
        <div><p className="eyebrow">Log tools</p><h1>Generate raw log</h1>
          <p className="page-description">Build a vendor sample, inspect the output, and copy or download it.</p></div>
      {productId && <Link to={`/guides?vendor=${productId}`}>Deployment guides for this integration</Link>}
      </div>
      <div className="tool-notice"><Icon name="code" /><span>Preview only. No destination or saved simulation is needed; nothing is sent.</span></div>
      {error && <ErrorAlert message={error} />}
      {notice && <InfoAlert message={notice} />}
      <div className="raw-workspace">
      <form
        className="card tool-controls"
        onInvalidCapture={(event) => {
          const details = (event.target as HTMLElement).closest("details");
          if (details) details.open = true;
        }}
        onSubmit={(event) => {
          event.preventDefault();
          void generate();
        }}
      >
        <div className="section-heading"><span className="section-number">1</span><div><h2>Choose your sample</h2><p>Product, event, and optional sample values.</p></div></div>
        <div className="form-row"><label htmlFor="raw-search">Find a product</label><input id="raw-search" type="search" value={productSearch}
          placeholder="Search vendors or products…" onChange={(event) => setProductSearch(event.target.value)} /></div>
        <div className="form-grid">
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
              {products.filter((item) => item.id === productId || `${item.display_name} ${item.id}`.toLowerCase().includes(productSearch.toLowerCase())).map((item) => (
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
        <details className="advanced-options" key={`${productId}-${scenarioId}`}>
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
            <Icon name="code" />{generating ? "Generating…" : "Generate raw log"}
          </button>
        </div>
      </form>
      <div className="raw-result">
      {result ? (
        <section className="card output-panel" aria-label="Generated raw log">
          <div className="json-toolbar">
            <div><p className="eyebrow">Generated sample</p><h2 ref={resultHeading} tabIndex={-1}>Raw log</h2><span className="form-hint">{result.content_type} · {result.raw_log.split("\n").length} lines · {new Blob([result.raw_log]).size.toLocaleString()} bytes</span></div>
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
      ) : <section className="card output-placeholder" aria-label="Raw log preview">
        <span className="empty-mark"><Icon name="code" /></span><h2>{generating ? "Generating your sample…" : "Your sample appears here"}</h2>
        <p>Choose a product and scenario, then generate a raw log. Changes clear outdated output.</p>
      </section>}
      </div>
      </div>
    </div>
  );
}
