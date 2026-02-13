"""
Unit tests for api.py — FastAPI endpoints.
Uses TestClient (no real server needed).
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import app, MAX_INPUT_SIZE, _validate_run_id
from tests.sample_data import SAMPLE_YAML, SAMPLE_MARKDOWN, SAMPLE_TEXT


client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
#  HEALTH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:

    def test_health_returns_ok(self):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["service"] == "Architecture Review Agent"


# ═══════════════════════════════════════════════════════════════════════════
#  REVIEW ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

class TestReviewEndpoint:

    def test_review_yaml(self):
        r = client.post("/api/review", json={"content": SAMPLE_YAML})
        assert r.status_code == 200
        data = r.json()
        assert "executive_summary" in data
        assert data["executive_summary"]["components"] >= 6
        assert data["executive_summary"]["format_detected"] == "yaml"

    def test_review_markdown(self):
        r = client.post("/api/review", json={"content": SAMPLE_MARKDOWN})
        assert r.status_code == 200
        data = r.json()
        assert data["executive_summary"]["components"] >= 3

    def test_review_plaintext(self):
        r = client.post("/api/review", json={"content": SAMPLE_TEXT})
        assert r.status_code == 200
        data = r.json()
        assert data["executive_summary"]["components"] >= 5

    def test_review_includes_diagram(self):
        r = client.post("/api/review", json={"content": SAMPLE_YAML})
        assert r.status_code == 200
        data = r.json()
        assert "diagram" in data
        assert data["diagram"]["element_count"] > 0
        assert "run_id" in data["diagram"]

    def test_review_includes_risks(self):
        r = client.post("/api/review", json={"content": SAMPLE_YAML})
        data = r.json()
        assert "risk_assessment" in data
        assert "summary" in data["risk_assessment"]

    def test_review_includes_component_map(self):
        r = client.post("/api/review", json={"content": SAMPLE_YAML})
        data = r.json()
        assert "component_map" in data
        assert "statistics" in data["component_map"]

    def test_review_empty_content(self):
        r = client.post("/api/review", json={"content": ""})
        assert r.status_code == 400

    def test_review_whitespace_only(self):
        r = client.post("/api/review", json={"content": "   \n\n  "})
        assert r.status_code == 400

    def test_review_too_large(self):
        r = client.post("/api/review", json={"content": "A" * (MAX_INPUT_SIZE + 1)})
        assert r.status_code == 413

    def test_review_missing_content_field(self):
        r = client.post("/api/review", json={})
        assert r.status_code == 422  # Pydantic validation error


# ═══════════════════════════════════════════════════════════════════════════
#  UPLOAD ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

class TestUploadEndpoint:

    def test_upload_yaml_file(self):
        r = client.post(
            "/api/review/upload",
            files={"file": ("test.yaml", SAMPLE_YAML.encode(), "text/yaml")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["executive_summary"]["components"] >= 6

    def test_upload_markdown_file(self):
        r = client.post(
            "/api/review/upload",
            files={"file": ("test.md", SAMPLE_MARKDOWN.encode(), "text/markdown")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["executive_summary"]["components"] >= 3

    def test_upload_text_file(self):
        r = client.post(
            "/api/review/upload",
            files={"file": ("test.txt", SAMPLE_TEXT.encode(), "text/plain")},
        )
        assert r.status_code == 200

    def test_upload_empty_file(self):
        r = client.post(
            "/api/review/upload",
            files={"file": ("empty.yaml", b"", "text/yaml")},
        )
        assert r.status_code == 400

    def test_upload_too_large(self):
        content = ("A" * (MAX_INPUT_SIZE + 1)).encode()
        r = client.post(
            "/api/review/upload",
            files={"file": ("large.txt", content, "text/plain")},
        )
        assert r.status_code == 413


# ═══════════════════════════════════════════════════════════════════════════
#  INFER ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

class TestInferEndpoint:

    def test_infer_empty_content(self):
        r = client.post("/api/infer", json={"content": ""})
        assert r.status_code == 400

    def test_infer_too_large(self):
        r = client.post("/api/infer", json={"content": "A" * (MAX_INPUT_SIZE + 1)})
        assert r.status_code == 413

    def test_infer_without_azure(self):
        """Without Azure OpenAI configured, infer should still return a response (with error)."""
        # Temporarily clear the env var
        original = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
        try:
            r = client.post("/api/infer", json={"content": "A frontend and a database"})
            assert r.status_code == 200
            data = r.json()
            # Should contain an error about missing endpoint
            assert "error" in data or "components" in data
        finally:
            if original:
                os.environ["AZURE_OPENAI_ENDPOINT"] = original


# ═══════════════════════════════════════════════════════════════════════════
#  DOWNLOAD ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

class TestDownloadEndpoints:

    def _create_review(self) -> str:
        """Helper: run a review and return the run_id."""
        r = client.post("/api/review", json={"content": SAMPLE_YAML})
        assert r.status_code == 200
        return r.json()["diagram"]["run_id"]

    def test_download_png(self):
        run_id = self._create_review()
        r = client.get(f"/api/download/png/{run_id}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert len(r.content) > 0

    def test_download_excalidraw(self):
        run_id = self._create_review()
        r = client.get(f"/api/download/excalidraw/{run_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "excalidraw"

    def test_download_png_not_found(self):
        r = client.get("/api/download/png/deadbeef")
        assert r.status_code == 404

    def test_download_excalidraw_not_found(self):
        r = client.get("/api/download/excalidraw/deadbeef")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
#  SECURITY
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurity:

    def test_path_traversal_rejected(self):
        """run_id with path traversal chars should be rejected."""
        r = client.get("/api/download/png/../../../etc/passwd")
        assert r.status_code in (400, 404, 422)

    def test_run_id_must_be_hex(self):
        r = client.get("/api/download/png/not-hex-id!")
        assert r.status_code in (400, 404, 422)

    def test_validate_run_id_good(self):
        assert _validate_run_id("abcd1234") == "abcd1234"

    def test_validate_run_id_bad(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_run_id("../../bad")

    def test_validate_run_id_too_long(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_run_id("a" * 20)
