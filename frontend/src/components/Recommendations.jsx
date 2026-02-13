import React from "react";

function Recommendations({ items }) {
  if (!items || items.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#868e96" }}>
        No recommendations — architecture looks good!
      </div>
    );
  }

  return (
    <table>
      <thead>
        <tr>
          <th style={{ width: 100 }}>Priority</th>
          <th style={{ width: 160 }}>Component</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {items.map((rec, i) => (
          <tr key={i}>
            <td>
              <span className={`severity-badge severity-${rec.priority}`}>
                {rec.priority}
              </span>
            </td>
            <td>{rec.component}</td>
            <td>{rec.action}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default Recommendations;
