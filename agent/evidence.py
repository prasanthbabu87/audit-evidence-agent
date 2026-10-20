"""Evidence store and deterministic control tests.

Design principle: the LLM *never* computes a test result. Every pass/fail is
produced here by plain, reviewable Python so results are reproducible and
re-performable by a reviewer. The agent plans the work, calls these tests,
investigates exceptions and writes the workpaper.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

TS_FMT = "%Y-%m-%d %H:%M"


def _ts(value: str) -> datetime | None:
    return datetime.strptime(value, TS_FMT) if value else None


def business_days_between(start: datetime, end: datetime) -> int:
    """Whole business days (Mon-Fri) elapsed from start to end."""
    if end <= start:
        return 0
    days, cursor = 0, start
    while cursor.date() < end.date():
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


@dataclass
class EvidenceStore:
    data_dir: Path
    controls: dict = field(init=False)
    tickets: dict[str, dict] = field(init=False)
    deployments: list[dict] = field(init=False)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self.controls = json.loads((self.data_dir / "controls.json").read_text())
        with open(self.data_dir / "change_tickets.csv", newline="") as f:
            self.tickets = {r["ticket_id"]: r for r in csv.DictReader(f)}
        with open(self.data_dir / "deployment_log.csv", newline="") as f:
            self.deployments = list(csv.DictReader(f))

    # ----- scoping -------------------------------------------------------
    def control_ids(self) -> list[str]:
        return [c["id"] for c in self.controls["controls"]]

    def population_summary(self) -> dict:
        by_type: dict[str, int] = {}
        by_system: dict[str, int] = {}
        for t in self.tickets.values():
            by_type[t["change_type"]] = by_type.get(t["change_type"], 0) + 1
            by_system[t["system"]] = by_system.get(t["system"], 0) + 1
        return {
            "change_tickets": len(self.tickets),
            "production_deployments": len(self.deployments),
            "by_change_type": by_type,
            "by_system": by_system,
            "period": self.controls["period"],
        }

    # ----- attribute tests (full population) -----------------------------
    def test_control(self, control_id: str) -> dict:
        tests = {
            "CM-01": self._test_authorization,
            "CM-02": self._test_sod,
            "CM-03": self._test_testing,
            "CM-04": self._test_emergency_pir,
            "CM-05": self._test_completeness,
        }
        if control_id not in tests:
            raise ValueError(f"Unknown control {control_id!r}; valid: {list(tests)}")
        exceptions = tests[control_id]()
        population = len(self.deployments) if control_id == "CM-05" else (
            sum(t["change_type"] == "emergency" for t in self.tickets.values())
            if control_id == "CM-04" else len(self.tickets))
        return {
            "control_id": control_id,
            "population_tested": population,
            "exceptions_found": len(exceptions),
            "exceptions": exceptions,
            "result": "No exceptions" if not exceptions else "Exceptions noted",
        }

    def _test_authorization(self) -> list[dict]:
        out = []
        for t in self.tickets.values():
            approved, deployed = _ts(t["approved_at"]), _ts(t["deployed_at"])
            if not t["approver"] or not approved:
                out.append({"ticket_id": t["ticket_id"], "attribute": "approver recorded",
                            "detail": "No approver / approval timestamp on ticket"})
            elif t["change_type"] == "standard" and approved > deployed:
                hrs = round((approved - deployed).total_seconds() / 3600, 1)
                out.append({"ticket_id": t["ticket_id"], "attribute": "approved before deployment",
                            "detail": f"Approved {hrs}h AFTER deployment ({t['approved_at']} vs {t['deployed_at']})"})
            elif t["change_type"] == "emergency" and business_days_between(deployed, approved) > 2:
                out.append({"ticket_id": t["ticket_id"], "attribute": "emergency retrospective approval",
                            "detail": "Retrospective approval later than 2 business days"})
        return out

    def _test_sod(self) -> list[dict]:
        out = []
        for t in self.tickets.values():
            if t["approver"] and t["developer"] == t["approver"]:
                out.append({"ticket_id": t["ticket_id"], "attribute": "developer != approver",
                            "detail": f"{t['developer']} approved own change"})
            if t["developer"] == t["deployed_by"]:
                out.append({"ticket_id": t["ticket_id"], "attribute": "developer != deployer",
                            "detail": f"{t['developer']} deployed own change to production"})
        return out

    def _test_testing(self) -> list[dict]:
        return [{"ticket_id": t["ticket_id"], "attribute": "test / UAT evidence attached",
                 "detail": "No test or UAT evidence attached"}
                for t in self.tickets.values() if not t["test_evidence"].strip()]

    def _test_emergency_pir(self) -> list[dict]:
        out = []
        for t in self.tickets.values():
            if t["change_type"] != "emergency":
                continue
            pir, deployed = _ts(t["post_impl_review_at"]), _ts(t["deployed_at"])
            if not pir:
                out.append({"ticket_id": t["ticket_id"], "attribute": "PIR recorded",
                            "detail": "Emergency change has no post-implementation review"})
            elif (bd := business_days_between(deployed, pir)) > 2:
                out.append({"ticket_id": t["ticket_id"], "attribute": "PIR within 2 business days",
                            "detail": f"PIR completed {bd} business days after deployment"})
        return out

    def _test_completeness(self) -> list[dict]:
        out = []
        for d in self.deployments:
            if not d["ticket_id"]:
                out.append({"deploy_id": d["deploy_id"], "attribute": "deployment has ticket reference",
                            "detail": f"Deployment to {d['system']} by {d['deployed_by']} at {d['deployed_at']} has no change ticket"})
            elif d["ticket_id"] not in self.tickets:
                out.append({"deploy_id": d["deploy_id"], "attribute": "ticket exists",
                            "detail": f"References {d['ticket_id']}, which does not exist in the change system"})
        return out

    # ----- drill-down ----------------------------------------------------
    def get_ticket(self, ticket_id: str) -> dict:
        if ticket_id not in self.tickets:
            return {"error": f"{ticket_id} not found in change system"}
        return self.tickets[ticket_id]

    def get_deployment(self, deploy_id: str) -> dict:
        for d in self.deployments:
            if d["deploy_id"] == deploy_id:
                return d
        return {"error": f"{deploy_id} not found in deployment log"}
