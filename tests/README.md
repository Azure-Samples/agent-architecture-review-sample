# Testing Guide

This guide walks you through running and understanding the tests for the Architecture Review Agent. No prior testing experience is required.

## What Are These Tests For?

The Architecture Review Agent takes an architecture description (YAML, Markdown, or plain text), analyses it for risks, generates diagrams, and produces a review report. The tests make sure every step of that pipeline works correctly — from parsing your input all the way to downloading the final PNG and Excalidraw files.

## Prerequisites

Make sure you have **Python 3.10+** installed, then install the project dependencies from the repository root:

```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio
```

> **Tip:** If you're using a virtual environment (recommended), activate it first:
>
> ```bash
> # Windows
> python -m venv .venv
> .venv\Scripts\activate
>
> # macOS / Linux
> python -m venv .venv
> source .venv/bin/activate
> ```

## Running the Tests

Open a terminal, navigate to the **project root** (not the `tests/` folder), and run:

```bash
pytest
```

That's it! Pytest automatically finds and runs every test. You'll see output like:

```
tests/test_tools.py::TestFormatDetection::test_detect_yaml PASSED
tests/test_tools.py::TestFormatDetection::test_detect_markdown PASSED
...
```

- **PASSED** means the test succeeded.
- **FAILED** means something is broken — the output will show you what went wrong.
- **SKIPPED** means the test was intentionally skipped (usually because an optional file or service isn't available).

### Useful Commands

| What you want to do | Command |
|---|---|
| Run all tests | `pytest` |
| Run one specific file | `pytest tests/test_tools.py` |
| Run one specific test class | `pytest tests/test_tools.py::TestYamlParser` |
| Run one specific test | `pytest tests/test_api.py::TestHealthEndpoint::test_health_returns_ok` |
| Run tests matching a keyword | `pytest -k "png"` |
| Show full error details | `pytest --tb=long` |
| Stop on first failure | `pytest -x` |

## What's in the `tests/` Folder?

```
tests/
├── __init__.py            # Makes this a Python package (don't delete)
├── conftest.py            # Shared test fixtures (reusable sample data)
├── sample_data.py         # Sample architecture inputs (YAML, Markdown, text)
├── test_api.py            # Tests for the web API endpoints
├── test_integration.py    # End-to-end pipeline tests with real example files
└── test_tools.py          # Unit tests for parsing, risk detection, diagrams, etc.
```

### `conftest.py` — Shared Fixtures

Fixtures are pre-built pieces of test data that pytest injects into tests automatically. You don't need to call them yourself — just know they exist:

| Fixture | What it provides |
|---|---|
| `sample_components` | A small 4-component architecture (gateway, service, database, cache) |
| `sample_connections` | 3 connections wiring those components together |
| `multi_writer_components` | 2 services sharing 1 database (an anti-pattern) |
| `multi_writer_connections` | Connections for the shared-database scenario |
| `frontend_to_db_components` | A frontend talking directly to a database (a security risk) |
| `frontend_to_db_connections` | The direct frontend-to-database connection |

### `sample_data.py` — Sample Inputs

Three architecture descriptions used throughout the tests:

| Constant | Format | What it describes |
|---|---|---|
| `SAMPLE_YAML` | YAML | 6 components (gateway, services, databases, cache) with 6 connections |
| `SAMPLE_MARKDOWN` | Markdown | 3 components (IoT gateway, stream processor, storage) with 2 connections |
| `SAMPLE_TEXT` | Plain text | A chain of 6 components connected with arrows (`->`) |

---

## Test Files Explained

### `test_tools.py` — Core Logic Tests

These test the Python functions in `tools.py` that power the entire application. This is the largest test file and the best place to start understanding how the code works.

**Format Detection** (`TestFormatDetection`)
Checks that the auto-detector correctly identifies whether input is YAML, Markdown, or plain text.

**Type Inference** (`TestTypeInference`)
Checks that component names like "PostgreSQL Database" are correctly classified as `database`, "API Gateway" as `gateway`, "Redis Cache" as `cache`, etc.

**Replica Extraction** (`TestReplicaExtraction`)
Checks that phrases like "3 replicas" or "5 instances" are parsed into the correct numbers.

**YAML Parser** (`TestYamlParser`)
Checks that YAML architecture descriptions are parsed into components and connections. Tests component fields (name, type, technology, replicas), connection labels, metadata, alternate key names (`services` vs `components`), and edge cases like empty YAML.

**Markdown Parser** (`TestMarkdownParser`)
Checks that Markdown with `## Components`, `### Name`, and bullet-point metadata is parsed correctly.

**Plaintext Parser** (`TestPlaintextParser`)
Checks that arrow-based text (`A -> B -> C`) is parsed into components and connections. Tests all supported arrow formats: `->`, `→`, `>>`, `=>`.

**Unified Parser** (`TestParseArchitecture`)
Tests the main `parse_architecture()` function that auto-detects format and falls back gracefully. Checks that components referenced only in connections are automatically created.

**Risk Detection** (`TestRiskDetection`)
Tests the risk analyser that flags architecture problems:
- Single points of failure (1 replica with many dependants)
- Shared database anti-pattern (multiple services writing to one DB)
- Direct frontend-to-database access
- Missing API gateway
- Shared cache contention
- External dependencies without circuit breakers

**Diagram Generation** (`TestDiagramGeneration`)
Checks that Excalidraw diagram elements (rectangles, arrows, labels) are generated correctly in both standard and MCP formats.

**Component Mapper** (`TestComponentMapper`)
Tests fan-in/fan-out metrics, dependency tracking, and orphan component detection.

**File Export** (`TestFileSave`)
Tests saving `.excalidraw` files and exporting PNG images (including valid image verification with Pillow).

**Report Builder** (`TestReportBuilder`)
Tests the final report structure: executive summary, risk levels (`critical`/`needs attention`/`moderate`/`healthy`), prioritised recommendations, and orphan warnings.

**End-to-End Pipeline** (`TestEndToEndPipeline`)
Runs the full flow (parse → risks → diagram → report) for YAML, Markdown, plaintext, and the real example files in `examples/`.

---

### `test_api.py` — Web API Tests

These test the FastAPI endpoints without starting a real server (using FastAPI's built-in `TestClient`).

**Health Check** (`TestHealthEndpoint`)
`GET /api/health` returns status `ok`.

**Review Endpoint** (`TestReviewEndpoint`)
`POST /api/review` accepts YAML, Markdown, or plaintext and returns a complete review report with diagram, risks, and component map. Also tests error handling: empty input (400), oversized input (413), missing fields (422).

**File Upload** (`TestUploadEndpoint`)
`POST /api/review/upload` accepts file uploads in all supported formats. Tests empty files (400) and oversized files (413).

**LLM Inference** (`TestInferEndpoint`)
`POST /api/infer` uses Azure OpenAI to extract architecture from unstructured text. Tests graceful fallback when Azure is not configured.

**File Downloads** (`TestDownloadEndpoints`)
`GET /api/download/png/{run_id}` and `GET /api/download/excalidraw/{run_id}` return the generated diagram files. Tests correct content types and 404 for missing files.

**Security** (`TestSecurity`)
Verifies that path traversal attacks (`../../etc/passwd`) and invalid run IDs are rejected.

---

### `test_integration.py` — End-to-End Tests

These run the full pipeline against the real example files in the `examples/` folder.

**E-Commerce Pipeline** (`TestEcommercePipeline`)
Runs `examples/ecommerce.yaml` through the entire pipeline and verifies: 12+ components extracted, risk patterns detected, PNG is a valid image, all output files created.

**Event-Driven Pipeline** (`TestEventDrivenPipeline`)
Runs `examples/event_driven.md` through the pipeline and checks component types (gateway, queue, database) and fan-in/fan-out metrics.

**Edge Cases** (`TestEdgeCases`)
Tests unusual inputs: single component, self-referencing connections (`A -> A`), 20-service chains, special characters, Unicode names, and concurrent pipeline runs.

**Smart Parse** (`TestSmartParse`)
Tests the async `smart_parse()` function that tries rule-based parsing first, then falls back to LLM inference for vague inputs.

---

## Understanding Test Output

When a test fails, pytest shows you:

1. **Which test failed** — the file, class, and method name
2. **What was expected** vs **what actually happened**
3. **A short traceback** showing where the assertion failed

Example failure output:

```
FAILED tests/test_tools.py::TestYamlParser::test_parse_components
    assert len(result["components"]) == 6
    AssertionError: assert 5 == 6
```

This tells you the YAML parser returned 5 components instead of the expected 6. You'd then look at the parser code in `tools.py` to investigate.

## Common Issues

| Problem | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'tools'` | Run pytest from the **project root**, not from `tests/` |
| `ModuleNotFoundError: No module named 'PIL'` | Run `pip install Pillow` |
| `ModuleNotFoundError: No module named 'pytest'` | Run `pip install pytest pytest-asyncio` |
| Tests marked SKIPPED | Example files may be missing — this is normal and not an error |
| `AZURE_OPENAI_ENDPOINT not set` errors | Expected when running without Azure — LLM tests fall back gracefully |

## Adding Your Own Tests

1. Create a new function starting with `test_` inside an existing class, or create a new class starting with `Test`:

   ```python
   # In test_tools.py
   class TestYamlParser:
       def test_my_new_case(self):
           result = _parse_yaml("components:\n  - name: MyService\n")
           assert len(result["components"]) == 1
   ```

2. Use fixtures from `conftest.py` by adding them as function parameters — pytest injects them automatically:

   ```python
   def test_something(self, sample_components, sample_connections):
       risks = analyze_risks(sample_components, sample_connections)
       assert risks["summary"]["total"] >= 1
   ```

3. For tests that create files, use `tempfile.TemporaryDirectory()` so files are cleaned up automatically:

   ```python
   import tempfile, os
   def test_file_export(self):
       with tempfile.TemporaryDirectory() as tmpdir:
           path = os.path.join(tmpdir, "test.png")
           export_png([], [], path)
           assert os.path.exists(path)
   ```

4. For async tests (like `smart_parse`), add the `@pytest.mark.asyncio` decorator:

   ```python
   @pytest.mark.asyncio
   async def test_async_function(self):
       result = await smart_parse("A -> B")
       assert result["parsing_sufficient"] is True
   ```

5. Run your new test: `pytest -k "test_my_new_case"`
