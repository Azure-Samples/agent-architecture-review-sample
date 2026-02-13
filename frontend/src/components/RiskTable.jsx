import React from "react";

const SEVERITIES = ["critical", "high", "medium", "low"];

function RiskTable({ risks }) {
  if (!risks) return <p>No risk data available.</p>;

  const allRisks = SEVERITIES.flatMap((sev) =>
    (risks[sev] || []).map((r) => ({ ...r, severity: sev }))
  );

  if (allRisks.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#868e96" }}>
        No risks detected — architecture looks healthy!
      </div>
    );
  }

  return (
    <table>
      <thead>
        <tr>
          <th style={{ width: 100 }}>Severity</th>
          <th style={{ width: 160 }}>Component</th>
          <th>Issue</th>
          <th>Recommendation</th>
        </tr>
      </thead>
      <tbody>
        {allRisks.map((r, i) => (
          <tr key={i}>
            <td>
              <span className={`severity-badge severity-${r.severity}`}>
                {r.severity}
              </span>
            </td>
            <td>{r.component}</td>
            <td>{r.issue}</td>
            <td>{r.recommendation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default RiskTable;
