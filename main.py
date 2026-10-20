"""CLI entry point.

    python main.py              # uses Claude if ANTHROPIC_API_KEY is set, else offline demo
    python main.py --offline    # scripted demo, no API key needed
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from agent.evidence import EvidenceStore
from agent.llm_agent import DEFAULT_MODEL, AuditTrail, run_agent
from agent.offline import run_offline
from agent.tools import Toolbox

ROOT = Path(__file__).parent


def main() -> None:
    p = argparse.ArgumentParser(description="AI agent for ITGC change-management testing")
    p.add_argument("--data", default=ROOT / "data", type=Path)
    p.add_argument("--out", default=ROOT / "output", type=Path)
    p.add_argument("--offline", action="store_true", help="run scripted demo without an API key")
    p.add_argument("--model", default=DEFAULT_MODEL)
    args = p.parse_args()

    toolbox = Toolbox(EvidenceStore(args.data))
    trail = AuditTrail(args.out / "agent_audit_trail.jsonl")

    if args.offline or not os.environ.get("ANTHROPIC_API_KEY"):
        print("Running in OFFLINE demo mode (scripted planner, same tools).")
        run_offline(toolbox, trail)
    else:
        print(f"Running with Claude ({args.model}).")
        run_agent(toolbox, trail, model=args.model)

    wp = toolbox.workpaper
    out_file = args.out / "workpaper.md"
    out_file.write_text(wp.to_markdown())
    print(f"\nFindings: {len(wp.findings)} | finalized: {wp.finalized}")
    print(f"Workpaper:   {out_file}")
    print(f"Audit trail: {trail.path}")


if __name__ == "__main__":
    main()
