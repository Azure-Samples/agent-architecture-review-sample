import React, { useEffect, useState, useRef } from "react";
import { pngDownloadUrl, excalidrawDownloadUrl } from "../api";

function DiagramViewer({ excalidrawFile, runId }) {
  const [Excalidraw, setExcalidraw] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const containerRef = useRef(null);

  // Dynamically import @excalidraw/excalidraw
  useEffect(() => {
    let cancelled = false;
    import("@excalidraw/excalidraw")
      .then((mod) => {
        if (!cancelled) {
          setExcalidraw(() => mod.Excalidraw);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!excalidrawFile) {
    return (
      <div style={{ padding: 24, textAlign: "center", color: "#868e96" }}>
        No diagram data available.
      </div>
    );
  }

  const initialData = {
    elements: excalidrawFile.elements || [],
    appState: {
      viewBackgroundColor: "#ffffff",
      currentItemFontFamily: 1,
      zoom: { value: 1 },
      ...(excalidrawFile.appState || {}),
    },
    scrollToContent: true,
  };

  return (
    <div>
      <div className="diagram-container" ref={containerRef}>
        {loadError ? (
          // Fallback: show PNG image if Excalidraw component fails to load
          runId ? (
            <img
              src={pngDownloadUrl(runId)}
              alt="Architecture Diagram"
              style={{
                width: "100%",
                height: "100%",
                objectFit: "contain",
                padding: 16,
              }}
            />
          ) : (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                color: "#868e96",
              }}
            >
              Could not load interactive diagram viewer.
            </div>
          )
        ) : Excalidraw ? (
          <Excalidraw
            initialData={initialData}
            viewModeEnabled={false}
            zenModeEnabled={false}
            gridModeEnabled={false}
            theme="light"
          />
        ) : (
          <div className="loading">
            <div className="spinner" />
            Loading diagram viewer...
          </div>
        )}
      </div>

      {runId && (
        <div className="diagram-actions">
          <a
            className="btn btn-secondary"
            href={pngDownloadUrl(runId)}
            download="architecture.png"
          >
            Download PNG
          </a>
          <a
            className="btn btn-secondary"
            href={excalidrawDownloadUrl(runId)}
            download="architecture.excalidraw"
          >
            Download Excalidraw
          </a>
        </div>
      )}
    </div>
  );
}

export default DiagramViewer;
