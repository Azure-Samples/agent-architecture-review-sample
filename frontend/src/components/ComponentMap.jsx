import React from "react";

function ComponentMap({ data }) {
  if (!data) return <p>No component data available.</p>;

  const components = data.component_map || [];
  const stats = data.statistics || {};

  return (
    <div>
      <table>
        <thead>
          <tr>
            <th>Component</th>
            <th>Type</th>
            <th style={{ textAlign: "center" }}>Fan-In</th>
            <th style={{ textAlign: "center" }}>Fan-Out</th>
            <th>Depends On</th>
            <th>Depended By</th>
          </tr>
        </thead>
        <tbody>
          {components.map((c) => (
            <tr key={c.id}>
              <td>
                <strong>{c.name}</strong>
              </td>
              <td>
                <span
                  style={{
                    fontSize: 12,
                    padding: "2px 6px",
                    background: "#f1f3f5",
                    borderRadius: 4,
                  }}
                >
                  {c.type}
                </span>
              </td>
              <td style={{ textAlign: "center" }}>{c.fan_in}</td>
              <td style={{ textAlign: "center" }}>{c.fan_out}</td>
              <td style={{ fontSize: 13, color: "#868e96" }}>
                {c.depends_on?.join(", ") || "—"}
              </td>
              <td style={{ fontSize: 13, color: "#868e96" }}>
                {c.depended_by?.join(", ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {stats.orphan_components?.length > 0 && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: "#fff3bf",
            borderRadius: 8,
            fontSize: 14,
          }}
        >
          <strong>Orphan components</strong> (no connections):{" "}
          {stats.orphan_components.join(", ")}
        </div>
      )}

      <div
        style={{
          marginTop: 12,
          fontSize: 13,
          color: "#868e96",
        }}
      >
        {stats.total_components} components, {stats.total_connections} connections
      </div>
    </div>
  );
}

export default ComponentMap;
