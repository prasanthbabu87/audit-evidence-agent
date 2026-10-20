"""Claude tool-use loop with a full audit trail of every agent action."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .tools import TOOL_SPECS, Toolbox

DEFAULT_MODEL = os.environ.get("AUDIT_AGENT_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """You are an IT auditor performing ITGC testing of change management, \
following ISACA ITAF practice. Work methodically:
1. Call get_audit_scope to understand the controls and population.
2. Call test_control for EVERY control in scope.
3. Investigate exceptions with get_ticket / get_deployment where the root cause or \
risk is unclear (e.g. who was involved, which system, timing).
4. Record findings with record_finding: one finding per control/issue type, grouping \
related exceptions. Use condition / criteria / effect / recommendation. Rate severity:
   High   = unauthorized or unreviewed change could reach production undetected
   Medium = control operated but with a significant gap (late approval, missing PIR)
   Low    = documentation gap with low likelihood of impact
5. When every exception is covered, call finalize_workpaper with a concise conclusion \
on whether the controls are operating effectively.
Only state facts returned by tools. Never invent tickets, people or numbers."""


class AuditTrail:
    """Append-only JSONL log of every agent step — the agent's own audit trail."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")

    def log(self, event: str, **data) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **data}
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def run_agent(toolbox: Toolbox, trail: AuditTrail, client=None, model: str = DEFAULT_MODEL,
              max_turns: int = 40, verbose: bool = True) -> Toolbox:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    messages = [{"role": "user", "content": "Perform the change management controls test for this period and produce the workpaper."}]
    trail.log("run_started", model=model)

    for turn in range(1, max_turns + 1):
        response = client.messages.create(
            model=model, max_tokens=4096, system=SYSTEM_PROMPT, tools=TOOL_SPECS, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text" and block.text.strip():
                trail.log("reasoning", turn=turn, text=block.text)
                if verbose:
                    print(f"\n[agent] {block.text.strip()}")

        if response.stop_reason != "tool_use":
            trail.log("run_ended", turn=turn, stop_reason=response.stop_reason)
            break

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output, is_error = toolbox.run(block.name, dict(block.input))
            trail.log("tool_call", turn=turn, tool=block.name, input=block.input, is_error=is_error,
                      output_preview=output[:300])
            if verbose:
                flag = "ERROR" if is_error else "ok"
                print(f"  -> {block.name}({json.dumps(block.input)[:80]}) [{flag}]")
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
        messages.append({"role": "user", "content": results})

        if toolbox.workpaper.finalized:
            trail.log("run_ended", turn=turn, stop_reason="workpaper_finalized")
            break
    else:
        trail.log("run_ended", stop_reason="max_turns_reached")

    return toolbox
