"""
Unit tests for tools.py — parser, risk detection, diagram generation,
component mapping, and report building.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from tools import (
    _detect_format,
    _infer_type,
    _extract_replicas,
    _parse_yaml,
    _parse_markdown,
    _parse_text,
    parse_architecture,
    analyze_risks,
    generate_excalidraw_elements,
    generate_mcp_diagram_elements,
    build_component_map,
    save_excalidraw_file,
    export_png,
    build_review_report,
    _hex_to_rgb,
)

from tests.sample_data import SAMPLE_YAML, SAMPLE_MARKDOWN, SAMPLE_TEXT


# ═══════════════════════════════════════════════════════════════════════════
#  FORMAT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatDetection:
    """Tests for _detect_format()."""

    def test_detect_yaml(self):
        assert _detect_format(SAMPLE_YAML) == "yaml"

    def test_detect_markdown(self):
        assert _detect_format(SAMPLE_MARKDOWN) == "markdown"

    def test_detect_plaintext(self):
        assert _detect_format(SAMPLE_TEXT) == "text"

    def test_detect_yaml_with_dashes(self):
        assert _detect_format("---\nname: test\ncomponents:\n  - name: A\n") == "yaml"

    def test_detect_plaintext_for_prose(self):
        assert _detect_format("We have a React frontend and a PostgreSQL database.") == "text"

    def test_detect_markdown_with_h1(self):
        assert _detect_format("# Architecture\n\nSome text") == "markdown"


# ═══════════════════════════════════════════════════════════════════════════
#  TYPE INFERENCE
# ═══════════════════════════════════════════════════════════════════════════

class TestTypeInference:
    """Tests for _infer_type()."""

    @pytest.mark.parametrize("name,expected", [
        ("PostgreSQL Database", "database"),
        ("Redis Cache", "database"),  # "redis" appears in both database & cache; database matched first
        ("RabbitMQ", "queue"),
        ("Kafka Event Hub", "queue"),
        ("API Gateway", "gateway"),
        ("Load Balancer", "gateway"),
        ("React Frontend", "frontend"),
        ("S3 Bucket", "storage"),
        ("Stripe Payment", "external"),
        ("Prometheus Monitor", "monitoring"),
        ("User Service", "service"),
        ("Order Handler", "service"),
    ])
    def test_infer_known_types(self, name, expected):
        assert _infer_type(name) == expected

    def test_default_service_for_unknown(self):
        assert _infer_type("FooBarBaz") == "service"

    def test_case_insensitive(self):
        assert _infer_type("POSTGRESQL database") == "database"


# ═══════════════════════════════════════════════════════════════════════════
#  REPLICA EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

class TestReplicaExtraction:
    """Tests for _extract_replicas()."""

    def test_extract_replica_count(self):
        assert _extract_replicas("3 replicas behind LB") == 3

    def test_extract_instance_count(self):
        assert _extract_replicas("running on 5 instances") == 5

    def test_extract_node_count(self):
        assert _extract_replicas("2 nodes in cluster") == 2

    def test_default_one_when_missing(self):
        assert _extract_replicas("no scaling info here") == 1

    def test_empty_string(self):
        assert _extract_replicas("") == 1


# ═══════════════════════════════════════════════════════════════════════════
#  YAML PARSER
# ═══════════════════════════════════════════════════════════════════════════

class TestYamlParser:
    """Tests for _parse_yaml()."""

    def test_parse_components(self):
        result = _parse_yaml(SAMPLE_YAML)
        assert len(result["components"]) == 6
        names = {c["name"] for c in result["components"]}
        assert "API Gateway" in names
        assert "User Service" in names
        assert "User Database" in names

    def test_parse_connections(self):
        result = _parse_yaml(SAMPLE_YAML)
        assert len(result["connections"]) == 6
        sources = {c["source"] for c in result["connections"]}
        assert "api_gateway" in sources
        assert "user_service" in sources

    def test_component_fields(self):
        result = _parse_yaml(SAMPLE_YAML)
        gw = next(c for c in result["components"] if c["name"] == "API Gateway")
        assert gw["type"] == "gateway"
        assert gw["technology"] == "Kong"
        assert gw["replicas"] == 2

    def test_connection_labels(self):
        result = _parse_yaml(SAMPLE_YAML)
        rest_conns = [c for c in result["connections"] if c["label"] == "REST"]
        assert len(rest_conns) == 2

    def test_metadata_preserved(self):
        result = _parse_yaml(SAMPLE_YAML)
        assert result["metadata"]["name"] == "Test Architecture"

    def test_string_components(self):
        yaml_str = "components:\n  - ServiceA\n  - ServiceB\n"
        result = _parse_yaml(yaml_str)
        assert len(result["components"]) == 2
        assert result["components"][0]["name"] == "ServiceA"

    def test_alternate_keys(self):
        yaml_str = "services:\n  - name: SvcA\nnodes:\n  - name: NodeB\nedges:\n  - from: svc_a\n    to: node_b\n"
        result = _parse_yaml(yaml_str)
        assert len(result["components"]) == 2
        assert len(result["connections"]) == 1

    def test_empty_yaml(self):
        result = _parse_yaml("---\n")
        assert result["components"] == []
        assert result["connections"] == []

    def test_non_dict_yaml(self):
        result = _parse_yaml("- item1\n- item2\n")
        assert result["components"] == []


# ═══════════════════════════════════════════════════════════════════════════
#  MARKDOWN PARSER
# ═══════════════════════════════════════════════════════════════════════════

class TestMarkdownParser:
    """Tests for _parse_markdown()."""

    def test_parse_components(self):
        result = _parse_markdown(SAMPLE_MARKDOWN)
        assert len(result["components"]) == 3
        names = {c["name"] for c in result["components"]}
        assert "Edge Gateway" in names
        assert "Stream Processor" in names
        assert "Hot Storage" in names

    def test_parse_connections(self):
        result = _parse_markdown(SAMPLE_MARKDOWN)
        assert len(result["connections"]) == 2

    def test_component_metadata(self):
        result = _parse_markdown(SAMPLE_MARKDOWN)
        gw = next(c for c in result["components"] if c["name"] == "Edge Gateway")
        assert gw["type"] == "gateway"
        assert gw["technology"] == "Azure IoT Edge"
        assert gw["replicas"] == 4

    def test_connection_labels(self):
        result = _parse_markdown(SAMPLE_MARKDOWN)
        mqtt = next(c for c in result["connections"] if c["label"] == "MQTT")
        assert mqtt["source"] == "edge_gateway"
        assert mqtt["target"] == "stream_processor"

    def test_empty_markdown(self):
        result = _parse_markdown("")
        assert result["components"] == []
        assert result["connections"] == []


# ═══════════════════════════════════════════════════════════════════════════
#  PLAINTEXT PARSER
# ═══════════════════════════════════════════════════════════════════════════

class TestPlaintextParser:
    """Tests for _parse_text()."""

    def test_chained_arrows(self):
        result = _parse_text("A -> B -> C -> D")
        assert len(result["components"]) == 4
        assert len(result["connections"]) == 3

    def test_simple_arrow(self):
        result = _parse_text("Frontend -> Backend")
        assert len(result["components"]) == 2
        assert result["connections"][0]["source"] == "frontend"
        assert result["connections"][0]["target"] == "backend"

    def test_multiple_lines(self):
        result = _parse_text(SAMPLE_TEXT)
        # Load Balancer -> Web Server -> App Server -> PostgreSQL DB  (4 comps, 3 conns)
        # Web Server -> Redis Cache   (1 new comp, 1 conn)
        # App Server -> Message Queue  (1 new comp, 1 conn)
        assert len(result["components"]) == 6
        assert len(result["connections"]) == 5

    def test_type_inference_in_text(self):
        result = _parse_text("API Gateway -> Redis Cache -> PostgreSQL DB")
        types = {c["name"]: c["type"] for c in result["components"]}
        assert types["API Gateway"] == "gateway"
        # "redis" in _TYPE_KEYWORDS matches "database" first (before "cache")
        assert types["Redis Cache"] == "database"
        assert types["PostgreSQL DB"] == "database"

    def test_unicode_arrow(self):
        result = _parse_text("Frontend → Backend")
        assert len(result["connections"]) == 1

    def test_double_arrow(self):
        result = _parse_text("Frontend >> Backend")
        assert len(result["connections"]) == 1

    def test_fat_arrow(self):
        result = _parse_text("Frontend => Backend")
        assert len(result["connections"]) == 1

    def test_deduplicate_components(self):
        text = "A -> B\nA -> C\nB -> C"
        result = _parse_text(text)
        assert len(result["components"]) == 3

    def test_empty_text(self):
        result = _parse_text("")
        assert result["components"] == []
        assert result["connections"] == []

    def test_bullet_list_without_arrows(self):
        text = "- API Gateway\n- User Service\n- PostgreSQL Database"
        result = _parse_text(text)
        assert len(result["components"]) == 3
        assert len(result["connections"]) == 0


# ═══════════════════════════════════════════════════════════════════════════
#  PARSE_ARCHITECTURE (unified entry point)
# ═══════════════════════════════════════════════════════════════════════════

class TestParseArchitecture:
    """Tests for parse_architecture() — unified parsing with auto-detection."""

    def test_auto_detect_yaml(self):
        result = parse_architecture(SAMPLE_YAML)
        assert result["detected_format"] == "yaml"
        assert result["parsing_sufficient"] is True
        assert len(result["components"]) >= 6

    def test_auto_detect_markdown(self):
        result = parse_architecture(SAMPLE_MARKDOWN)
        assert result["detected_format"] == "markdown"
        assert result["parsing_sufficient"] is True

    def test_auto_detect_text(self):
        result = parse_architecture(SAMPLE_TEXT)
        assert result["detected_format"] == "text"
        assert result["parsing_sufficient"] is True

    def test_format_hint_override(self):
        result = parse_architecture(SAMPLE_TEXT, format_hint="text")
        assert result["detected_format"] == "text"

    def test_backfill_missing_components(self):
        """If a connection references a component ID not in the list, it should be auto-created."""
        yaml_content = """\
components:
  - name: ServiceA
    type: service
connections:
  - from: servicea
    to: unknown_service
"""
        result = parse_architecture(yaml_content)
        ids = {c["id"] for c in result["components"]}
        assert "unknown_service" in ids

    def test_insufficient_parsing(self):
        """Single vague line should be flagged as insufficient."""
        result = parse_architecture("Hello world")
        assert result["parsing_sufficient"] is False

    def test_sufficient_with_two_components(self):
        result = parse_architecture("A -> B")
        assert result["parsing_sufficient"] is True


# ═══════════════════════════════════════════════════════════════════════════
#  RISK DETECTION
# ═══════════════════════════════════════════════════════════════════════════

class TestRiskDetection:
    """Tests for analyze_risks() and its sub-detectors."""

    def test_spof_detection(self, sample_components, sample_connections):
        """API Gateway with 1 replica and 2+ dependants should trigger SPOF."""
        risks = analyze_risks(sample_components, sample_connections)
        critical = risks["critical"]
        assert len(critical) >= 1
        spof_names = {r["component"] for r in critical}
        # Gateway with 1 replica is infrastructure SPOF
        assert "API Gateway" in spof_names or "User DB" in spof_names

    def test_no_risks_for_healthy_arch(self):
        """Well-scaled arch with no anti-patterns should have few/no risks."""
        comps = [
            {"id": "gw", "name": "Gateway", "type": "gateway", "replicas": 3, "technology": ""},
            {"id": "svc", "name": "Service", "type": "service", "replicas": 2, "technology": ""},
        ]
        conns = [{"source": "gw", "target": "svc", "label": "", "type": "sync"}]
        risks = analyze_risks(comps, conns)
        assert risks["summary"]["critical"] == 0

    def test_shared_db_anti_pattern(self, multi_writer_components, multi_writer_connections):
        """Two services writing to same DB should trigger anti-pattern risk."""
        risks = analyze_risks(multi_writer_components, multi_writer_connections)
        high = risks["high"]
        assert any("shared" in r["issue"].lower() or "anti-pattern" in r["issue"].lower()
                    for r in high)

    def test_frontend_direct_db_access(self, frontend_to_db_components, frontend_to_db_connections):
        """Frontend → DB direct access should trigger security risk."""
        risks = analyze_risks(frontend_to_db_components, frontend_to_db_connections)
        all_risks = risks["critical"] + risks["high"] + risks["medium"]
        assert any("direct" in r["issue"].lower() or "frontend" in r["issue"].lower()
                    for r in all_risks)

    def test_missing_gateway_risk(self):
        """Frontend without gateway should trigger security warning."""
        comps = [
            {"id": "fe", "name": "React App", "type": "frontend", "replicas": 1, "technology": ""},
            {"id": "svc", "name": "Backend", "type": "service", "replicas": 1, "technology": ""},
        ]
        conns = [{"source": "fe", "target": "svc", "label": "", "type": "sync"}]
        risks = analyze_risks(comps, conns)
        all_risks = risks["critical"] + risks["high"]
        assert any("gateway" in r["issue"].lower() for r in all_risks)

    def test_scalability_risk_shared_cache(self):
        """Cache used by ≥3 services should trigger scalability risk."""
        comps = [
            {"id": "cache", "name": "Redis", "type": "cache", "replicas": 1, "technology": ""},
            {"id": "s1", "name": "Svc1", "type": "service", "replicas": 1, "technology": ""},
            {"id": "s2", "name": "Svc2", "type": "service", "replicas": 1, "technology": ""},
            {"id": "s3", "name": "Svc3", "type": "service", "replicas": 1, "technology": ""},
        ]
        conns = [
            {"source": "s1", "target": "cache", "label": "", "type": "sync"},
            {"source": "s2", "target": "cache", "label": "", "type": "sync"},
            {"source": "s3", "target": "cache", "label": "", "type": "sync"},
        ]
        risks = analyze_risks(comps, conns)
        medium = risks["medium"]
        assert any("contention" in r["issue"].lower() for r in medium)

    def test_risk_summary_counts(self, sample_components, sample_connections):
        risks = analyze_risks(sample_components, sample_connections)
        s = risks["summary"]
        assert s["total"] == s["critical"] + s["high"] + s["medium"] + s["low"]

    def test_external_dependency_risk(self):
        """External component should trigger circuit-breaker recommendation."""
        comps = [
            {"id": "svc", "name": "Payment Svc", "type": "service", "replicas": 1, "technology": ""},
            {"id": "stripe", "name": "Stripe", "type": "external", "replicas": 1, "technology": ""},
        ]
        conns = [{"source": "svc", "target": "stripe", "label": "", "type": "sync"}]
        risks = analyze_risks(comps, conns)
        medium = risks["medium"]
        assert any("circuit" in r["recommendation"].lower() for r in medium)

    def test_empty_architecture(self):
        risks = analyze_risks([], [])
        assert risks["summary"]["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════
#  EXCALIDRAW DIAGRAM GENERATION
# ═══════════════════════════════════════════════════════════════════════════

class TestDiagramGeneration:
    """Tests for generate_excalidraw_elements() and generate_mcp_diagram_elements()."""

    def test_generates_valid_json(self, sample_components, sample_connections):
        result = generate_excalidraw_elements(sample_components, sample_connections)
        elements = json.loads(result["elements_json"])
        assert isinstance(elements, list)
        assert result["element_count"] == len(elements)

    def test_contains_rectangles_and_arrows(self, sample_components, sample_connections):
        result = generate_excalidraw_elements(sample_components, sample_connections)
        elements = json.loads(result["elements_json"])
        types = {e["type"] for e in elements}
        assert "rectangle" in types
        assert "arrow" in types
        assert "text" in types

    def test_element_count_matches(self, sample_components, sample_connections):
        result = generate_excalidraw_elements(sample_components, sample_connections)
        assert result["element_count"] > 0

    def test_empty_architecture(self):
        result = generate_excalidraw_elements([], [])
        elements = json.loads(result["elements_json"])
        assert elements == []

    def test_mcp_diagram_has_bindings(self, sample_components, sample_connections):
        result = generate_mcp_diagram_elements(sample_components, sample_connections)
        elements = json.loads(result["elements_json"])
        arrows = [e for e in elements if e["type"] == "arrow"]
        for arrow in arrows:
            assert "startBinding" in arrow
            assert "endBinding" in arrow

    def test_mcp_diagram_has_camera(self, sample_components, sample_connections):
        result = generate_mcp_diagram_elements(sample_components, sample_connections)
        elements = json.loads(result["elements_json"])
        cameras = [e for e in elements if e["type"] == "cameraUpdate"]
        assert len(cameras) == 1

    def test_mcp_diagram_labeled_rectangles(self, sample_components, sample_connections):
        result = generate_mcp_diagram_elements(sample_components, sample_connections)
        elements = json.loads(result["elements_json"])
        rects = [e for e in elements if e["type"] == "rectangle"]
        for rect in rects:
            assert "label" in rect
            assert "text" in rect["label"]


# ═══════════════════════════════════════════════════════════════════════════
#  COMPONENT MAPPER
# ═══════════════════════════════════════════════════════════════════════════

class TestComponentMapper:
    """Tests for build_component_map()."""

    def test_fan_in_out(self, sample_components, sample_connections):
        cmap = build_component_map(sample_components, sample_connections)
        mapping = {c["id"]: c for c in cmap["component_map"]}
        # API Gateway has 0 fan-in, 1 fan-out (user_service)
        assert mapping["api_gateway"]["fan_in"] == 0
        assert mapping["api_gateway"]["fan_out"] == 1
        # User Service has 1 fan-in (gateway), 2 fan-out (db + cache)
        assert mapping["user_service"]["fan_in"] == 1
        assert mapping["user_service"]["fan_out"] == 2

    def test_statistics(self, sample_components, sample_connections):
        cmap = build_component_map(sample_components, sample_connections)
        stats = cmap["statistics"]
        assert stats["total_components"] == 4
        assert stats["total_connections"] == 3

    def test_orphan_detection(self):
        comps = [
            {"id": "a", "name": "A", "type": "service"},
            {"id": "b", "name": "B", "type": "service"},
            {"id": "orphan", "name": "Orphan", "type": "service"},
        ]
        conns = [{"source": "a", "target": "b", "label": "", "type": "sync"}]
        cmap = build_component_map(comps, conns)
        assert "Orphan" in cmap["statistics"]["orphan_components"]

    def test_empty_architecture(self):
        cmap = build_component_map([], [])
        assert cmap["statistics"]["total_components"] == 0
        assert cmap["statistics"]["total_connections"] == 0


# ═══════════════════════════════════════════════════════════════════════════
#  FILE SAVE / EXPORT
# ═══════════════════════════════════════════════════════════════════════════

class TestFileSave:
    """Tests for save_excalidraw_file() and export_png()."""

    def test_save_excalidraw_creates_file(self, sample_components, sample_connections):
        result = generate_excalidraw_elements(sample_components, sample_connections)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.excalidraw")
            saved = save_excalidraw_file(result["elements_json"], path)
            assert os.path.exists(saved)
            with open(saved, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["type"] == "excalidraw"
            assert data["version"] == 2
            assert data["source"] == "arch-review"
            assert isinstance(data["elements"], list)

    def test_save_excalidraw_filters_pseudo_elements(self, sample_components, sample_connections):
        result = generate_excalidraw_elements(sample_components, sample_connections)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.excalidraw")
            save_excalidraw_file(result["elements_json"], path)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # No cameraUpdate pseudo-elements should be in the saved file
            types = {e["type"] for e in data["elements"]}
            assert "cameraUpdate" not in types

    def test_export_png_creates_file(self, sample_components, sample_connections):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.png")
            saved = export_png(sample_components, sample_connections, path)
            assert os.path.exists(saved)
            assert os.path.getsize(saved) > 0

    def test_export_png_empty_diagram(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "empty.png")
            saved = export_png([], [], path)
            assert os.path.exists(saved)
            assert os.path.getsize(saved) > 0

    def test_export_png_scale_factor(self, sample_components, sample_connections):
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "scale1.png")
            path3 = os.path.join(tmpdir, "scale3.png")
            export_png(sample_components, sample_connections, path1, scale=1.0)
            export_png(sample_components, sample_connections, path3, scale=3.0)
            # Higher scale → larger file
            assert os.path.getsize(path3) > os.path.getsize(path1)

    def test_save_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "test.excalidraw")
            saved = save_excalidraw_file("[]", path)
            assert os.path.exists(saved)


# ═══════════════════════════════════════════════════════════════════════════
#  REPORT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

class TestReportBuilder:
    """Tests for build_review_report()."""

    def test_report_structure(self, sample_components, sample_connections):
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
        report = build_review_report(parsed, risks, cmap, diagram)

        assert "executive_summary" in report
        assert "risk_assessment" in report
        assert "component_map" in report
        assert "diagram" in report
        assert "recommendations" in report
        assert "warnings" in report

    def test_executive_summary_fields(self):
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
        report = build_review_report(parsed, risks, cmap, diagram)
        summary = report["executive_summary"]

        assert "components" in summary
        assert "connections" in summary
        assert "risk_level" in summary
        assert "total_risks" in summary
        assert "format_detected" in summary
        assert summary["format_detected"] == "yaml"

    def test_risk_level_critical(self):
        """Architecture with critical risks should have 'critical' level."""
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = {"element_count": 0}
        report = build_review_report(parsed, risks, cmap, diagram)
        # The YAML has single-replica databases → should be critical
        if risks["summary"]["critical"] > 0:
            assert report["executive_summary"]["risk_level"] == "critical"

    def test_risk_level_healthy(self):
        """Arch with no risks should be 'healthy'."""
        parsed = {"components": [{"id": "a", "name": "A"}], "connections": [],
                  "detected_format": "text"}
        risks = {"critical": [], "high": [], "medium": [], "low": [],
                 "summary": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}}
        cmap = {"component_map": [], "statistics": {"total_components": 1, "total_connections": 0, "orphan_components": []}}
        diagram = {"element_count": 0}
        report = build_review_report(parsed, risks, cmap, diagram)
        assert report["executive_summary"]["risk_level"] == "healthy"

    def test_recommendations_prioritised(self):
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = {"element_count": 0}
        report = build_review_report(parsed, risks, cmap, diagram)
        if report["recommendations"]:
            priorities = [r["priority"] for r in report["recommendations"]]
            # Should be ordered: critical, then high, then medium, then low
            order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(priorities) - 1):
                assert order[priorities[i]] <= order[priorities[i + 1]]

    def test_orphan_warnings(self):
        parsed = {"components": [{"id": "orphan", "name": "Orphan"}], "connections": [],
                  "detected_format": "text"}
        risks = {"critical": [], "high": [], "medium": [], "low": [],
                 "summary": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}}
        cmap = {"component_map": [], "statistics": {"total_components": 1, "total_connections": 0,
                                                     "orphan_components": ["Orphan"]}}
        diagram = {"element_count": 0}
        report = build_review_report(parsed, risks, cmap, diagram)
        assert len(report["warnings"]) >= 1
        assert "Orphan" in report["warnings"][0]


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestUtilities:
    """Tests for helper functions."""

    def test_hex_to_rgb(self):
        assert _hex_to_rgb("#ff0000") == (255, 0, 0)
        assert _hex_to_rgb("#00ff00") == (0, 255, 0)
        assert _hex_to_rgb("#0000ff") == (0, 0, 255)
        assert _hex_to_rgb("ffffff") == (255, 255, 255)
        assert _hex_to_rgb("#000000") == (0, 0, 0)


# ═══════════════════════════════════════════════════════════════════════════
#  END-TO-END: YAML → full pipeline
# ═══════════════════════════════════════════════════════════════════════════

class TestEndToEndPipeline:
    """Full pipeline from YAML/MD/text input to report output."""

    def _run_pipeline(self, content: str) -> dict:
        parsed = parse_architecture(content)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
        return build_review_report(parsed, risks, cmap, diagram)

    def test_yaml_e2e(self):
        report = self._run_pipeline(SAMPLE_YAML)
        assert report["executive_summary"]["components"] == 6
        assert report["executive_summary"]["connections"] == 6
        assert report["executive_summary"]["format_detected"] == "yaml"

    def test_markdown_e2e(self):
        report = self._run_pipeline(SAMPLE_MARKDOWN)
        assert report["executive_summary"]["components"] == 3
        assert report["executive_summary"]["connections"] == 2
        assert report["executive_summary"]["format_detected"] == "markdown"

    def test_text_e2e(self):
        report = self._run_pipeline(SAMPLE_TEXT)
        assert report["executive_summary"]["format_detected"] == "text"
        assert report["executive_summary"]["components"] >= 5

    def test_ecommerce_yaml_e2e(self):
        """Test with the real ecommerce.yaml example file."""
        ecommerce_path = os.path.join(os.path.dirname(__file__), "..", "examples", "ecommerce.yaml")
        if not os.path.exists(ecommerce_path):
            pytest.skip("ecommerce.yaml not found")
        with open(ecommerce_path, "r", encoding="utf-8") as f:
            content = f.read()
        report = self._run_pipeline(content)
        assert report["executive_summary"]["components"] >= 10
        assert report["executive_summary"]["connections"] >= 10

    def test_event_driven_md_e2e(self):
        """Test with the real event_driven.md example file."""
        md_path = os.path.join(os.path.dirname(__file__), "..", "examples", "event_driven.md")
        if not os.path.exists(md_path):
            pytest.skip("event_driven.md not found")
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        report = self._run_pipeline(content)
        assert report["executive_summary"]["components"] >= 5
        assert report["executive_summary"]["connections"] >= 5
        assert report["executive_summary"]["format_detected"] == "markdown"

    def test_pipeline_with_png_export(self):
        """Full pipeline including PNG export."""
        parsed = parse_architecture(SAMPLE_YAML)
        risks = analyze_risks(parsed["components"], parsed["connections"])
        cmap = build_component_map(parsed["components"], parsed["connections"])
        diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            excalidraw_path = os.path.join(tmpdir, "arch.excalidraw")
            png_path = os.path.join(tmpdir, "arch.png")

            save_excalidraw_file(diagram["elements_json"], excalidraw_path)
            export_png(parsed["components"], parsed["connections"], png_path)

            assert os.path.exists(excalidraw_path)
            assert os.path.exists(png_path)

            # Verify Excalidraw file structure
            with open(excalidraw_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["type"] == "excalidraw"
            assert len(data["elements"]) > 0

            # Verify PNG is a valid image
            from PIL import Image
            img = Image.open(png_path)
            assert img.width > 0
            assert img.height > 0
            img.close()
