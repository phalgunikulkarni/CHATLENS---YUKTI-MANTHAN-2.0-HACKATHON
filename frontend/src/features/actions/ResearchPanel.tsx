import { useState } from "react";
import { Icon } from "../../components/Icon";
import { useResearch } from "../../hooks/useResearch";
import type { ResearchSource } from "../../api/types";

/**
 * Research panel: a query box that calls the backend Research agent (scholarly
 * providers + local Qwen) and renders the synthesized answer, key findings, and
 * a source list with REAL clickable links. All research logic lives in the
 * backend; this component only presents the returned structured result.
 */
export function ResearchPanel() {
  const { status, result, errorMessage, runResearch } = useResearch();
  const [query, setQuery] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    void runResearch(query);
  };

  return (
    <div className="panel research-panel">
      <div className="panel-head">
        <Icon name="brain" size={18} style={{ color: "var(--accent)" }} />
        <h3>Research</h3>
      </div>
      <div className="panel-body">
        <p className="card-desc" style={{ marginBottom: 10 }}>
          Ask a research question. ChatLens gathers credible sources (OpenAlex, Crossref,
          arXiv, PubMed) and synthesizes an answer with your local model.
        </p>
        <form className="research-form" onSubmit={submit}>
          <input
            className="ct-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. transformer neural networks for time series"
            aria-label="Research query"
          />
          <button className="btn btn-primary" type="submit" disabled={status === "loading" || !query.trim()}>
            <Icon name="search" size={15} /> {status === "loading" ? "Researching…" : "Research"}
          </button>
        </form>

        {status === "loading" && (
          <p className="card-desc" style={{ marginTop: 12 }}>Gathering sources and synthesizing…</p>
        )}

        {status === "error" && (
          <div className="research-error" role="alert">
            <strong>Couldn’t complete research.</strong>
            <p className="card-desc">{errorMessage}</p>
          </div>
        )}

        {status === "ready" && result && result.ok && (
          <div className="research-result">
            <div className="research-section">
              <div className="section-title">Research Summary</div>
              <p className="card-desc">{result.research_answer}</p>
            </div>

            {result.key_findings.length > 0 && (
              <div className="research-section">
                <div className="section-title">Key Findings</div>
                <ul className="summary-points">
                  {result.key_findings.map((k, i) => (
                    <li key={i}><span className="bullet"><Icon name="check" size={15} /></span>{k}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="research-section">
              <div className="section-title">Sources ({result.sources.length})</div>
              {result.sources.length === 0 ? (
                <p className="card-desc">No sources were returned.</p>
              ) : (
                <ol className="source-list">
                  {result.sources.map((s, i) => <SourceItem key={i} source={s} />)}
                </ol>
              )}
            </div>

            {result.limitations.length > 0 && (
              <div className="research-section">
                <div className="section-title">Limitations</div>
                <ul className="summary-points">
                  {result.limitations.map((l, i) => <li key={i}>{l}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SourceItem({ source }: { source: ResearchSource }) {
  const evidenceType = source.abstract ? "abstract" : source.snippet ? "snippet" : null;
  const published = source.publication_date || (source.year ? String(source.year) : null);
  return (
    <li className="source-item">
      <div className="source-title">{source.title || "(untitled source)"}</div>
      <div className="source-meta">
        {source.provider && <span className="source-badge">{source.provider}</span>}
        {source.source_type && <span className="source-type">{source.source_type}</span>}
        {published && <span className="source-date">{published}</span>}
      </div>
      {source.authors.length > 0 && (
        <div className="source-authors">{source.authors.slice(0, 6).join(", ")}</div>
      )}
      {source.doi && <div className="source-doi">DOI: {source.doi}</div>}
      {evidenceType && (source.abstract || source.snippet) && (
        <p className="source-evidence card-desc">
          <span className="evidence-tag">{evidenceType}</span>{" "}
          {(source.abstract || source.snippet || "").slice(0, 260)}
          {((source.abstract || source.snippet || "").length > 260) ? "…" : ""}
        </p>
      )}
      {source.url && (
        <a className="source-link" href={source.url} target="_blank" rel="noopener noreferrer">
          <Icon name="arrow" size={13} /> Open source
        </a>
      )}
    </li>
  );
}
