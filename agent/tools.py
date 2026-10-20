"""Tool definitions exposed to the model, and the dispatcher that runs them."""
from __future__ import annotations

import json
from typing import Any

from .evidence import EvidenceStore
from .workpaper import SEVERITIES, Workpaper

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "get_audit_scope",
        "description": "Return the audit area, period, in-scope systems, control descriptions and a summary of the change population. Call this first.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "test_control",
        "description": "Run the deterministic attribute tests for one control across the FULL population and return every exception. Results are computed by code, not estimated.",
        "input_schema": {
            "type": "object",
            "properties": {"control_id": {"type": "string", "description": "e.g. CM-01"}},
            "required": ["control_id"],
        },
    },
    {
        "name": "get_ticket",
        "description": "Retrieve the full change ticket record to investigate an exception.",
        "input_schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    {
        "name": "get_deployment",
        "description": "Retrieve a production deployment log entry by deploy_id.",
        "input_schema": {
            "type": "object",
            "properties": {"deploy_id": {"type": "string"}},
            "required": ["deploy_id"],
        },
    },
    {
        "name": "record_finding",
        "description": "Record an audit finding in condition / criteria / effect / recommendation format. Group related exceptions for the same control into one finding. references must be ticket or deploy IDs returned by test_control.",
        "input_schema": {
            "type": "object",
            "properties": {
                "control_id": {"type": "string"},
                "title": {"type": "string", "description": "Short finding title"},
                "condition": {"type": "string", "description": "What was found (facts, counts)"},
                "criteria": {"type": "string", "description": "What should have happened (the control requirement)"},
                "effect": {"type": "string", "description": "Risk / potential impact"},
                "recommendation": {"type": "string"},
                "severity": {"type": "string", "enum": list(SEVERITIES)},
                "references": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["control_id", "title", "condition", "criteria", "effect", "recommendation", "severity", "references"],
        },
    },
    {
        "name": "finalize_workpaper",
        "description": "Write the overall conclusion and close the workpaper. Only call once every control is tested and every exception is covered by a finding.",
        "input_schema": {
            "type": "object",
            "properties": {"conclusion": {"type": "string", "description": "Overall opinion on design and operating effectiveness of change management controls"}},
            "required": ["conclusion"],
        },
    },
]


class Toolbox:
    """Binds tool names to the evidence store and workpaper."""

    def __init__(self, store: EvidenceStore):
        self.store = store
        self.workpaper = Workpaper(audit_area=store.controls["audit_area"], period=store.controls["period"])

    def run(self, name: str, args: dict) -> tuple[str, bool]:
        """Execute a tool. Returns (json_result, is_error)."""
        handler = getattr(self, f"_{name}", None)
        if handler is None:
            return json.dumps({"error": f"Unknown tool {name}"}), True
        try:
            return json.dumps(handler(**args), indent=1), False
        except (ValueError, TypeError) as exc:
            return json.dumps({"error": str(exc)}), True

    def _get_audit_scope(self) -> dict:
        c = self.store.controls
        return {
            "audit_area": c["audit_area"],
            "period": c["period"],
            "in_scope_systems": c["in_scope_systems"],
            "controls": c["controls"],
            "population": self.store.population_summary(),
        }

    def _test_control(self, control_id: str) -> dict:
        result = self.store.test_control(control_id)
        self.workpaper.test_results[control_id] = result
        return result

    def _get_ticket(self, ticket_id: str) -> dict:
        return self.store.get_ticket(ticket_id)

    def _get_deployment(self, deploy_id: str) -> dict:
        return self.store.get_deployment(deploy_id)

    def _record_finding(self, **kwargs) -> dict:
        return {"status": self.workpaper.add_finding(**kwargs),
                "exceptions_not_yet_covered": self.workpaper.uncovered_exceptions()}

    def _finalize_workpaper(self, conclusion: str) -> dict:
        untested = sorted(set(self.store.control_ids()) - set(self.workpaper.test_results))
        if untested:
            raise ValueError(f"Cannot finalize: controls not tested: {untested}")
        uncovered = self.workpaper.uncovered_exceptions()
        if uncovered:
            raise ValueError(f"Cannot finalize: exceptions not covered by a finding: {uncovered}")
        self.workpaper.conclusion = conclusion
        self.workpaper.finalized = True
        return {"status": "Workpaper finalized", "findings": len(self.workpaper.findings)}
