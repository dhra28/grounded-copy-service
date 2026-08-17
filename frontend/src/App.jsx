import { useState, useEffect } from "react";
import { getProducts, getCopy, generateCopy, getLatestEval, runEval } from "./api";
import "./App.css";

function EvalSummary({ onEvalComplete }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const loadLatest = () => {
    setLoading(true);
    getLatestEval()
      .then((data) => {
        setSummary(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadLatest();
  }, []);

  const handleRunEval = () => {
    setRunning(true);
    setError(null);
    runEval()
      .then(() => {
        setRunning(false);
        loadLatest();
        onEvalComplete();
      })
      .catch((err) => {
        setError(err.message);
        setRunning(false);
      });
  };

  return (
    <div className="eval-summary">
      <div className="eval-header">
        <div>
          <h2>Latest Eval Run</h2>
          <p className="eval-subtext">Groundedness = % of claims verified against real evidence</p>
        </div>
        <button onClick={handleRunEval} disabled={running}>
          {running ? "Running (~2-3 min)..." : "Run New Eval"}
        </button>
      </div>

      {loading && <p className="muted">Loading eval results...</p>}
      {error && <p className="error">{error}</p>}

      {summary && !loading && (
        <div className="stat-row">
          <div className="stat-card">
            <div className="stat-value">{summary.passed}/{summary.total_products}</div>
            <div className="stat-label">Passed</div>
          </div>
          <div className="stat-card stat-highlight">
            <div className="stat-value">{(summary.groundedness_pass_rate * 100).toFixed(0)}%</div>
            <div className="stat-label">Groundedness</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{summary.repaired_count}</div>
            <div className="stat-label">Repaired</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{summary.fallback_used}</div>
            <div className="stat-label">Fallback used</div>
          </div>
        </div>
      )}
    </div>
  );
}

function ProductDetailRow({ product, onGenerated }) {
  const [copy, setCopy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);

  const loadCopy = () => {
    setCopy(null);
    setError(null);
    setLoading(true);
    getCopy(product.product_id)
      .then((data) => {
        setCopy(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadCopy();
  }, [product.product_id]);

  const handleGenerate = (force) => {
    setGenerating(true);
    setError(null);
    generateCopy(product.product_id, force)
      .then((data) => {
        setCopy(data);
        setGenerating(false);
        onGenerated(); // tell App to refresh the product list/status badges
      })
      .catch((err) => {
        setError(err.message);
        setGenerating(false);
      });
  };

  return (
    <tr>
      <td colSpan={5} className="detail-cell">
        <div className="detail-panel-inline">
          {loading && <p className="muted">Loading copy...</p>}

          {!loading && error && (
            <div className="empty-state">
              <p className="error">{error}</p>
              <button onClick={() => handleGenerate(false)} disabled={generating}>
                {generating ? "Generating..." : "Generate Copy"}
              </button>
            </div>
          )}

          {!loading && !error && copy && (
            <>
              <div className="copy-block">
                <div className="copy-block-top">
                  <p className="headline">{copy.headline}</p>
                  <span className={`badge badge-${copy.status}`}>{copy.status}</span>
                </div>
                <p className="subline">{copy.subline}</p>
              </div>

              <h3>Claims &amp; Citations</h3>
              <ul className="claims-list">
                {copy.claims.map((c, i) => (
                  <li key={i}>
                    <span className="claim-text">"{c.text}"</span>
                    <span className={`source-tag source-${c.source_type}`}>
                      {c.source_type === "attribute" ? "📋" : "💬"} {c.source_id}
                    </span>
                  </li>
                ))}
              </ul>

              {copy.attempt_log && (
                <details className="log-details">
                  <summary>Generation Log ({copy.attempt_log.length} steps)</summary>
                  <ul className="log-list">
                    {copy.attempt_log.map((entry, i) => (
                      <li key={i}>{entry}</li>
                    ))}
                  </ul>
                </details>
              )}

              <div className="detail-actions">
                <button onClick={() => handleGenerate(true)} disabled={generating}>
                  {generating ? "Regenerating..." : "Force Regenerate"}
                </button>
              </div>
            </>
          )}
        </div>
      </td>
    </tr>
  );
}

function App() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const loadProducts = () => {
    getProducts()
      .then((data) => {
        setProducts(data.products);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadProducts();
  }, []);

  if (loading) return <div className="container"><p className="muted">Loading products...</p></div>;
  if (error) return <div className="container"><p className="error">Error: {error}</p></div>;

  const toggleRow = (product) => {
    setExpandedId(expandedId === product.product_id ? null : product.product_id);
  };

  return (
    <div className="container">
      <header className="page-header">
        <h1>Grounded Product Copy</h1>
        <p className="subtitle">AI-generated product copy, verified against real evidence — {products.length} products</p>
      </header>

      <EvalSummary onEvalComplete={loadProducts} />

      <table className="product-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Category</th>
            <th>Price</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {products.map((p) => (
            <>
              <tr
                key={p.product_id}
                onClick={() => toggleRow(p)}
                className={`clickable-row ${expandedId === p.product_id ? "row-expanded" : ""}`}
              >
                <td className="mono">{p.product_id}</td>
                <td className="product-name">{p.name}</td>
                <td>{p.category}</td>
                <td>${p.price}</td>
                <td>
                  <span className={`badge badge-${p.current_status || "none"}`}>
                    {p.has_generated_copy ? p.current_status : "not generated"}
                  </span>
                </td>
              </tr>
              {expandedId === p.product_id && (
                <ProductDetailRow
                  key={`${p.product_id}-detail`}
                  product={p}
                  onGenerated={loadProducts}
                />
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default App;