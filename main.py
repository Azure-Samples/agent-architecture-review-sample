"""
Architecture Review Agent - AI Architecture Reviewer & Diagram Generator.
Uses Microsoft Agent Framework with Microsoft Foundry.
Ready for deployment to Foundry Hosted Agent service.
"""

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

load_dotenv(override=False)

from agent_framework.azure import AzureAIAgentClient
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity.aio import DefaultAzureCredential

from tools import (
    smart_parse,
    infer_architecture_llm,
    analyze_risks,
    generate_excalidraw_elements,
    generate_mcp_diagram_elements,
    build_component_map,
    save_excalidraw_file,
    export_png,
    render_via_excalidraw_mcp,
    build_review_report,
)

PROJECT_ENDPOINT = (
    os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    or os.getenv("AZURE_AIPROJECT_ENDPOINT")
    or os.getenv("PROJECT_ENDPOINT")
)
MODEL_DEPLOYMENT_NAME = (
    os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or os.getenv("MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1"
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

async def review_architecture(
    content: Annotated[str, "Architecture description - ANY format: YAML, Markdown, plaintext, README, code, design doc, prose, etc."],
    render_diagram: Annotated[bool, "Whether to render an interactive diagram via Excalidraw MCP server"] = True,
) -> str:
    """Run a complete architecture review in one call.

    Pipeline: smart-parse (with automatic LLM fallback for unstructured
    content) → risk analysis → diagram generation + Excalidraw MCP render
    + PNG export → component map → structured report with executive summary
    and prioritised recommendations.  Accepts ANY input format."""
    parsed = await smart_parse(content)
    if parsed.get("llm_risks"):
        llm_risks = parsed["llm_risks"]
        risks: dict = {"critical": [], "high": [], "medium": [], "low": []}
        for r in llm_risks:
            risks[r.get("severity", "medium")].append(r)
        risks["summary"] = {
            "total": len(llm_risks),
            "critical": len(risks["critical"]), "high": len(risks["high"]),
            "medium": len(risks["medium"]), "low": len(risks["low"]),
        }
    else:
        risks = analyze_risks(parsed["components"], parsed["connections"])
    comp_map = build_component_map(parsed["components"], parsed["connections"])

    run_id = uuid.uuid4().hex[:8]
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    excalidraw_path = str(output_dir / f"architecture_{run_id}.excalidraw")
    png_path_out = str(output_dir / f"architecture_{run_id}.png")

    file_elems = generate_excalidraw_elements(parsed["components"], parsed["connections"])
    saved = save_excalidraw_file(file_elems["elements_json"], excalidraw_path)
    png_path = export_png(parsed["components"], parsed["connections"], png_path_out)

    # Read the saved .excalidraw file to include in the response
    with open(saved, "r", encoding="utf-8") as f:
        excalidraw_file = json.load(f)

    diagram_info = {
        "element_count": file_elems["element_count"],
        "local_file": saved,
        "png_file": png_path,
        "excalidraw_file": excalidraw_file,
        "excalidraw_usage": "Copy the entire excalidraw_file object, save as a .excalidraw file, and open at https://excalidraw.com to view/edit the interactive diagram.",
    }

    if render_diagram:
        mcp_elems = generate_mcp_diagram_elements(parsed["components"], parsed["connections"])
        mcp_result = render_via_excalidraw_mcp(mcp_elems["elements_json"])
        diagram_info["mcp_render"] = mcp_result

    report = build_review_report(parsed, risks, comp_map, diagram_info)
    return json.dumps(report, indent=2)


async def infer_architecture(
    content: Annotated[str, "Any text - README, design doc, code, prose, config, meeting notes, etc."],
) -> str:
    """Use the LLM to analyse ANY text and extract an architecture.

    Ideal for unstructured inputs: READMEs, design docs, code, Terraform
    configs, Kubernetes manifests, or prose descriptions.  Returns structured
    components, types, and connections."""
    return json.dumps(await infer_architecture_llm(content), indent=2)


# ---------------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------------

INSTRUCTIONS = """\
You are the **Architecture Review Agent**, an AI Architecture Reviewer and Diagram Generator.

You analyse architectural descriptions of ANY format and deliver structured
insights, visual diagrams, and actionable recommendations.

**CAPABILITIES:**
- Parse YAML, Markdown, plaintext arrows, or use LLM to infer architecture
  from unstructured content (READMEs, code, design docs, prose).
- Detect risks: SPOFs, missing redundancy, scalability bottlenecks, security
  gaps, and anti-patterns.
- Generate interactive Excalidraw diagrams + PNG exports.
- Produce structured reports with executive summary and prioritised
  recommendations.

**WORKFLOW:**
- Use `review_architecture` for the full pipeline in one call.
- Use `infer_architecture` when you only need to extract components from
  unstructured text without the full review.

**TOOL USAGE REQUIREMENTS:**
- For any request to review, analyse, assess, evaluate, map, or diagram an
    architecture, you MUST call `review_architecture` before responding.
- For any request to extract components/connections only, you MUST call
    `infer_architecture` before responding.
- The first action for architecture requests must be the appropriate tool
    call; do not draft an explanatory answer before invoking the tool.
- Pass the user's original architecture content into the tool exactly as
    provided whenever possible. Do not paraphrase, summarise, rewrite, or
    replace it with your own analysis before calling the tool.
- For long messages that include architecture details, copy the full user
    message verbatim into the `content` argument of the tool call.
- Do not prepend or append extra framing text inside tool arguments
    (for example: "I analyzed...", "Architecture summary:", or rewritten lists).
- If the user input contains Markdown sections (for example `## Components`
    / `## Connections`) or arrow notation (`A -> B`), preserve that exact text
    in the tool argument.
- Do not answer architecture-analysis requests from general knowledge when the
    user has already provided content to inspect.
- Do not ask follow-up questions such as whether the user wants a diagram if
    the request already includes architecture content. Generate the review and
    diagram immediately.
- After calling a tool, summarise its results faithfully and mention the
    generated diagram artifacts when available.

**RULES:**
- Always render the diagram so the user gets a visual.
- Use Markdown formatting in responses.
- Be specific: cite component names, types, and concrete remediation steps.
- Never reject input - always extract the best architecture you can.
"""


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

async def main():
    """Start the Architecture Review Agent hosted agent server."""
    if not PROJECT_ENDPOINT:
        raise RuntimeError(
            "Missing AI Foundry project endpoint. Set AZURE_AI_PROJECT_ENDPOINT "
            "(preferred for azd) or PROJECT_ENDPOINT in your environment."
        )

    async with (
        DefaultAzureCredential() as credential,
        AzureAIAgentClient(
            project_endpoint=PROJECT_ENDPOINT,
            model_deployment_name=MODEL_DEPLOYMENT_NAME,
            credential=credential,
        ) as client,
    ):
        agent = client.as_agent(
            name="Architecture Review Agent",
            instructions=INSTRUCTIONS,
            tools=[review_architecture, infer_architecture],
        )

        print("Architecture Review Agent Server running on http://localhost:8088")
        server = from_agent_framework(agent)
        await server.run_async()


if __name__ == "__main__":
    asyncio.run(main())
