"""
Integration tests — end-to-end flows using the real example files
and the full pipeline (parser → risks → diagram → PNG → report).
"""

import json
import os
import tempfile

import pytest

from tests.sample_data import SAMPLE_YAML, SAMPLE_MARKDOWN, SAMPLE_TEXT

from tools import (
    parse_architecture,
    smart_parse,
    analyze_risks,
    generate_excalidraw_elements,
    generate_mcp_diagram_elements,
    build_component_map,
    save_excalidraw_file,
    export_png,
    build_review_report,
)

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")


def _load_example(filename: str) -> str:
    path = os.path.join(EXAMPLES_DIR, filename)
    if not os.path.exists(path):
        pytest.skip(f"{filename} not found")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _full_pipeline(content: str, tmpdir: str) -> dict:
    """Run the complete pipeline and return the report + file paths."""
    parsed = parse_architecture(content)

    # Risk analysis
    risks = analyze_risks(parsed["components"], parsed["connections"])

    # Component map
    cmap = build_component_map(parsed["components"], parsed["connections"])

    # Diagram generation (both formats)
    file_diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
    mcp_diagram = generate_mcp_diagram_elements(parsed["components"], parsed["connections"])

    # File exports
    excalidraw_path = os.path.join(tmpdir, "architecture.excalidraw")
    png_path = os.path.join(tmpdir, "architecture.png")
    bundle_path = os.path.join(tmpdir, "review_bundle.json")

    saved_excalidraw = save_excalidraw_file(file_diagram["elements_json"], excalidraw_path)
    saved_png = export_png(parsed["components"], parsed["connections"], png_path)

    # Build report
    diagram_info = {
        "element_count": file_diagram["element_count"],
        "local_file": saved_excalidraw,
        "png_file": saved_png,
    }
    report = build_review_report(parsed, risks, cmap, diagram_info)

    # Save bundle
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return {
        "parsed": parsed,
        "risks": risks,
        "cmap": cmap,
        "file_diagram": file_diagram,
        "mcp_diagram": mcp_diagram,
        "report": report,
        "files": {
            "excalidraw": saved_excalidraw,
            "png": saved_png,
            "bundle": bundle_path,
        },
    }


class TestEcommercePipeline:
    """Full pipeline with examples/ecommerce.yaml."""

    def test_full_pipeline(self):
        content = _load_example("ecommerce.yaml")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _full_pipeline(content, tmpdir)

            # Parsing
            parsed = result["parsed"]
            assert parsed["detected_format"] == "yaml"
            assert len(parsed["components"]) >= 12
            assert len(parsed["connections"]) >= 13

            # Risks
            risks = result["risks"]
            assert risks["summary"]["total"] >= 1  # Should have at least SPOF risks

            # Component map
            stats = result["cmap"]["statistics"]
            assert stats["total_components"] >= 12
            assert stats["total_connections"] >= 13

            # Files exist and have content
            for name, path in result["files"].items():
                assert os.path.exists(path), f"{name} file not created"
                assert os.path.getsize(path) > 0, f"{name} file is empty"

            # Report structure
            report = result["report"]
            assert report["executive_summary"]["risk_level"] in ("critical", "needs attention", "moderate", "healthy")

    def test_diagram_element_count(self):
        content = _load_example("ecommerce.yaml")
        parsed = parse_architecture(content)
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
        elements = json.loads(diagram["elements_json"])

        # Each component produces 3 elements (rect + name text + type text)
        # Each connection produces 1-2 elements (arrow + optional label)
        # Plus camera element
        n_comp = len(parsed["components"])
        n_conn = len(parsed["connections"])
        assert len(elements) >= n_comp + n_conn  # at minimum

    def test_mcp_diagram_structure(self):
        content = _load_example("ecommerce.yaml")
        parsed = parse_architecture(content)
        mcp_diagram = generate_mcp_diagram_elements(parsed["components"], parsed["connections"])
        elements = json.loads(mcp_diagram["elements_json"])

        rects = [e for e in elements if e["type"] == "rectangle"]
        arrows = [e for e in elements if e["type"] == "arrow"]
        cameras = [e for e in elements if e["type"] == "cameraUpdate"]

        assert len(rects) == len(parsed["components"])
        assert len(arrows) == len(parsed["connections"])
        assert len(cameras) == 1

    def test_risk_categories_present(self):
        content = _load_example("ecommerce.yaml")
        parsed = parse_architecture(content)
        risks = analyze_risks(parsed["components"], parsed["connections"])

        # E-commerce arch has known risk patterns:
        # - Notification Service: 1 replica, infrastructure
        # - Order Database: 1 replica
        # - Multiple services → Redis Cache (scalability)
        assert risks["summary"]["total"] >= 1

    def test_png_is_valid_image(self):
        content = _load_example("ecommerce.yaml")
        parsed = parse_architecture(content)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            png_path = os.path.join(tmpdir, "test.png")
            export_png(parsed["components"], parsed["connections"], png_path)
            from PIL import Image
            img = Image.open(png_path)
            assert img.width > 200
            assert img.height > 200
            assert img.mode in ("RGB", "RGBA")
            img.close()


class TestEventDrivenPipeline:
    """Full pipeline with examples/event_driven.md."""

    def test_full_pipeline(self):
        content = _load_example("event_driven.md")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _full_pipeline(content, tmpdir)

            parsed = result["parsed"]
            assert parsed["detected_format"] == "markdown"
            assert len(parsed["components"]) >= 8
            assert len(parsed["connections"]) >= 8

            # All files created
            for name, path in result["files"].items():
                assert os.path.exists(path)

    def test_component_types_correct(self):
        content = _load_example("event_driven.md")
        parsed = parse_architecture(content)
        types = {c["name"]: c["type"] for c in parsed["components"]}
        assert types["Edge Gateway"] == "gateway"
        assert types["Ingestion Hub"] == "queue"
        assert types["Cold Storage"] == "database"
        assert types["Hot Storage"] == "database"

    def test_component_map_fan_metrics(self):
        content = _load_example("event_driven.md")
        parsed = parse_architecture(content)
        cmap = build_component_map(parsed["components"], parsed["connections"])
        mapping = {c["name"]: c for c in cmap["component_map"]}

        # Stream Processor has 1 fan-in (Ingestion Hub), 3 fan-out (Hot, Cold, Alert)
        sp = mapping["Stream Processor"]
        assert sp["fan_in"] == 1
        assert sp["fan_out"] == 3


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_single_component_no_connections(self):
        content = "- API Service"
        parsed = parse_architecture(content)
        assert len(parsed["components"]) == 1
        assert parsed["parsing_sufficient"] is False

    def test_self_referencing_connection(self):
        content = "A -> A"
        parsed = parse_architecture(content)
        assert len(parsed["connections"]) == 1
        assert parsed["connections"][0]["source"] == parsed["connections"][0]["target"]

    def test_very_long_chain(self):
        chain = " -> ".join([f"Service{i}" for i in range(20)])
        parsed = parse_architecture(chain)
        assert len(parsed["components"]) == 20
        assert len(parsed["connections"]) == 19

    def test_special_characters_in_names(self):
        content = "User-Auth Service -> DB (Primary)"
        parsed = parse_architecture(content)
        assert len(parsed["components"]) >= 2

    def test_mixed_arrow_formats(self):
        content = "A -> B\nC => D\nE >> F"
        parsed = parse_architecture(content)
        assert len(parsed["connections"]) == 3

    def test_unicode_content(self):
        content = "Düsseldorf Gateway -> München Service -> Zürich Database"
        parsed = parse_architecture(content)
        assert len(parsed["components"]) == 3

    def test_report_json_serializable(self):
        """The full report should be JSON-serializable."""
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
        report = build_review_report(parsed, risks, cmap, diagram)
        # Should not raise
        serialized = json.dumps(report)
        assert isinstance(serialized, str)

    def test_concurrent_pipeline_runs(self):
        """Multiple pipeline runs should not interfere with each other."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content1 = "A -> B -> C"
            content2 = "X -> Y -> Z"

            result1 = _full_pipeline(content1, os.path.join(tmpdir, "run1"))
            result2 = _full_pipeline(content2, os.path.join(tmpdir, "run2"))

            # Different components
            names1 = {c["name"] for c in result1["parsed"]["components"]}
            names2 = {c["name"] for c in result2["parsed"]["components"]}
            assert names1 != names2


class TestSmartParse:
    """Tests for smart_parse() — async parse with LLM fallback."""

    @pytest.mark.asyncio
    async def test_smart_parse_yaml(self):
        result = await smart_parse(SAMPLE_YAML)
        assert result["detected_format"] == "yaml"
        assert result["parsing_sufficient"] is True

    @pytest.mark.asyncio
    async def test_smart_parse_markdown(self):
        result = await smart_parse(SAMPLE_MARKDOWN)
        assert result["detected_format"] == "markdown"
        assert result["parsing_sufficient"] is True

    @pytest.mark.asyncio
    async def test_smart_parse_plaintext(self):
        result = await smart_parse(SAMPLE_TEXT)
        assert result["detected_format"] == "text"
        assert result["parsing_sufficient"] is True

    @pytest.mark.asyncio
    async def test_smart_parse_insufficient_falls_back(self):
        """For vague input, smart_parse should try LLM fallback (will fail gracefully without Azure)."""
        result = await smart_parse("Our system uses microservices.")
        # Without Azure configured, should still return a result
        assert "components" in result
        assert "connections" in result
