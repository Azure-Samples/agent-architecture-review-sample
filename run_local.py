"""
Architecture Review Agent — Local Test Runner (no Azure required for structured inputs)
========================================================================================
Usage:
    python run_local.py examples/ecommerce.yaml
    python run_local.py examples/event_driven.md
    python run_local.py --text "API Gateway -> Auth Service -> User DB"
    python run_local.py examples/ecommerce.yaml --render   # render via Excalidraw MCP
    python run_local.py any_readme.md --infer               # force LLM inference
    python run_local.py design_doc.txt                      # auto-fallback to LLM if needed
"""

import argparse
import asyncio
import io
import json
import logging
import os
import sys

# Ensure UTF-8 output on Windows (prevents UnicodeEncodeError with Rich/Unicode chars)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(override=True)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Suppress tools.py logger — run_local.py prints decisions inline via Rich
logging.getLogger("arch-review").setLevel(logging.CRITICAL)

from tools import (
    parse_architecture,
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

console = Console()


async def run_review(content: str, render_mcp: bool = False, force_infer: bool = False) -> None:
    console.rule("[bold blue]Architecture Review[/bold blue]")

    # 1. Parse / Infer
    console.print()
    if force_infer:
        console.print("[dim]Step 1:[/dim] Forcing LLM inference (--infer flag)")
        parsed = await infer_architecture_llm(content)
        if parsed.get("error"):
            console.print(f"  [red]\u2717 LLM inference error:[/red] {parsed['error']}")
            console.print("  [yellow]\u21b3 Falling back to rule-based parser...[/yellow]")
            parsed = parse_architecture(content)
            console.print(f"  [green]\u2713 Fallback:[/green] Rule-based ({parsed['detected_format']})")
        else:
            console.print(f"  [green]\u2713 Engine:[/green]  LLM inference")
    else:
        parsed = await smart_parse(content)
        fmt = parsed.get('detected_format', 'unknown')
        sufficient = parsed.get('parsing_sufficient', True)
        if parsed.get("llm_inferred"):
            console.print(f"[dim]Step 1:[/dim] Tried rule-based parser \u2192 insufficient \u2192 used LLM inference")
            console.print(f"  [green]\u2713 Engine:[/green]  LLM-inferred")
            console.print(f"  [dim]  Reason:[/dim]  Rule-based parser found \u22641 component; LLM analysed content")
        elif not sufficient:
            console.print(f"[dim]Step 1:[/dim] Rule-based parser found insufficient data \u2192 LLM unavailable \u2192 using rule-based result")
            console.print(f"  [yellow]\u26a0 Engine:[/yellow]  Rule-based (fallback \u2014 LLM not configured)")
            console.print(f"  [yellow]\u26a0 Format:[/yellow]  {fmt}")
            console.print(f"  [dim]  Hint:[/dim]    Set AZURE_OPENAI_ENDPOINT in .env for LLM inference on unstructured input")
        else:
            console.print(f"[dim]Step 1:[/dim] Rule-based parser succeeded")
            console.print(f"  [green]\u2713 Engine:[/green]  Rule-based")
            console.print(f"  [green]\u2713 Format:[/green]  {fmt}")

    if parsed.get("error"):
        console.print(f"  [red]\u2717 Error:[/red]   {parsed['error']}")

    n_comp = len(parsed['components'])
    n_conn = len(parsed['connections'])
    console.print(f"  [cyan]\u2713 Result:[/cyan]  {n_comp} components, {n_conn} connections")

    if parsed.get("metadata", {}).get("architecture_name"):
        console.print(f"  [cyan]\u2713 Name:[/cyan]    {parsed['metadata']['architecture_name']}")

    if not parsed["components"]:
        console.print("[red]No components found — cannot proceed with review.[/red]")
        return

    # 2. Risks — use LLM-generated risks when available, else template-based
    console.print(f"\n[dim]Step 2:[/dim] Risk analysis")
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
        console.print(f"  [green]\u2713 Source:[/green] LLM-generated")
    else:
        risks = analyze_risks(parsed["components"], parsed["connections"])
    s = risks["summary"]
    console.print(
        f"  [cyan]\u2713 Found:[/cyan]  {s['total']} risks "
        f"(critical={s['critical']}, high={s['high']}, medium={s['medium']}, low={s['low']})"
    )
    table = Table(title="Risk Assessment", show_lines=True)
    table.add_column("Severity", width=10)
    table.add_column("Component", width=20)
    table.add_column("Issue", width=40)
    table.add_column("Recommendation", width=40)
    styles = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "green"}
    for sev in ("critical", "high", "medium", "low"):
        for r in risks.get(sev, []):
            table.add_row(f"[{styles[sev]}]{sev.upper()}[/{styles[sev]}]",
                          r["component"], r["issue"], r["recommendation"])
    console.print(table)

    # 3. Diagram (local file)
    console.print(f"\n[dim]Step 3:[/dim] Diagram generation")
    diagram = generate_excalidraw_elements(parsed["components"], parsed["connections"])
    saved = save_excalidraw_file(diagram["elements_json"])
    console.print(f"  [green]\u2713 Excalidraw:[/green] {saved}  ({diagram['element_count']} elements)")
    diagram_info: dict = {"element_count": diagram["element_count"], "local_file": saved}

    # 3a. PNG export
    png_path = export_png(parsed["components"], parsed["connections"])
    console.print(f"  [green]\u2713 PNG:[/green]       {png_path}")
    diagram_info["png_file"] = png_path

    # 3b. Excalidraw file in response (read from saved file to avoid duplication)
    with open(saved, "r", encoding="utf-8") as f:
        diagram_info["excalidraw_file"] = json.load(f)
    diagram_info["excalidraw_usage"] = "Copy the entire excalidraw_file object, save as a .excalidraw file, and open at https://excalidraw.com to view/edit the interactive diagram."

    # 3c. Render via Excalidraw MCP (optional)
    if render_mcp:
        console.print("  [dim]\u21b3 Rendering via Excalidraw MCP server...[/dim]")
        mcp_elems = generate_mcp_diagram_elements(parsed["components"], parsed["connections"])
        mcp_result = render_via_excalidraw_mcp(mcp_elems["elements_json"])
        diagram_info["mcp_render"] = mcp_result
        if mcp_result.get("success"):
            console.print(
                f"  [green]\u2713 MCP:[/green]       Success via {mcp_result.get('transport', 'unknown')}"
            )
        else:
            console.print(f"  [red]\u2717 MCP:[/red]       {mcp_result.get('error', 'unknown')}")

    # 4. Component map
    console.print(f"\n[dim]Step 4:[/dim] Component mapping")
    cmap = build_component_map(parsed["components"], parsed["connections"])
    mt = Table(title="Component Map", show_lines=True)
    mt.add_column("Component", width=20)
    mt.add_column("Type", width=12)
    mt.add_column("Fan-In", width=8, justify="center")
    mt.add_column("Fan-Out", width=8, justify="center")
    for c in cmap["component_map"]:
        mt.add_row(c["name"], c["type"], str(c["fan_in"]), str(c["fan_out"]))
    console.print(mt)

    # 5. Structured report
    report = build_review_report(parsed, risks, cmap, diagram_info)
    summary = report["executive_summary"]
    console.print(Panel(
        f"[bold]Risk Level:[/bold] {summary['risk_level'].upper()}\n"
        f"[bold]Components:[/bold] {summary['components']}  |  "
        f"[bold]Connections:[/bold] {summary['connections']}  |  "
        f"[bold]Risks:[/bold] {summary['total_risks']}\n"
        f"[bold]Format:[/bold] {summary['format_detected']}",
        title="Executive Summary", border_style="blue",
    ))
    if report.get("recommendations"):
        rt = Table(title="Prioritised Recommendations", show_lines=True)
        rt.add_column("Priority", width=10)
        rt.add_column("Component", width=20)
        rt.add_column("Action", width=50)
        for rec in report["recommendations"]:
            style = styles.get(rec["priority"], "white")
            rt.add_row(f"[{style}]{rec['priority'].upper()}[/{style}]",
                       rec["component"], rec["action"])
        console.print(rt)

    # Save bundle
    out = "./output/review_bundle.json"
    os.makedirs("./output", exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    console.print(f"\n[green]Review report saved:[/green] {os.path.abspath(out)}")
    console.rule("[bold blue]Done[/bold blue]")


def main() -> None:
    parser = argparse.ArgumentParser(description="Architecture Review Agent — Local Runner")
    parser.add_argument("file", nargs="?", help="Architecture file (YAML/MD/TXT/README/any)")
    parser.add_argument("--text", "-t", help="Inline architecture description")
    parser.add_argument("--render", "-r", action="store_true",
                        help="Render diagram via Excalidraw MCP server")
    parser.add_argument("--infer", "-i", action="store_true",
                        help="Force LLM inference (skip rule-based parser, requires Azure OpenAI)")
    args = parser.parse_args()

    # Resolve input: --text wins, then positional file, then stdin
    input_text = args.text
    if not input_text and args.file:
        if os.path.isfile(args.file):
            with open(args.file, "r", encoding="utf-8") as f:
                input_text = f.read()
        else:
            # Treat non-existent "file" arg as inline text (e.g. --infer "prose ...")
            input_text = args.file

    if input_text:
        asyncio.run(run_review(input_text, render_mcp=args.render, force_infer=args.infer))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
