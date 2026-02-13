import React from "react";

function Summary({ data }) {
  if (!data) return null;

  const riskClass = `risk-${data.risk_level?.replace(/\s+/g, "-") || "healthy"}`;

  return (
    <div className="card">
      <h2>Executive Summary</h2>
      <div className="summary-grid">
        <div className="summary-stat">
          <div className={`value ${riskClass}`}>
            {data.risk_level?.toUpperCase() || "—"}
          </div>
          <div className="label">Risk Level</div>
        </div>
        <div className="summary-stat">
          <div className="value">{data.components ?? 0}</div>
          <div className="label">Components</div>
        </div>
        <div className="summary-stat">
          <div className="value">{data.connections ?? 0}</div>
          <div className="label">Connections</div>
        </div>
        <div className="summary-stat">
          <div className="value">{data.total_risks ?? 0}</div>
          <div className="label">Total Risks</div>
        </div>
        <div className="summary-stat">
          <div className="value" style={{ fontSize: 16 }}>
            {data.format_detected || "—"}
          </div>
          <div className="label">Input Format</div>
        </div>
      </div>
    </div>
  );
}

export default Summary;
