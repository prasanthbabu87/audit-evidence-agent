"""Offline demo mode: a scripted planner that drives the SAME tools the LLM uses.

Lets anyone clone the repo and see the full workflow without an API key, and
doubles as a regression baseline for the deterministic tests.
"""
from __future__ import annotations

import json

from .llm_agent import AuditTrail
from .tools import Toolbox

TEMPLATES = {
    "CM-01": dict(title="Changes deployed without timely authorization", severity="High",
                  criteria="Standard changes must be approved before deployment; emergency changes approved within 2 business days.",
                  effect="Unauthorized changes to financially significant systems could affect the integrity of financial data.",
                  recommendation="Enforce a workflow gate that blocks deployment until the ticket is in 'Approved' status; review exceptions with change owners."),
    "CM-02": dict(title="Segregation of duties conflicts in change process", severity="High",
                  criteria="Developers must not approve or deploy their own changes.",
                  effect="A single individual could introduce and promote unreviewed code to production.",
                  recommendation="Restrict production deployment rights to the release team and block self-approval in the ticketing tool."),
    "CM-03": dict(title="Test / UAT evidence not retained", severity="Medium",
                  criteria="Test and user acceptance evidence must be attached before deployment.",
                  effect="Untested changes may cause processing errors or outages.",
                  recommendation="Make the UAT sign-off attachment a mandatory field before approval."),
    "CM-04": dict(title="Emergency changes lacking timely post-implementation review", severity="Medium",
                  criteria="Emergency changes require a PIR within 2 business days.",
                  effect="Emergency changes bypass normal controls; without PIR, inappropriate changes may go undetected.",
                  recommendation="Auto-create a PIR task with a 2-business-day SLA for every emergency change and report breaches to the CAB."),
    "CM-05": dict(title="Production deployments not traceable to approved change tickets", severity="High",
                  criteria="Every production deployment must reference a valid approved change ticket.",
                  effect="Unauthorized changes reached production outside the change process.",
                  recommendation="Integrate the CI/CD pipeline with the change system to reject deployments without a valid ticket; investigate the listed deployments."),
}


def run_offline(toolbox: Toolbox, trail: AuditTrail, verbose: bool = True) -> Toolbox:
    def call(name, **args):
        out, err = toolbox.run(name, args)
        trail.log("tool_call", tool=name, input=args, is_error=err, output_preview=out[:300])
        if verbose:
            print(f"  -> {name}({json.dumps(args)[:80]}) [{'ERROR' if err else 'ok'}]")
        return json.loads(out)

    trail.log("run_started", model="offline-scripted")
    scope = call("get_audit_scope")
    for control in scope["controls"]:
        result = call("test_control", control_id=control["id"])
        if not result["exceptions"]:
            continue
        refs = [e.get("ticket_id") or e.get("deploy_id") for e in result["exceptions"]]
        condition = f"{len(refs)} of {result['population_tested']} items failed: " + "; ".join(
            f"{e.get('ticket_id') or e.get('deploy_id')} ({e['detail']})" for e in result["exceptions"])
        call("record_finding", control_id=control["id"], condition=condition,
             references=sorted(set(refs)), **TEMPLATES[control["id"]])

    n = len(toolbox.workpaper.findings)
    call("finalize_workpaper", conclusion=(
        f"Change management controls are NOT operating effectively for the period: {n} findings were "
        "identified, including unauthorized production deployments and segregation of duties conflicts. "
        "Management should remediate and the audit team should perform follow-up testing next quarter."
        if n else "Change management controls are operating effectively for the period."))
    trail.log("run_ended", stop_reason="workpaper_finalized")
    return toolbox
