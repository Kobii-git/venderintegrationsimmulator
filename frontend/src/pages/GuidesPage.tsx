import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { get } from "../api/client";
import { ErrorAlert } from "../components/ErrorAlert";
import { formatApiError } from "../utils/format";

interface Guide {
  product_id: string;
  product_name: string;
  method_id: string;
  title: string;
  summary: string;
  connection_methods: string[];
  destinations: string[];
  support: string;
  reviewed_at: string;
  content?: string;
}

const slug = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

function CodeBlock({ children }: { children: React.ReactNode }) {
  const [notice, setNotice] = useState("");
  const copy = async (element: HTMLElement | null) => {
    const code = element?.querySelector("code");
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.textContent ?? "");
      setNotice("Copied");
    } catch {
      const range = document.createRange();
      range.selectNodeContents(code);
      window.getSelection()?.removeAllRanges();
      window.getSelection()?.addRange(range);
      setNotice("Selected — copy with your keyboard");
    }
  };
  return <div className="guide-code"><button type="button" className="btn btn-sm guide-copy" onClick={e => void copy(e.currentTarget.parentElement)}>{notice || "Copy command"}</button><pre>{children}</pre></div>;
}

const components: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  h2: ({ children }) => <h2 id={slug(String(children))}>{children}</h2>,
  a: ({ href, children }) => <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{children}</a>,
};

export function GuidesPage() {
  const { productId, methodId } = useParams();
  const [params, setParams] = useSearchParams();
  const [guides, setGuides] = useState<Guide[]>([]);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [error, setError] = useState<string | null>(null);
  const vendor = params.get("vendor") ?? "";
  const method = params.get("method") ?? "";
  const destination = params.get("destination") ?? "";
  const query = params.get("q") ?? "";
  useEffect(() => {
    let active = true;
    void get<Guide[]>("/guides").then(value => { if (active) setGuides(value); }).catch(err => { if (active) setError(formatApiError(err)); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setGuide(null);
    setError(null);
    if (productId && methodId) void get<Guide>(`/guides/${encodeURIComponent(productId)}/${encodeURIComponent(methodId)}`).then(value => { if (active) setGuide(value); }).catch(err => { if (active) setError(formatApiError(err)); });
    return () => { active = false; };
  }, [productId, methodId]);
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next);
  };
  const filtered = guides.filter(g => (!vendor || vendor === g.product_id) && (!method || g.connection_methods.includes(method)) && (!destination || g.destinations.includes(destination)) && `${g.title} ${g.summary} ${g.product_name}`.toLowerCase().includes(query.toLowerCase()));
  const headings = (guide?.content ?? "").split("\n").filter(line => line.startsWith("## ")).map(line => line.slice(3));
  const download = () => {
    if (!guide?.content) return;
    const url = URL.createObjectURL(new Blob([guide.content], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = `${guide.product_id}-${guide.method_id}.md`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="guides-page">
    <h1>Deployment Guides</h1>
    {error && <ErrorAlert message={error} />}
    {!productId && <>
      <p>Production and simulator walkthroughs for every integration. Guides are bundled for offline reading; official reference links require internet access.</p>
      <div className="guide-filters">
        <label>Search guides<input aria-label="Search guides" value={query} onChange={e => update("q", e.target.value)} placeholder="Vendor, connection or topic" /></label>
        <label>Vendor<select aria-label="Vendor" value={vendor} onChange={e => update("vendor", e.target.value)}><option value="">All vendors</option>{[...new Map(guides.map(g => [g.product_id, g.product_name])).entries()].sort((a,b) => a[1].localeCompare(b[1])).map(([id,name]) => <option key={id} value={id}>{name}</option>)}</select></label>
        <label>Connection method<select aria-label="Connection method" value={method} onChange={e => update("method", e.target.value)}><option value="">All methods</option>{[...new Set(guides.flatMap(g => g.connection_methods))].sort().map(m => <option key={m}>{m}</option>)}</select></label>
        <label>Destination<select aria-label="Destination" value={destination} onChange={e => update("destination", e.target.value)}><option value="">All destinations</option>{[...new Set(guides.flatMap(g => g.destinations))].sort().map(d => <option key={d}>{d}</option>)}</select></label>
      </div>
      <p role="status">{filtered.length} guides</p>
      <div className="guide-grid">{filtered.map(g => <article className="card" key={`${g.product_id}/${g.method_id}`}><span className="guide-status">{g.support}</span><h2><Link to={`/guides/${g.product_id}/${g.method_id}`}>{g.title}</Link></h2><p>{g.summary}</p><small>{g.connection_methods.join(" · ")} · Reviewed {g.reviewed_at}</small></article>)}</div>
      {!filtered.length && <p>No guides match these filters.</p>}
    </>}
    {productId && !guide && !error && <p>Loading guide…</p>}
    {guide && <>
      <div className="guide-toolbar"><Link to={`/guides?vendor=${guide.product_id}`}>All {guide.product_name} guides</Link><span>{guide.support} · Reviewed {guide.reviewed_at}</span><button type="button" className="btn" onClick={download}>Download Markdown</button><button type="button" className="btn" onClick={() => window.print()}>Print guide</button><Link to={`/raw-logs?product=${guide.product_id}`}>Generate raw log</Link></div>
      <div className="guide-reading"><aside className="guide-contents" aria-label="Guide contents"><strong>Contents</strong>{headings.map(h => <a key={h} href={`#${slug(h)}`}>{h}</a>)}</aside><article className="guide-body"><Markdown remarkPlugins={[remarkGfm]} skipHtml components={components} urlTransform={url => /^(https?:\/\/|#|\/guides(?:\/|\?))/.test(url) ? url : ""}>{guide.content}</Markdown></article></div>
    </>}
  </div>;
}
