"""
Architecture Review Agent - Local Tool Functions
==================================================
Pure-Python helpers for architecture parsing, risk detection, Excalidraw
diagram generation, and component mapping.  These are consumed by the
agent via @ai_function wrappers in main.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from typing import Any

import yaml

from agent_framework import ChatMessage
from agent_framework.azure import AzureOpenAIChatClient

logger = logging.getLogger("arch-review")

# ═══════════════════════════════════════════════════════════════════════════
#  1.  ARCHITECTURE PARSER
# ═══════════════════════════════════════════════════════════════════════════

_TYPE_KEYWORDS: dict[str, list[str]] = {
    "database": ["database", "db", "mysql", "postgres", "mongodb", "redis", "sql", "dynamodb", "cosmos", "firestore"],
    "cache":    ["cache", "redis", "memcached", "cdn"],
    "queue":    ["queue", "kafka", "rabbitmq", "sqs", "event hub", "eventhub", "pubsub", "nats"],
    "gateway":  ["gateway", "api gateway", "load balancer", "lb", "nginx", "envoy", "ingress"],
    "frontend": ["frontend", "ui", "spa", "react", "angular", "vue", "web app", "client"],
    "storage":  ["storage", "s3", "blob", "bucket", "file"],
    "external": ["external", "third-party", "3rd party", "stripe", "twilio", "sendgrid"],
    "monitoring": ["monitor", "logging", "metrics", "prometheus", "grafana", "datadog", "elastic"],
}


def _infer_type(text: str) -> str:
    lower = text.lower()
    for comp_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return comp_type
    return "service"


def _extract_replicas(text: str) -> int:
    # e.g. "3 replica", "5 instances", "2 nodes"
    m = re.search(r"(\d+)\s*(?:replica|instance|node|pod)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Leading count in name, e.g. "3 API servers" or "2 backends"
    m2 = re.match(r"^(\d+)\s+\w", text.strip())
    if m2:
        return int(m2.group(1))
    return 1


def _strip_leading_count(text: str) -> str:
    """Remove a leading numeric count from a component name.

    ``"3 API servers"`` → ``"API servers"``  (replicas extracted separately).
    Only strips when the remainder is ≥2 words to avoid stripping names like
    ``"5th generation service"``.
    """
    m = re.match(r"^(\d+)\s+(.+)", text.strip())
    if m and len(m.group(2).split()) >= 1:
        return m.group(2)
    return text


def _sanitize_component_name(raw: str) -> str:
    """Clean component names extracted from free-form text.

    Prevents inline explanatory prose from being absorbed into node names,
    e.g. ``Redis cache. Auth handled by API`` -> ``Redis cache``.
    """
    text = raw.strip().lstrip("-* ").strip().strip('"\'`')
    if not text:
        return text

    # Split trailing prose sentences while preserving names like "Node.js".
    text = re.split(r"(?<=[a-z0-9])\.\s+(?=[A-Z])", text, maxsplit=1)[0]

    # Remove trailing punctuation noise.
    text = re.sub(r"[\s,;:.]+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_flat_markdown(content: str) -> str:
    """Rehydrate markdown that was flattened to a single line.

    This commonly happens when invoking local agent CLI with
    `(Get-Content file) -join " "`.
    """
    if "\n" in content:
        return content
    if "## " not in content and "### " not in content:
        return content

    text = content
    # Headings
    text = re.sub(r"\s+(##\s+)", r"\n\1", text)
    text = re.sub(r"\s+(###\s+)", r"\n\1", text)
    # Bullets (but avoid arrow syntax like '->')
    text = re.sub(r"\s+-\s+(?!>)", r"\n- ", text)
    return text.strip()


def _truncate_component_label(text: str, max_chars: int = 34) -> str:
    """Keep node labels short enough to fit diagram boxes."""
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= max_chars else (t[: max_chars - 3].rstrip() + "...")


def _parse_flattened_yaml_payload(content: str) -> dict[str, Any] | None:
    """Parse YAML-like payloads that were flattened to one line.

    Local invocations often use `(Get-Content file) -join " "`, which can
    collapse valid YAML into a single line that `yaml.safe_load` cannot parse
    reliably (especially when the file starts with comment lines).
    """
    if "\n" in content:
        return None

    lower = content.lower()
    if "components:" not in lower:
        return None

    # Drop any leading prose/comments before the schema starts.
    start = lower.find("components:")
    if start > 0:
        content = content[start:]

    known_keys = "name|type|technology|replicas|description|from|to|target|source|protocol|label"

    def _extract_field(block: str, key: str) -> str:
        pat = rf"\b{key}:\s*(.+?)(?=\s+\b(?:{known_keys})\b:|$)"
        m = re.search(pat, block, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    sections = re.split(r"\bconnections\s*:", content, maxsplit=1, flags=re.IGNORECASE)
    comp_text = sections[0]
    conn_text = sections[1] if len(sections) > 1 else ""

    components: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    comp_iter = re.finditer(
        r"-\s+name:\s*(.+?)(?=\s+-\s+name:|\s+connections:|$)",
        comp_text,
        re.IGNORECASE,
    )
    for m in comp_iter:
        block = m.group(1).strip()
        name = re.split(r"\s+\b(?:type|technology|replicas|description)\b:\s*", block, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        name = _sanitize_component_name(name)
        if not name:
            continue

        cid = re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")
        rtxt = _extract_field(block, "replicas")
        components.append({
            "id": cid,
            "name": name,
            "type": (_extract_field(block, "type") or _infer_type(name)).lower(),
            "description": _extract_field(block, "description"),
            "replicas": int(rtxt) if rtxt.isdigit() else 1,
            "technology": _extract_field(block, "technology"),
        })

    conn_iter = re.finditer(
        r"-\s+(?:from|source):\s*(.+?)(?=\s+-\s+(?:from|source):|$)",
        conn_text,
        re.IGNORECASE,
    )
    for m in conn_iter:
        block = m.group(1).strip()
        src = re.split(r"\s+\b(?:to|target|protocol|label|description)\b:\s*", block, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        tgt = _extract_field(block, "to") or _extract_field(block, "target")
        if not src or not tgt:
            continue

        source_id = re.sub(r"[^a-z0-9]", "_", _sanitize_component_name(src).lower()).strip("_")
        target_id = re.sub(r"[^a-z0-9]", "_", _sanitize_component_name(tgt).lower()).strip("_")
        if not source_id or not target_id:
            continue

        connections.append({
            "source": source_id,
            "target": target_id,
            "label": _extract_field(block, "protocol") or _extract_field(block, "label"),
            "type": "sync",
        })

    if not components and not connections:
        return None

    return {
        "components": components,
        "connections": connections,
        "metadata": {},
        "detected_format": "yaml",
    }


_ARCH_YAML_KEYS = frozenset(
    "components services nodes connections edges flows links"
    " name type technology replicas description from to source target".split()
)


def _detect_format(content: str) -> str:
    stripped = content.strip()
    # YAML: must start with a document marker OR have a key that looks like a
    # known architecture keyword (not just any English sentence ending in ':')
    if stripped.startswith("---") or re.search(
        r"^(?:" + "|".join(_ARCH_YAML_KEYS) + r")\s*:",
        stripped, re.MULTILINE | re.IGNORECASE,
    ):
        try:
            data = yaml.safe_load(stripped)
            if isinstance(data, dict) and _ARCH_YAML_KEYS & set(data.keys()):
                return "yaml"
        except yaml.YAMLError:
            pass
    if re.search(r"^#{1,3}\s+", stripped, re.MULTILINE):
        return "markdown"
    return "text"


def _parse_yaml(content: str) -> dict[str, Any]:
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return {"components": [], "connections": [], "metadata": {}}

    components: list[dict] = []
    connections: list[dict] = []

    for key in ("components", "services", "nodes"):
        for item in data.get(key, []) or []:
            if isinstance(item, dict):
                components.append({
                    "id": item.get("id") or item.get("name", "").lower().replace(" ", "_"),
                    "name": item.get("name", item.get("id", "unknown")),
                    "type": item.get("type", "service"),
                    "description": item.get("description", ""),
                    "replicas": item.get("replicas", 1),
                    "technology": item.get("technology", ""),
                })
            elif isinstance(item, str):
                cid = item.lower().replace(" ", "_").replace("-", "_")
                components.append({"id": cid, "name": item, "type": "service",
                                   "description": "", "replicas": 1, "technology": ""})

    for key in ("connections", "edges", "flows", "links"):
        for item in data.get(key, []) or []:
            if isinstance(item, dict):
                connections.append({
                    "source": (item.get("from") or item.get("source", "")).lower().replace(" ", "_"),
                    "target": (item.get("to") or item.get("target", "")).lower().replace(" ", "_"),
                    "label": item.get("label") or item.get("protocol", ""),
                    "type": item.get("type", "sync"),
                })
            elif isinstance(item, str):
                parts = re.split(r"\s*(?:->|→|>>)\s*", item)
                if len(parts) == 2:
                    connections.append({
                        "source": parts[0].strip().lower().replace(" ", "_"),
                        "target": parts[1].strip().lower().replace(" ", "_"),
                        "label": "", "type": "sync",
                    })

    metadata = {k: v for k, v in data.items()
                if k not in ("components", "services", "nodes", "connections", "edges", "flows", "links")}
    return {"components": components, "connections": connections, "metadata": metadata}


def _parse_markdown(content: str) -> dict[str, Any]:
    components: list[dict] = []
    connections: list[dict] = []
    top_section = ""
    current_comp: dict | None = None

    for line in content.split("\n"):
        # Top-level sections: ## Components, ## Connections
        h2 = re.match(r"^##\s+(.+)", line)
        if h2:
            if current_comp:
                components.append(current_comp)
                current_comp = None

            section_raw = h2.group(1).strip()
            inline_tail = ""
            if " - " in section_raw:
                head, tail = section_raw.split(" - ", 1)
                top_section = head.strip().lower()
                inline_tail = tail.strip()
            else:
                top_section = section_raw.lower()

            # Flattened markdown can carry connections inline on the section line:
            # "## Connections - A -> B (...) - B -> C (...)"
            if inline_tail and any(k in top_section for k in ("connection", "flow", "edge", "link")):
                for candidate in [c.strip() for c in re.split(r"\s+-\s+", inline_tail) if c.strip()]:
                    parts = re.split(r"\s*(?:->|→|>>)\s*", candidate)
                    if len(parts) >= 2:
                        src = parts[0].strip()
                        tgt_raw = parts[1].strip()
                        tgt_m = re.match(r"^(.+?)\s*\(.+\)$", tgt_raw)
                        tgt = tgt_m.group(1).strip() if tgt_m else tgt_raw
                        label_m = re.search(r"\((.+?)\)", tgt_raw)
                        label = label_m.group(1) if label_m else ""
                        connections.append({
                            "source": re.sub(r"[^a-z0-9]", "_", src.lower()).strip("_"),
                            "target": re.sub(r"[^a-z0-9]", "_", tgt.lower()).strip("_"),
                            "label": label,
                            "type": "sync",
                        })
            continue

        # Component headers: ### Name
        h3 = re.match(r"^###\s+(.+)", line)
        if h3:
            if current_comp:
                components.append(current_comp)
            raw = h3.group(1).strip()
            # Support flattened markdown where metadata is inline, e.g.
            # "### Edge Gateway - **Type:** gateway - **Replicas:** 10"
            parts = [p.strip() for p in re.split(r"\s+-\s+", raw) if p.strip()]
            name = parts[0] if parts else raw
            cid = re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")
            current_comp = {"id": cid, "name": name, "type": "service",
                            "description": "", "replicas": 1, "technology": ""}

            # Parse optional inline metadata segments after the name.
            for part in parts[1:]:
                lower = part.lower()
                if lower.startswith("**type:**"):
                    current_comp["type"] = re.sub(r"^\*\*type:\*\*\s*", "", part, flags=re.IGNORECASE).strip().lower()
                elif lower.startswith("**technology:**"):
                    current_comp["technology"] = re.sub(r"^\*\*technology:\*\*\s*", "", part, flags=re.IGNORECASE).strip()
                elif lower.startswith("**replicas:**"):
                    val = re.sub(r"^\*\*replicas:\*\*\s*", "", part, flags=re.IGNORECASE).strip()
                    if val.isdigit():
                        current_comp["replicas"] = int(val)
                else:
                    # Treat any remaining inline segment as description text.
                    current_comp["description"] = (current_comp["description"] + " " + part).strip()
            continue

        bullet = re.match(r"^\s*[-*]\s+(.+)", line)
        if not bullet:
            continue
        text = bullet.group(1).strip()

        # Inside a component definition - parse metadata bullets
        if current_comp and "component" in top_section:
            type_m = re.match(r"\*\*Type:\*\*\s*(.+)", text)
            tech_m = re.match(r"\*\*Technology:\*\*\s*(.+)", text)
            rep_m = re.match(r"\*\*Replicas:\*\*\s*(\d+)", text)
            if type_m:
                current_comp["type"] = type_m.group(1).strip().lower()
                continue
            if tech_m:
                current_comp["technology"] = tech_m.group(1).strip()
                continue
            if rep_m:
                current_comp["replicas"] = int(rep_m.group(1))
                continue
            # Remaining bullets are description
            current_comp["description"] = text
            continue

        # Inside connections section
        if any(k in top_section for k in ("connection", "flow", "edge", "link")):
            parts = re.split(r"\s*(?:->|→|>>)\s*", text)
            if len(parts) >= 2:
                src = parts[0].strip()
                tgt_raw = parts[1].strip()
                tgt_m = re.match(r"^(.+?)\s*\(.+\)$", tgt_raw)
                tgt = tgt_m.group(1).strip() if tgt_m else tgt_raw
                label_m = re.search(r"\((.+?)\)", tgt_raw)
                label = label_m.group(1) if label_m else ""
                connections.append({
                    "source": re.sub(r"[^a-z0-9]", "_", src.lower()).strip("_"),
                    "target": re.sub(r"[^a-z0-9]", "_", tgt.lower()).strip("_"),
                    "label": label,
                    "type": "sync",
                })

    if current_comp:
        components.append(current_comp)

    return {"components": components, "connections": connections, "metadata": {}}


def _parse_text(content: str) -> dict[str, Any]:
    components: list[dict] = []
    connections: list[dict] = []
    seen: set[str] = set()

    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        arrow = re.split(r"\s*(?:->|→|>>|=>)\s*", line)
        if len(arrow) >= 2:
            # Support chained arrows: A -> B -> C creates edges A→B, B→C
            parts = [_sanitize_component_name(p) for p in arrow]
            for idx in range(len(parts) - 1):
                src, tgt = parts[idx], parts[idx + 1]
                # Extract replica count from leading number, e.g. "3 API servers"
                src_replicas = _extract_replicas(src)
                tgt_replicas = _extract_replicas(tgt)
                src = _strip_leading_count(src)
                tgt = _strip_leading_count(tgt)
                sid = re.sub(r"[^a-z0-9]", "_", src.lower()).strip("_")
                tid = re.sub(r"[^a-z0-9]", "_", tgt.lower()).strip("_")
                if not sid or not tid:
                    continue
                connections.append({"source": sid, "target": tid, "label": "", "type": "sync"})
                for cid, cname, creplicas in [(sid, src, src_replicas), (tid, tgt, tgt_replicas)]:
                    if cid not in seen:
                        seen.add(cid)
                        components.append({"id": cid, "name": cname, "type": _infer_type(cname),
                                           "description": "", "replicas": creplicas, "technology": ""})
            continue
        m = re.match(r"^\s*[-*]\s+(.+)", line)
        text = m.group(1).strip() if m else line
        name_m = re.match(r"^(.+?)(?:\s*\((.+)\))?$", text)
        name = _sanitize_component_name(name_m.group(1).strip() if name_m else text)
        desc = name_m.group(2).strip() if name_m and name_m.group(2) else ""
        cid = re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")
        if cid and cid not in seen:
            seen.add(cid)
            components.append({"id": cid, "name": name, "type": _infer_type(name + " " + desc),
                               "description": desc, "replicas": _extract_replicas(desc), "technology": ""})

    return {"components": components, "connections": connections, "metadata": {}}


_PROSE_PREFIX_RE = re.compile(
    # Match a conversational phrase ending with ": ".
    # Requires at least one interior space (multi-word phrase) to avoid matching
    # single-word YAML keys like "name:", "components:", or "connections:".
    r"^[A-Za-z][^:\n]*\s[^:\n]{1,60}:\s+",
    re.DOTALL,
)


def _strip_leading_prose(content: str) -> str:
    """Remove a short conversational prefix before structured content.

    Handles inputs like:
    - ``"Review my architecture: Load Balancer -> ..."``
    - ``"Analyse this design and highlight risks: ## Components ..."``

    Only strips when the prefix is clearly multi-word (not a bare YAML key)
    and the remainder looks like structured content (heading, arrow, or YAML key).
    """
    m = _PROSE_PREFIX_RE.match(content.strip())
    if not m:
        return content
    remainder = content.strip()[m.end():].lstrip()
    # Only strip if remainder begins with something structural
    if re.match(r"(?:#{1,3}\s|---\s*\n|[\w][\w\s]*:\s*(?:\S|-)|.+\s*(?:->|→|>>))", remainder):
        logger.debug("[PARSER] Stripped leading prose prefix: %r", m.group(0))
        return remainder
    return content


def parse_architecture(content: str, format_hint: str = "auto") -> dict[str, Any]:
    """Parse architecture description (YAML / Markdown / plaintext) into
    ``{"components": [...], "connections": [...], "detected_format": str}``.

    If the rule-based parser extracts too few results (≤1 component with no
    connections) and ``llm_fallback`` isn't explicitly disabled, the original
    content is returned with a flag so the caller can decide to invoke the
    LLM-based inference.
    """
    # Strip a short conversational prefix found in direct agent invocations.
    content = _strip_leading_prose(content)

    # Special handling for one-line YAML payloads from `Get-Content ... -join " "`.
    flat_yaml = _parse_flattened_yaml_payload(content)
    if flat_yaml is not None:
        result = flat_yaml
    else:
        content = _normalize_flat_markdown(content)
        fmt = format_hint if format_hint != "auto" else _detect_format(content)
        logger.debug("[PARSER] Detected format: %s (hint=%s)", fmt, format_hint)
        result = {"yaml": _parse_yaml, "markdown": _parse_markdown}.get(fmt, _parse_text)(content)
        result["detected_format"] = fmt

    # Back-fill components referenced only in connections
    known = {c["id"] for c in result["components"]}
    for conn in result["connections"]:
        for role in ("source", "target"):
            if conn[role] not in known:
                result["components"].append({
                    "id": conn[role], "name": conn[role].replace("_", " ").title(),
                    "type": "service", "description": "(auto-discovered)", "replicas": 1, "technology": "",
                })
                known.add(conn[role])

    # Check if parsing extracted meaningful results
    n_comp = len(result["components"])
    n_conn = len(result["connections"])
    result["parsing_sufficient"] = (n_comp >= 2) or (n_comp >= 1 and n_conn >= 1)
    logger.debug("[PARSER] Rule-based result: %d components, %d connections, sufficient=%s",
                 n_comp, n_conn, result["parsing_sufficient"])

    return result


# ═══════════════════════════════════════════════════════════════════════════
#  1b. LLM-BASED ARCHITECTURE INFERENCE
# ═══════════════════════════════════════════════════════════════════════════

_LLM_INFERENCE_PROMPT = """\
You are an expert software architect.  Analyse the following content - it may be
a README, design document, code file, deployment manifest, infrastructure config,
or any other text that describes or implies a software system architecture.

**Your task:** extract a structured architecture description in JSON with exactly
this schema:

```json
{
  "architecture_name": "<short title for the system>",
  "components": [
    {
      "id": "<snake_case_id>",
      "name": "<Display Name>",
      "type": "<one of: frontend, gateway, service, database, cache, queue, storage, external, monitoring>",
      "description": "<brief purpose>",
      "technology": "<tech stack if mentioned, else empty string>",
      "replicas": <number, default 1>
    }
  ],
  "connections": [
    {
      "source": "<component id>",
      "target": "<component id>",
      "label": "<protocol or description>",
      "type": "sync"
    }
  ],
  "risks": [
    {
      "component": "<Display Name of affected component>",
      "severity": "<critical | high | medium | low>",
      "issue": "<one-liner describing the problem>",
      "recommendation": "<one-liner actionable fix>"
    }
  ]
}
```

**Rules:**
1. Infer component types from context (names, descriptions, technology).
2. Create connections based on data flow, API calls, event publishing, or any
   dependency you can infer - even if not explicitly stated as arrows.
3. If the text only lists services without explicit connections, infer likely
   connections based on common architectural patterns.
4. Use snake_case for all IDs.  Names should be human-readable.
5. Include ALL components you can identify - even infrastructure (load balancers,
   message queues, caches, databases, monitoring).
6. If the input is too vague to extract any architecture, return an empty
   components array with a note in architecture_name.
7. Return ONLY valid JSON - no markdown fences, no commentary.
8. For risks: identify SPOFs, missing redundancy, shared-DB anti-patterns,
   security gaps, scalability bottlenecks, and missing observability.
   Each issue and recommendation MUST be exactly one concise sentence.
"""


async def infer_architecture_llm(content: str) -> dict[str, Any]:
    """Use Azure OpenAI to analyse **any** text and extract an architecture.

    Works with READMEs, design docs, code, plain descriptions, infra configs, etc.
    Falls back gracefully if Azure OpenAI is not configured.

    Uses ``AzureOpenAIChatClient`` from the agent framework which natively
    handles Azure endpoints, api-version, and authentication.  Reads config
    from env vars: ``AZURE_OPENAI_ENDPOINT``, ``AZURE_OPENAI_API_KEY``,
    ``AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`` / ``MODEL_DEPLOYMENT_NAME``.

    Returns the same ``{"components": [...], "connections": [...], ...}``
    schema as ``parse_architecture()``.
    """
    logger.debug("[LLM] Starting LLM inference (input length: %d chars)", len(content))

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    deployment = (
        os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4.1")
    )

    if not endpoint:
        logger.debug("[LLM] AZURE_OPENAI_ENDPOINT not set - skipping LLM")
        return _llm_error("AZURE_OPENAI_ENDPOINT not set - LLM inference unavailable")
    logger.debug("[LLM] Using endpoint=%s, deployment=%s", endpoint, deployment)
    try:
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        if api_key:
            logger.debug("[LLM] Using API key authentication")
            client = AzureOpenAIChatClient(
                endpoint=endpoint,
                deployment_name=deployment,
                api_key=api_key,
            )
        else:
            logger.debug("[LLM] Using DefaultAzureCredential authentication")
            from azure.identity import DefaultAzureCredential
            client = AzureOpenAIChatClient(
                endpoint=endpoint,
                deployment_name=deployment,
                credential=DefaultAzureCredential(),
            )

        response = await client.get_response(
            messages=[
                ChatMessage(role="system", text=_LLM_INFERENCE_PROMPT),
                ChatMessage(role="user", text=content[:12000]),
            ],
            temperature=0.1,
        )

        raw = response.text or "{}"
        data = json.loads(raw)
        logger.debug("[LLM] Response received - %d components, %d connections inferred",
                     len(data.get("components", [])), len(data.get("connections", [])))
    except Exception as exc:
        logger.debug("[LLM] Call failed: %s", exc)
        return _llm_error(f"LLM call failed: {exc}")

    # Normalise into our standard schema
    components: list[dict] = []
    for c in data.get("components", []):
        cid = c.get("id") or re.sub(r"[^a-z0-9]", "_", c.get("name", "unknown").lower()).strip("_")
        components.append({
            "id": cid,
            "name": c.get("name", cid.replace("_", " ").title()),
            "type": c.get("type", _infer_type(c.get("name", "") + " " + c.get("technology", ""))),
            "description": c.get("description", ""),
            "technology": c.get("technology", ""),
            "replicas": c.get("replicas", 1),
        })

    connections: list[dict] = []
    known_ids = {c["id"] for c in components}
    for conn in data.get("connections", []):
        src = conn.get("source", "")
        tgt = conn.get("target", "")
        if src and tgt:
            connections.append({
                "source": src,
                "target": tgt,
                "label": conn.get("label", ""),
                "type": conn.get("type", "sync"),
            })
            # Back-fill components referenced only in connections
            for role_id, role_name in [(src, src), (tgt, tgt)]:
                if role_id not in known_ids:
                    components.append({
                        "id": role_id,
                        "name": role_id.replace("_", " ").title(),
                        "type": _infer_type(role_id),
                        "description": "(LLM-inferred)",
                        "replicas": 1,
                        "technology": "",
                    })
                    known_ids.add(role_id)

    # Normalise LLM-generated risks
    llm_risks: list[dict] = []
    for r in data.get("risks", []):
        sev = r.get("severity", "medium")
        if sev not in ("critical", "high", "medium", "low"):
            sev = "medium"
        llm_risks.append({
            "component": r.get("component", "Architecture"),
            "severity": sev,
            "issue": r.get("issue", ""),
            "recommendation": r.get("recommendation", ""),
        })

    return {
        "components": components,
        "connections": connections,
        "metadata": {"architecture_name": data.get("architecture_name", "")},
        "detected_format": "llm-inferred",
        "llm_inferred": True,
        "llm_risks": llm_risks,
        "parsing_sufficient": len(components) >= 1,
    }


def _llm_error(msg: str) -> dict[str, Any]:
    return {
        "components": [], "connections": [], "metadata": {},
        "detected_format": "unstructured", "llm_inferred": True,
        "parsing_sufficient": False, "error": msg,
    }


async def smart_parse(content: str, format_hint: str = "auto") -> dict[str, Any]:
    """Parse architecture with automatic LLM fallback.

    1. Try the fast rule-based parser first.
    2. If it extracts too few results, invoke the LLM to analyse the content.
    3. Return whichever result has more meaningful data.
    """
    logger.debug("[SMART_PARSE] Starting - format_hint=%s", format_hint)
    result = parse_architecture(content, format_hint)
    if result["parsing_sufficient"]:
        logger.info("[SMART_PARSE] Using RULE-BASED parser (%s) - %d components, %d connections",
                    result["detected_format"], len(result["components"]), len(result["connections"]))
        return result

    # Rule-based parsing was insufficient - try LLM inference
    logger.info("[SMART_PARSE] Rule-based insufficient (%d components) - falling back to LLM",
                len(result["components"]))
    llm_result = await infer_architecture_llm(content)
    if llm_result.get("error"):
        logger.warning("[SMART_PARSE] LLM fallback failed: %s - using rule-based result",
                       llm_result["error"])
        # LLM unavailable - return whatever we got from rule-based
        return result

    logger.info("[SMART_PARSE] Using LLM-INFERRED result - %d components, %d connections",
                len(llm_result["components"]), len(llm_result["connections"]))
    return llm_result


# ═══════════════════════════════════════════════════════════════════════════
#  2.  RISK DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

def _detect_spof(comps: list[dict], conns: list[dict]) -> list[dict]:
    risks: list[dict] = []
    fan_in: dict[str, int] = {}
    for c in conns:
        fan_in[c["target"]] = fan_in.get(c["target"], 0) + 1
    for comp in comps:
        replicas = comp.get("replicas", 1)
        if replicas <= 1 and fan_in.get(comp["id"], 0) >= 2:
            risks.append({"component": comp["name"], "severity": "critical",
                          "issue": f"Single point of failure - {fan_in[comp['id']]} dependants, 1 replica",
                          "recommendation": f"Scale {comp['name']} to ≥2 replicas behind a load balancer"})
        elif replicas <= 1 and comp.get("type") in ("gateway", "database", "cache", "queue"):
            risks.append({"component": comp["name"], "severity": "critical",
                          "issue": f"Infrastructure '{comp['type']}' has no redundancy",
                          "recommendation": f"Deploy {comp['name']} in HA configuration (cluster / multi-AZ)"})
    return risks


def _detect_scalability(comps: list[dict], conns: list[dict]) -> list[dict]:
    fan_in: dict[str, int] = {}
    for c in conns:
        fan_in[c["target"]] = fan_in.get(c["target"], 0) + 1
    return [
        {"component": comp["name"], "severity": "medium",
         "issue": f"Shared {comp['type']} used by {fan_in[comp['id']]} services - contention risk",
         "recommendation": f"Consider per-service {comp['type']} or partitioning"}
        for comp in comps
        if comp.get("type") in ("cache", "database", "queue") and fan_in.get(comp["id"], 0) >= 3
    ]


def _detect_security(comps: list[dict], conns: list[dict]) -> list[dict]:
    risks: list[dict] = []
    has_gw = any(c.get("type") == "gateway" for c in comps)
    has_fe = any(c.get("type") == "frontend" for c in comps)
    if has_fe and not has_gw:
        risks.append({"component": "Architecture", "severity": "high",
                      "issue": "Frontend talks to backend without an API Gateway",
                      "recommendation": "Introduce an API Gateway for auth, rate-limiting, and routing"})
    db_ids = {c["id"] for c in comps if c.get("type") == "database"}
    fe_ids = {c["id"] for c in comps if c.get("type") == "frontend"}
    for conn in conns:
        if conn["source"] in fe_ids and conn["target"] in db_ids:
            risks.append({"component": conn["target"], "severity": "critical",
                          "issue": "Frontend has direct database access",
                          "recommendation": "Route DB access through backend services"})
    for ext in (c for c in comps if c.get("type") == "external"):
        risks.append({"component": ext["name"], "severity": "medium",
                      "issue": f"External dependency '{ext['name']}' - no circuit-breaker",
                      "recommendation": f"Add circuit-breaker / retry for calls to {ext['name']}"})
    return risks


def _detect_anti_patterns(comps: list[dict], conns: list[dict]) -> list[dict]:
    db_ids = {c["id"] for c in comps if c.get("type") == "database"}
    writers: dict[str, list[str]] = {}
    for conn in conns:
        if conn["target"] in db_ids:
            writers.setdefault(conn["target"], []).append(conn["source"])
    return [
        {"component": next((c["name"] for c in comps if c["id"] == db_id), db_id),
         "severity": "high",
         "issue": f"Shared DB anti-pattern - {len(w)} services write to same database",
         "recommendation": "Give each service its own data store"}
        for db_id, w in writers.items() if len(w) > 1
    ]


def analyze_risks(components: list[dict], connections: list[dict]) -> dict[str, Any]:
    """Run all risk detectors. Returns severity-bucketed assessment."""
    all_risks: list[dict] = []
    all_risks.extend(_detect_spof(components, connections))
    all_risks.extend(_detect_scalability(components, connections))
    all_risks.extend(_detect_security(components, connections))
    all_risks.extend(_detect_anti_patterns(components, connections))

    result: dict[str, Any] = {"critical": [], "high": [], "medium": [], "low": []}
    for r in all_risks:
        result[r.get("severity", "medium")].append(r)
    result["summary"] = {
        "total": len(all_risks),
        "critical": len(result["critical"]), "high": len(result["high"]),
        "medium": len(result["medium"]), "low": len(result["low"]),
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  3.  EXCALIDRAW DIAGRAM RENDERER
# ═══════════════════════════════════════════════════════════════════════════

_COLORS: dict[str, dict[str, str]] = {
    "frontend":   {"bg": "#a5d8ff", "border": "#1971c2"},
    "gateway":    {"bg": "#d0bfff", "border": "#7048e8"},
    "service":    {"bg": "#b2f2bb", "border": "#2f9e44"},
    "database":   {"bg": "#ffec99", "border": "#e67700"},
    "cache":      {"bg": "#ffd8a8", "border": "#e8590c"},
    "queue":      {"bg": "#eebefa", "border": "#be4bdb"},
    "storage":    {"bg": "#d3f9d8", "border": "#37b24d"},
    "external":   {"bg": "#ffc9c9", "border": "#e03131"},
    "monitoring": {"bg": "#dee2e6", "border": "#495057"},
}
_DEFAULT_COL = {"bg": "#e7f5ff", "border": "#1c7ed6"}
_W, _H = 200, 80


def _layout(comps: list[dict]) -> dict[str, tuple[int, int]]:
    layer_order = {"frontend": 0, "gateway": 0, "service": 1,
                   "database": 2, "cache": 2, "queue": 2, "storage": 2,
                   "external": 2, "monitoring": 3}
    layers: dict[int, list[dict]] = {}
    for c in comps:
        layers.setdefault(layer_order.get(c.get("type", "service"), 1), []).append(c)
    positions: dict[str, tuple[int, int]] = {}
    x_gap, y_gap = 300, 250
    for li in sorted(layers):
        items = layers[li]
        start_x = -(len(items) * x_gap) // 2 + x_gap // 2
        for i, comp in enumerate(items):
            positions[comp["id"]] = (start_x + i * x_gap, li * y_gap)
    return positions


def _rect(cid: str, name: str, ctype: str, x: int, y: int) -> list[dict]:
    col = _COLORS.get(ctype, _DEFAULT_COL)
    short_name = _truncate_component_label(name)
    return [
        {"type": "rectangle", "id": cid, "x": x, "y": y, "width": _W, "height": _H,
         "strokeColor": col["border"], "backgroundColor": col["bg"],
         "fillStyle": "solid", "roundness": {"type": 3}},
        {"type": "text", "id": f"{cid}_lbl", "x": x + 10, "y": y + 12,
         "width": _W - 20, "height": 24, "text": short_name, "fontSize": 18,
         "textAlign": "center", "strokeColor": "#1e1e1e"},
        {"type": "text", "id": f"{cid}_tag", "x": x + 10, "y": y + 44,
         "width": _W - 20, "height": 16, "text": f"[{ctype.upper()}]",
         "fontSize": 12, "textAlign": "center", "strokeColor": "#868e96"},
    ]


def _arrow(aid: str, sx: int, sy: int, tx: int, ty: int, label: str = "") -> list[dict]:
    if abs(sy - ty) < 50:
        x0, y0 = sx + _W, sy + _H // 2
        x1, y1 = tx, ty + _H // 2
    else:
        x0, y0 = sx + _W // 2, sy + _H
        x1, y1 = tx + _W // 2, ty
    dx, dy = x1 - x0, y1 - y0
    elems: list[dict] = [{"type": "arrow", "id": aid, "x": x0, "y": y0,
                          "width": abs(dx), "height": abs(dy), "strokeColor": "#495057",
                          "points": [[0, 0], [dx, dy]],
                          "startArrowhead": None, "endArrowhead": "arrow"}]
    if label:
        elems.append({"type": "text", "id": f"{aid}_lbl",
                      "x": x0 + dx // 2 - 40, "y": y0 + dy // 2 - 10,
                      "width": 80, "height": 16, "text": label,
                      "fontSize": 12, "textAlign": "center", "strokeColor": "#868e96"})
    return elems


def generate_excalidraw_elements(components: list[dict], connections: list[dict]) -> dict[str, Any]:
    """Build Excalidraw elements JSON. Returns ``{"elements_json": str, "element_count": int}``."""
    pos = _layout(components)
    elems: list[dict] = []
    # camera pseudo-element
    if pos:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        elems.append({"type": "cameraUpdate",
                      "x": min(xs) - 100, "y": min(ys) - 80,
                      "width": max(xs) + _W + 100 - (min(xs) - 100),
                      "height": max(ys) + _H + 80 - (min(ys) - 80)})
    for comp in components:
        p = pos.get(comp["id"], (0, 0))
        elems.extend(_rect(comp["id"], comp["name"], comp.get("type", "service"), p[0], p[1]))
    for i, conn in enumerate(connections):
        sp, tp = pos.get(conn["source"], (0, 0)), pos.get(conn["target"], (0, 0))
        elems.extend(_arrow(f"conn_{i}", sp[0], sp[1], tp[0], tp[1], conn.get("label", "")))
    return {"elements_json": json.dumps(elems), "element_count": len(elems)}


# ═══════════════════════════════════════════════════════════════════════════
#  4.  COMPONENT MAPPER
# ═══════════════════════════════════════════════════════════════════════════

def build_component_map(components: list[dict], connections: list[dict]) -> dict[str, Any]:
    """Dependency map with fan-in/fan-out metrics."""
    outgoing: dict[str, list[str]] = {}
    incoming: dict[str, list[str]] = {}
    for conn in connections:
        outgoing.setdefault(conn["source"], []).append(conn["target"])
        incoming.setdefault(conn["target"], []).append(conn["source"])

    cmap = [
        {"id": c["id"], "name": c["name"], "type": c.get("type", "service"),
         "depends_on": outgoing.get(c["id"], []), "depended_by": incoming.get(c["id"], []),
         "fan_in": len(incoming.get(c["id"], [])), "fan_out": len(outgoing.get(c["id"], []))}
        for c in components
    ]
    return {
        "component_map": cmap,
        "statistics": {
            "total_components": len(components),
            "total_connections": len(connections),
            "orphan_components": [c["name"] for c in components
                                  if c["id"] not in outgoing and c["id"] not in incoming],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  5.  FILE SAVE HELPER
# ═══════════════════════════════════════════════════════════════════════════

def save_excalidraw_file(elements_json: str, filepath: str = "./output/architecture.excalidraw") -> str:
    """Save Excalidraw elements as a ``.excalidraw`` file for local viewing."""
    pseudo = {"cameraUpdate", "delete", "restoreCheckpoint"}
    elements = json.loads(elements_json)
    real = [e for e in elements if e.get("type") not in pseudo]
    data = {"type": "excalidraw", "version": 2, "source": "arch-review",
            "elements": real, "appState": {"viewBackgroundColor": "#ffffff"}, "files": {}}
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return os.path.abspath(filepath)


# ═══════════════════════════════════════════════════════════════════════════
#  6.  MCP DIAGRAM RENDERER (Excalidraw MCP Server Integration)
# ═══════════════════════════════════════════════════════════════════════════


# ── PNG color helpers (hex → RGB tuple) ──────────────────────────────────

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ═══════════════════════════════════════════════════════════════════════════
#  6a.  PNG EXPORT  (Pillow-based - no external renderers needed)
# ═══════════════════════════════════════════════════════════════════════════

def export_png(
    components: list[dict],
    connections: list[dict],
    filepath: str = "./output/architecture.png",
    scale: float = 2.0,
) -> str:
    """Render the architecture diagram as a PNG image using Pillow.

    Uses the same layout engine and colour palette as the Excalidraw renderer
    so the PNG matches the interactive diagram exactly.

    Args:
        components: Parsed component list.
        connections: Parsed connection list.
        filepath: Output path (directories created automatically).
        scale: Resolution multiplier (2.0 = retina-quality).

    Returns:
        Absolute path to the saved PNG file.
    """
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

    pos = _layout(components)
    if not pos:
        # Empty diagram - still produce a valid PNG
        img = Image.new("RGB", (400, 200), "#ffffff")
        draw = ImageDraw.Draw(img)
        draw.text((20, 80), "No components to render", fill="#1e1e1e")
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        img.save(filepath, "PNG")
        return os.path.abspath(filepath)

    # ── Canvas bounds ────────────────────────────────────────────────────
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    pad = 120
    min_x, min_y = min(xs) - pad, min(ys) - pad
    max_x = max(xs) + _W + pad
    max_y = max(ys) + _H + pad

    cw = int((max_x - min_x) * scale)
    ch = int((max_y - min_y) * scale)
    img = Image.new("RGB", (cw, ch), "#ffffff")
    draw = ImageDraw.Draw(img)

    def sx(v: float) -> float:
        return (v - min_x) * scale

    def sy(v: float) -> float:
        return (v - min_y) * scale

    # ── Try to load a nicer font; fall back to default ───────────────────
    try:
        font_lg = ImageFont.truetype("arial.ttf", int(18 * scale))
        font_sm = ImageFont.truetype("arial.ttf", int(12 * scale))
        font_tag = ImageFont.truetype("arial.ttf", int(11 * scale))
    except (IOError, OSError):
        try:
            font_lg = ImageFont.truetype("DejaVuSans.ttf", int(18 * scale))
            font_sm = ImageFont.truetype("DejaVuSans.ttf", int(12 * scale))
            font_tag = ImageFont.truetype("DejaVuSans.ttf", int(11 * scale))
        except (IOError, OSError):
            font_lg = ImageFont.load_default()
            font_sm = font_lg
            font_tag = font_lg

    # ── Draw connections (arrows) first so they sit behind nodes ─────────
    for conn in connections:
        sp = pos.get(conn["source"])
        tp = pos.get(conn["target"])
        if not sp or not tp:
            continue

        # Same logic as _arrow(): horizontal vs vertical
        if abs(sp[1] - tp[1]) < 50:
            x0, y0 = sp[0] + _W, sp[1] + _H // 2
            x1, y1 = tp[0], tp[1] + _H // 2
        else:
            x0, y0 = sp[0] + _W // 2, sp[1] + _H
            x1, y1 = tp[0] + _W // 2, tp[1]

        line_color = _hex_to_rgb("#495057")
        draw.line(
            [(sx(x0), sy(y0)), (sx(x1), sy(y1))],
            fill=line_color, width=max(2, int(2 * scale)),
        )

        # Arrowhead
        angle = math.atan2(y1 - y0, x1 - x0)
        arrow_len = 12 * scale
        ax1 = sx(x1) - arrow_len * math.cos(angle - 0.35)
        ay1 = sy(y1) - arrow_len * math.sin(angle - 0.35)
        ax2 = sx(x1) - arrow_len * math.cos(angle + 0.35)
        ay2 = sy(y1) - arrow_len * math.sin(angle + 0.35)
        draw.polygon(
            [(sx(x1), sy(y1)), (ax1, ay1), (ax2, ay2)],
            fill=line_color,
        )

        # Connection label
        label = conn.get("label", "")
        if label:
            lx = (sx(x0) + sx(x1)) / 2
            ly = (sy(y0) + sy(y1)) / 2 - 10 * scale
            bbox = draw.textbbox((0, 0), label, font=font_sm)
            tw = bbox[2] - bbox[0]
            # Label background for readability
            draw.rectangle(
                [lx - tw / 2 - 4 * scale, ly - 2 * scale,
                 lx + tw / 2 + 4 * scale, ly + (bbox[3] - bbox[1]) + 2 * scale],
                fill="#ffffff",
            )
            draw.text((lx - tw / 2, ly), label, fill=_hex_to_rgb("#868e96"), font=font_sm)

    # ── Draw component rectangles ────────────────────────────────────────
    corner_r = int(8 * scale)
    for comp in components:
        p = pos.get(comp["id"])
        if not p:
            continue
        ctype = comp.get("type", "service")
        col = _COLORS.get(ctype, _DEFAULT_COL)
        bg = _hex_to_rgb(col["bg"])
        border = _hex_to_rgb(col["border"])
        rx0, ry0 = sx(p[0]), sy(p[1])
        rx1, ry1 = sx(p[0] + _W), sy(p[1] + _H)

        # Rounded rectangle
        draw.rounded_rectangle(
            [rx0, ry0, rx1, ry1],
            radius=corner_r, fill=bg, outline=border,
            width=max(2, int(2 * scale)),
        )

        # Component name (centered)
        name = _truncate_component_label(comp["name"], max_chars=34)
        bbox = draw.textbbox((0, 0), name, font=font_lg)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = (rx0 + rx1) / 2
        draw.text((cx - tw / 2, ry0 + 10 * scale), name,
              fill=_hex_to_rgb("#1e1e1e"), font=font_lg)

        # Type tag
        tag = f"[{ctype.upper()}]"
        bbox_t = draw.textbbox((0, 0), tag, font=font_tag)
        ttw = bbox_t[2] - bbox_t[0]
        draw.text((cx - ttw / 2, ry0 + 10 * scale + th + 6 * scale), tag,
                  fill=_hex_to_rgb("#868e96"), font=font_tag)

    # ── Title watermark ──────────────────────────────────────────────────
    draw.text((10 * scale, 6 * scale), "Architecture Review Agent",
              fill=_hex_to_rgb("#ced4da"), font=font_lg)

    # ── Save ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    img.save(filepath, "PNG", dpi=(150 * scale, 150 * scale))
    return os.path.abspath(filepath)

EXCALIDRAW_MCP_URL = os.environ.get(
    "EXCALIDRAW_MCP_URL", "https://excalidraw-mcp-app.vercel.app/mcp"
)


def generate_mcp_diagram_elements(
    components: list[dict], connections: list[dict],
) -> dict[str, Any]:
    """Build Excalidraw elements optimised for MCP ``create_view`` streaming.

    Uses **labeled shapes** (one element per node instead of three) and
    **progressive ordering** (shape → arrows from shape → next shape)
    per the MCP server's ``read_me`` best-practices.
    """
    pos = _layout(components)
    elems: list[dict] = []

    # ── Camera (4:3 ratio required) ──────────────────────────────────────
    if pos:
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        cam_x = min(xs) - 100
        cam_y = min(ys) - 80
        cam_w = max(xs) + _W + 200 - cam_x
        cam_h = max(ys) + _H + 100 - cam_y
        if cam_w / max(cam_h, 1) > 4 / 3:
            cam_h = int(cam_w * 3 / 4)
        else:
            cam_w = int(cam_h * 4 / 3)
        elems.append({"type": "cameraUpdate", "x": cam_x, "y": cam_y,
                      "width": cam_w, "height": cam_h})

    # ── Index arrows by source for progressive emit ──────────────────────
    conn_by_src: dict[str, list[tuple[int, dict]]] = {}
    for i, conn in enumerate(connections):
        conn_by_src.setdefault(conn["source"], []).append((i, conn))

    for comp in components:
        cid = comp["id"]
        p = pos.get(cid, (0, 0))
        col = _COLORS.get(comp.get("type", "service"), _DEFAULT_COL)
        ctype = comp.get("type", "service").upper()

        # Labeled rectangle - single element with embedded text
        elems.append({
            "type": "rectangle", "id": cid,
            "x": p[0], "y": p[1], "width": _W, "height": _H,
            "strokeColor": col["border"], "backgroundColor": col["bg"],
            "fillStyle": "solid", "roundness": {"type": 3},
            "label": {"text": f"{comp['name']}\n[{ctype}]", "fontSize": 16},
        })

        # Arrows originating from this component
        for i, conn in conn_by_src.get(cid, []):
            sp = pos.get(conn["source"], (0, 0))
            tp = pos.get(conn["target"], (0, 0))
            if abs(sp[1] - tp[1]) < 50:  # horizontal
                x0 = sp[0] + _W
                y0 = sp[1] + _H // 2
                dx = tp[0] - x0
                dy = tp[1] + _H // 2 - y0
                s_fp, e_fp = [1, 0.5], [0, 0.5]
            else:                                # vertical
                x0 = sp[0] + _W // 2
                y0 = sp[1] + _H
                dx = tp[0] + _W // 2 - x0
                dy = tp[1] - y0
                s_fp, e_fp = [0.5, 1], [0.5, 0]

            arrow: dict[str, Any] = {
                "type": "arrow", "id": f"conn_{i}",
                "x": x0, "y": y0,
                "width": abs(dx), "height": abs(dy),
                "strokeColor": "#495057",
                "points": [[0, 0], [dx, dy]],
                "startArrowhead": None, "endArrowhead": "arrow",
                "startBinding": {"elementId": conn["source"], "fixedPoint": s_fp},
                "endBinding": {"elementId": conn["target"], "fixedPoint": e_fp},
            }
            if conn.get("label"):
                arrow["label"] = {"text": conn["label"]}
            elems.append(arrow)

    return {"elements_json": json.dumps(elems), "element_count": len(elems)}


# ── Async MCP client ────────────────────────────────────────────────────


async def _render_mcp_async(
    elements_json: str, mcp_url: str = EXCALIDRAW_MCP_URL,
) -> dict[str, Any]:
    """Connect to Excalidraw MCP server and invoke ``create_view``."""
    try:
        from mcp import ClientSession  # type: ignore[import-untyped]
    except ImportError:
        return {"success": False, "error": "mcp package not installed - run: pip install mcp"}

    def _extract(result: Any) -> str:
        if hasattr(result, "content"):
            parts = []
            for block in result.content:
                parts.append(getattr(block, "text", str(block)))
            return "\n".join(parts)
        return str(result)

    def _make_httpx_client(**kwargs: Any) -> Any:
        """Custom httpx client factory - disables SSL verification when the
        standard CA bundle fails (common behind corporate proxies)."""
        import httpx  # type: ignore[import-untyped]
        # Respect explicit env override first
        if os.environ.get("ARCH_REVIEW_NO_SSL_VERIFY", "").lower() in ("1", "true"):
            kwargs["verify"] = False
            logger.debug("[MCP] SSL verify disabled via ARCH_REVIEW_NO_SSL_VERIFY")
        elif kwargs.get("verify", True) is not False:
            # Probe the actual target - ssl.create_default_context() alone
            # doesn't catch proxy-injected CAs that httpx will reject.
            try:
                with httpx.Client(verify=True) as probe:
                    probe.head(mcp_url, timeout=5)
                logger.debug("[MCP] SSL probe OK - using default verification")
            except Exception as exc:
                kwargs["verify"] = False
                logger.warning("[MCP] SSL probe failed (%s) - disabling verification. "
                               "Set ARCH_REVIEW_NO_SSL_VERIFY=1 to suppress this warning.", exc)
        return httpx.AsyncClient(**kwargs)

    errors: list[str] = []

    # 1️⃣  Streamable HTTP (preferred)
    try:
        from mcp.client.streamable_http import streamablehttp_client
        async with streamablehttp_client(
            mcp_url, httpx_client_factory=_make_httpx_client,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool("create_view", {"elements": elements_json})
                return {"success": True, "transport": "streamable-http",
                        "result": _extract(res)}
    except Exception as exc:
        errors.append(f"streamable-http: {exc}")

    # 2️⃣  SSE fallback (also with SSL handling)
    try:
        from mcp.client.sse import sse_client
        async with sse_client(mcp_url, httpx_client_factory=_make_httpx_client) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.call_tool("create_view", {"elements": elements_json})
                return {"success": True, "transport": "sse",
                        "result": _extract(res)}
    except Exception as exc:
        errors.append(f"sse: {exc}")

    return {"success": False, "error": " | ".join(errors)}


def render_via_excalidraw_mcp(
    elements_json: str, mcp_url: str = EXCALIDRAW_MCP_URL,
) -> dict[str, Any]:
    """Render architecture diagram via Excalidraw MCP server (**sync wrapper**).

    Handles both sync and async caller contexts gracefully.
    """
    import concurrent.futures

    coro = _render_mcp_async(elements_json, mcp_url)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Called from inside an event-loop (e.g. hosted agent runtime)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=30)
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════════════════
#  7.  STRUCTURED REPORT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def build_review_report(
    parsed: dict[str, Any],
    risks: dict[str, Any],
    comp_map: dict[str, Any],
    diagram_info: dict[str, Any],
) -> dict[str, Any]:
    """Compose a structured architecture review report ready for the agent."""
    n_comp = len(parsed["components"])
    n_conn = len(parsed["connections"])
    rs = risks["summary"]

    if rs["critical"] > 0:
        severity_label = "critical"
    elif rs["high"] > 0:
        severity_label = "needs attention"
    elif rs["medium"] > 0:
        severity_label = "moderate"
    else:
        severity_label = "healthy"

    # Prioritised recommendations
    recs: list[dict[str, str]] = []
    for sev in ("critical", "high", "medium", "low"):
        for r in risks.get(sev, []):
            recs.append({"priority": sev, "component": r["component"],
                         "action": r["recommendation"]})

    orphans = comp_map.get("statistics", {}).get("orphan_components", [])

    return {
        "executive_summary": {
            "components": n_comp,
            "connections": n_conn,
            "risk_level": severity_label,
            "total_risks": rs["total"],
            "format_detected": parsed.get("detected_format", "unknown"),
        },
        "risk_assessment": risks,
        "component_map": comp_map,
        "diagram": diagram_info,
        "recommendations": recs,
        "warnings": (
            [f"Orphan components (no connections): {', '.join(orphans)}"]
            if orphans else []
        ),
    }
