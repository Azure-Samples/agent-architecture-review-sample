import React, { useState, useCallback } from "react";
import { reviewArchitecture, reviewFile } from "./api";
import Summary from "./components/Summary";
import RiskTable from "./components/RiskTable";
import ComponentMap from "./components/ComponentMap";
import Recommendations from "./components/Recommendations";
import DiagramViewer from "./components/DiagramViewer";

const SAMPLE_YAML = `# Sample Architecture — paste your own or upload a file
components:
  - name: API Gateway
    type: gateway
    technology: Kong
    replicas: 2
  - name: Auth Service
    type: service
    replicas: 2
  - name: Product Service
    type: service
    replicas: 3
  - name: User Database
    type: database
    technology: PostgreSQL
  - name: Product Database
    type: database
    technology: PostgreSQL
  - name: Redis Cache
    type: cache
    replicas: 3

connections:
  - from: api_gateway
    to: auth_service
    protocol: REST
  - from: api_gateway
    to: product_service
    protocol: REST
  - from: auth_service
    to: user_database
    protocol: TCP
  - from: product_service
    to: product_database
    protocol: TCP
  - from: product_service
    to: redis_cache
    protocol: TCP`;

function App() {
  const [content, setContent] = useState("");
  const [forceInfer, setForceInfer] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);
  const [activeTab, setActiveTab] = useState("diagram");
  const [dragOver, setDragOver] = useState(false);

  const handleReview = useCallback(async () => {
    if (!content.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const result = await reviewArchitecture(content, forceInfer);
      setReport(result);
      setActiveTab("diagram");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [content, forceInfer]);

  const handleFile = useCallback(
    async (file) => {
      if (!file) return;
      setLoading(true);
      setError(null);
      setReport(null);
      try {
        // Also show file contents in textarea
        const text = await file.text();
        setContent(text);
        const result = await reviewFile(file, forceInfer);
        setReport(result);
        setActiveTab("diagram");
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [forceInfer]
  );

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleFileInput = useCallback(
    (e) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const loadSample = useCallback(() => {
    setContent(SAMPLE_YAML);
    setReport(null);
    setError(null);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>Architecture Review Agent</h1>
        <span>AI Architecture Reviewer &amp; Diagram Generator</span>
      </header>

      {/* Input Section */}
      <section className="input-section">
        <h2>Architecture Input</h2>

        <div
          className={`file-drop ${dragOver ? "drag-over" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById("file-input").click()}
        >
          Drop a file here or click to upload (YAML, Markdown, TXT, README, any
          text)
          <input
            id="file-input"
            type="file"
            accept=".yaml,.yml,.md,.txt,.json,.tf,.py,.js,.ts"
            style={{ display: "none" }}
            onChange={handleFileInput}
          />
        </div>

        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Paste your architecture description here...&#10;&#10;Supports YAML, Markdown, plaintext arrows (A -> B -> C), or any unstructured text.&#10;The LLM will auto-infer architecture from READMEs, design docs, code, etc."
        />

        <div className="button-row">
          <button
            className="btn btn-primary"
            onClick={handleReview}
            disabled={loading || !content.trim()}
          >
            {loading ? (
              <>
                <span className="spinner" style={{ width: 16, height: 16 }} />
                Analyzing...
              </>
            ) : (
              "Review Architecture"
            )}
          </button>
          <button className="btn btn-secondary" onClick={loadSample}>
            Load Sample
          </button>
          <div className="input-controls">
            <label>
              <input
                type="checkbox"
                checked={forceInfer}
                onChange={(e) => setForceInfer(e.target.checked)}
              />
              Force LLM inference
            </label>
          </div>
        </div>
      </section>

      {/* Error */}
      {error && <div className="error-banner">Error: {error}</div>}

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          Analyzing architecture...
        </div>
      )}

      {/* Results */}
      {report && !loading && (
        <div className="results">
          <Summary data={report.executive_summary} />

          {/* Tabs */}
          <div className="card">
            <div className="tabs">
              <button
                className={`tab ${activeTab === "diagram" ? "active" : ""}`}
                onClick={() => setActiveTab("diagram")}
              >
                Diagram
              </button>
              <button
                className={`tab ${activeTab === "risks" ? "active" : ""}`}
                onClick={() => setActiveTab("risks")}
              >
                Risks ({report.risk_assessment?.summary?.total || 0})
              </button>
              <button
                className={`tab ${activeTab === "components" ? "active" : ""}`}
                onClick={() => setActiveTab("components")}
              >
                Components
              </button>
              <button
                className={`tab ${activeTab === "recommendations" ? "active" : ""}`}
                onClick={() => setActiveTab("recommendations")}
              >
                Recommendations
              </button>
            </div>

            {activeTab === "diagram" && (
              <DiagramViewer
                excalidrawFile={report.diagram?.excalidraw_file}
                runId={report.diagram?.run_id}
              />
            )}
            {activeTab === "risks" && (
              <RiskTable risks={report.risk_assessment} />
            )}
            {activeTab === "components" && (
              <ComponentMap data={report.component_map} />
            )}
            {activeTab === "recommendations" && (
              <Recommendations items={report.recommendations} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
