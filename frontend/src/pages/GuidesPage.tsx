import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { get } from "../api/client";
import { ErrorAlert } from "../components/ErrorAlert";
import { Icon } from "../components/Icon";
import { LoadingState } from "../components/LoadingState";
import { formatApiError } from "../utils/format";

interface Guide {
  product_id: string; product_name: string; method_id: string; title: string; summary: string;
  connection_methods: string[]; destinations: string[]; support: string; reviewed_at: string;
  content?: string; documentation_status?: string;
  method_inventory?: { method: string; support: string; documentation_status: string;
    production_verification: { status: string; notes: string };
    simulator_verification: { status: string; notes: string };
  }[];
}
const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const verificationLabel = (value: string) => value.replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase());
const plainHeading = (value: string) => value.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*`]/g, "").replace(/\s+#+\s*$/, "");

function CodeBlock({ children }: { children: React.ReactNode }) {
  const [notice, setNotice] = useState("");
  const copy = async (element: HTMLElement | null) => {
    const code = element?.querySelector("code");
    if (!code) return;
    try { await navigator.clipboard.writeText(code.textContent ?? ""); setNotice("Copied"); }
    catch {
      const range = document.createRange(); range.selectNodeContents(code);
      window.getSelection()?.removeAllRanges(); window.getSelection()?.addRange(range);
      setNotice("Selected — copy with your keyboard");
    }
  };
  return <div className="guide-code"><div className="guide-code-toolbar"><span>Command / example</span><button type="button" className="btn btn-sm" onClick={(event) => void copy(event.currentTarget.closest(".guide-code"))}>{notice === "Copied" ? "Copied" : "Copy command"}</button></div>{notice && <span className="guide-code-notice" role="status">{notice}</span>}<pre>{children}</pre></div>;
}

export function GuidesPage() {
  const { productId, methodId } = useParams();
  const [params, setParams] = useSearchParams();
  const [guides, setGuides] = useState<Guide[]>([]);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [guideError, setGuideError] = useState<string | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const vendor = params.get("vendor") ?? "";
  const method = params.get("method") ?? "";
  const destination = params.get("destination") ?? "";
  const query = params.get("q") ?? "";
  useEffect(() => {
    if (productId) return;
    let active = true;
    setCatalogLoading(true); setCatalogError(null);
    void get<Guide[]>("/guides").then((value) => { if (active) setGuides(value); })
      .catch((err) => { if (active) setCatalogError(formatApiError(err)); })
      .finally(() => { if (active) setCatalogLoading(false); });
    return () => { active = false; };
  }, [productId, retry]);
  useEffect(() => {
    let active = true; setGuide(null); setGuideError(null);
    if (productId && methodId) void get<Guide>(`/guides/${encodeURIComponent(productId)}/${encodeURIComponent(methodId)}`)
      .then((value) => { if (active) setGuide(value); }).catch((err) => { if (active) setGuideError(formatApiError(err)); });
    return () => { active = false; };
  }, [productId, methodId, retry]);
  useEffect(() => {
    if (!guide || !window.location.hash) return;
    try { document.getElementById(decodeURIComponent(window.location.hash.slice(1)))?.scrollIntoView?.({ block: "start" }); }
    catch { /* Ignore malformed bookmark fragments. */ }
  }, [guide]);
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };
  const filtered = guides.filter((item) => (!vendor || vendor === item.product_id) && (!method || item.connection_methods.includes(method)) && (!destination || item.destinations.includes(destination)) && `${item.title} ${item.summary} ${item.product_name} ${item.connection_methods.join(" ")} ${item.destinations.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()));
  const headingCounts = new Map<string, number>();
  let fenced = false;
  const headings = (guide?.content ?? "").split("\n").flatMap((line, index) => {
    if (/^\s*(```|~~~)/.test(line)) { fenced = !fenced; return []; }
    if (fenced || !line.startsWith("## ")) return [];
    const label = plainHeading(line.slice(3).trim()); const base = slug(label) || "section";
    const count = (headingCounts.get(base) ?? 0) + 1; headingCounts.set(base, count);
    return [{ label, id: count === 1 ? base : `${base}-${count}`, line: index + 1 }];
  });
  const components: Components = {
    pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
    h1: () => null,
    h2: ({ children, node }) => <h2 tabIndex={-1} id={headings.find((heading) => heading.line === node?.position?.start.line)?.id}>{children}</h2>,
    a: ({ href, children }) => <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{children}</a>,
  };
  const download = () => {
    if (!guide?.content) return;
    const url = URL.createObjectURL(new Blob([guide.content], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `${guide.product_id}-${guide.method_id}.md`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const context = params.size ? `?${params.toString()}` : "";
  const back = context ? `/guides${context}` : `/guides?vendor=${guide?.product_id ?? productId ?? ""}`;
  const title = guide?.content?.split("\n").find((line) => /^#\s/.test(line))?.replace(/^#\s+/, "") ?? guide?.title;

  return <div className="guides-page">
    {!productId ? <>
      <div className="page-header"><div><p className="eyebrow">Learn & deploy</p><h1>Deployment Guides</h1><p className="page-description">Find a connection path, follow the setup, and verify each step.</p></div><Link className="btn" to="/">Open simulations<Icon name="arrow" /></Link></div>
      <div className="tool-notice"><Icon name="book" /><span>Guides are bundled for offline reading. Official reference links need internet access.</span></div>
      <section className="card guide-search-panel" aria-label="Guide filters"><div className="guide-filters">
        <div className="form-row"><label htmlFor="guide-query">Search guides</label><input id="guide-query" type="search" value={query} onChange={(event) => update("q", event.target.value)} placeholder="Vendor, connection or topic" /></div>
        <div className="form-row"><label htmlFor="guide-vendor">Vendor</label><select id="guide-vendor" value={vendor} onChange={(event) => update("vendor", event.target.value)}><option value="">All vendors</option>{[...new Map(guides.map((item) => [item.product_id, item.product_name])).entries()].sort((a,b) => a[1].localeCompare(b[1])).map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></div>
        <div className="form-row"><label htmlFor="guide-method">Connection method</label><select id="guide-method" value={method} onChange={(event) => update("method", event.target.value)}><option value="">All methods</option>{[...new Set(guides.flatMap((item) => item.connection_methods))].sort().map((value) => <option key={value}>{value}</option>)}</select></div>
        <div className="form-row"><label htmlFor="guide-destination">Destination</label><select id="guide-destination" value={destination} onChange={(event) => update("destination", event.target.value)}><option value="">All destinations</option>{[...new Set(guides.flatMap((item) => item.destinations))].sort().map((value) => <option key={value}>{value}</option>)}</select></div>
      </div><div className="monitor-history-toolbar"><span className="form-hint" role="status">{catalogLoading ? "Loading the guide library…" : `${filtered.length} of ${guides.length} guides · ${new Set(guides.map((item) => item.product_id)).size} vendors`}</span><button type="button" className="btn btn-sm" onClick={() => setParams({})}>Clear filters</button></div></section>
      {catalogError ? <><ErrorAlert message={catalogError} /><button type="button" className="btn" onClick={() => setRetry((value) => value + 1)}>Try again</button></> : catalogLoading ? <LoadingState label="Loading guides…" /> : <>
      <div className="guide-grid">{filtered.map((item) => <article className="card guide-card" key={`${item.product_id}/${item.method_id}`}><Link className="guide-card-link" aria-label={item.title} to={`/guides/${item.product_id}/${item.method_id}${context}`}><div className="guide-card-heading"><span className="guide-vendor">{item.product_name}</span><Icon name="book" /></div><h2>{item.title}</h2><p>{item.summary}</p><div className="guide-card-meta"><span className="badge badge-stopped">{item.support}</span><span>{item.connection_methods.join(" · ")}</span></div><div className="guide-card-footer"><small>Reviewed {item.reviewed_at}</small><span>Read guide<Icon name="arrow" /></span></div></Link></article>)}</div>
      {!filtered.length && <div className="card empty-state"><span className="empty-mark"><Icon name="search" /></span><h2>No guides match these filters.</h2><p>Try a vendor name, change the connection method, or clear the filters to browse the library.</p><button type="button" className="btn" onClick={() => setParams({})}>Show all guides</button></div>}</>}
    </> : <>
      <Link className="guide-back" to={back}><span aria-hidden="true">← </span>{context ? "Back to guide results" : "All vendor guides"}</Link>
      {guideError ? <><ErrorAlert message={guideError} /><button type="button" className="btn" onClick={() => setRetry((value) => value + 1)}>Try again</button></> : !guide ? <LoadingState label="Loading guide…" /> : <>
      <div className="page-header guide-page-header"><div><p className="eyebrow">Deployment guide · {guide.product_name}</p><h1>{title}</h1><p className="page-description">{guide.summary}</p></div></div>
      <div className="guide-toolbar"><div className="guide-document-meta"><span className="badge badge-stopped">{guide.support}</span><span>Reviewed {guide.reviewed_at}</span></div><div className="page-actions"><button type="button" className="btn" onClick={download}>Download Markdown</button><button type="button" className="btn" onClick={() => window.print()}>Print guide</button><Link className="btn btn-primary" to={`/raw-logs?product=${guide.product_id}`}>Generate raw log<Icon name="arrow" /></Link></div></div>
      <details className="card guide-verification"><summary>Documentation: {guide.documentation_status ?? "unreviewed"} — deployment verification</summary><p className="form-hint">Documentation review and local simulator checks are separate from live vendor, parser and Sentinel acceptance.</p>
        {guide.method_inventory?.length ? <div className="table-wrap" role="region" aria-label="Deployment verification" tabIndex={0}><table className="data-table"><thead><tr><th>Method / support</th><th>Production verification</th><th>Simulator verification</th></tr></thead><tbody>{guide.method_inventory.map((item) => <tr key={item.method}><td>{item.method}<span className="table-secondary">{item.support}</span></td><td><strong>{verificationLabel(item.production_verification.status)}</strong><p>{item.production_verification.notes}</p></td><td><strong>{verificationLabel(item.simulator_verification.status)}</strong><p>{item.simulator_verification.notes}</p></td></tr>)}</tbody></table></div> : <p className="inline-empty">No deployment verification evidence recorded.</p>}
      </details>
      <div className="guide-reading"><aside className="guide-contents" aria-label="Guide contents"><div className="guide-jump form-row"><label htmlFor="guide-jump">Jump to section</label><select id="guide-jump" value="" onChange={(event) => { if (event.target.value) window.location.hash = event.target.value; }}><option value="">Choose a section</option>{headings.map((heading) => <option key={heading.id} value={heading.id}>{heading.label}</option>)}</select></div><nav className="guide-contents-links" aria-label="On this page"><strong>On this page</strong>{headings.map((heading, index) => <a key={heading.id} href={`#${heading.id}`}><span aria-hidden="true">{index + 1}</span>{heading.label}</a>)}</nav></aside>
      <article className="guide-body" key={`${productId}/${methodId}`}><Markdown remarkPlugins={[remarkGfm]} skipHtml components={components} urlTransform={(url) => /^(https?:\/\/|#|\/guides(?:\/|\?))/.test(url) ? url : ""}>{guide.content}</Markdown></article></div>
      </>}
    </>}
  </div>;
}
