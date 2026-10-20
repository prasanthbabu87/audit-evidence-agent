"""Workpaper state: test results, findings and the final rendered report."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

SEVERITIES = ("High", "Medium", "Low")


@dataclass
class Finding:
    control_id: str
    title: str
    condition: str
    criteria: str
    effect: str
    recommendation: str
    severity: str
    references: list[str]


@dataclass
class Workpaper:
    audit_area: str
    period: str
    test_results: dict[str, dict] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    conclusion: str = ""
    finalized: bool = False

    def observed_exception_ids(self) -> set[str]:
        ids = set()
        for result in self.test_results.values():
            for exc in result["exceptions"]:
                ids.add(exc.get("ticket_id") or exc.get("deploy_id"))
        return ids

    def add_finding(self, **kwargs) -> str:
        """Guardrail: a finding may only cite evidence that a test actually
        flagged, so the agent cannot invent exceptions."""
        if kwargs["control_id"] not in self.test_results:
            raise ValueError(f"Control {kwargs['control_id']} has not been tested yet; run test_control first.")
        if kwargs["severity"] not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        unknown = set(kwargs["references"]) - self.observed_exception_ids()
        if unknown:
            raise ValueError(f"References {sorted(unknown)} were not flagged by any test; findings must cite tested exceptions.")
        self.findings.append(Finding(**kwargs))
        return f"Finding {len(self.findings)} recorded for {kwargs['control_id']}."

    def uncovered_exceptions(self) -> list[str]:
        cited = {r for f in self.findings for r in f.references}
        return sorted(self.observed_exception_ids() - cited)

    # ----- rendering -----------------------------------------------------
    def to_markdown(self) -> str:
        lines = [
            f"# Audit Workpaper — {self.audit_area}",
            "",
            f"**Period:** {self.period}  ",
            f"**Prepared:** {datetime.now():%Y-%m-%d %H:%M} by audit-evidence-agent (AI-assisted, requires reviewer sign-off)",
            "",
            "## 1. Test summary",
            "",
            "| Control | Population tested | Exceptions | Result |",
            "|---|---:|---:|---|",
        ]
        for cid, r in sorted(self.test_results.items()):
            lines.append(f"| {cid} | {r['population_tested']} | {r['exceptions_found']} | {r['result']} |")

        lines += ["", "## 2. Findings", ""]
        if not self.findings:
            lines.append("No findings.")
        order = {s: i for i, s in enumerate(SEVERITIES)}
        for i, f in enumerate(sorted(self.findings, key=lambda f: (order[f.severity], f.control_id)), 1):
            lines += [
                f"### Finding {i}: {f.title}  `{f.severity}`",
                "",
                f"- **Control:** {f.control_id}",
                f"- **Condition:** {f.condition}",
                f"- **Criteria:** {f.criteria}",
                f"- **Effect / risk:** {f.effect}",
                f"- **Recommendation:** {f.recommendation}",
                f"- **Evidence references:** {', '.join(f.references)}",
                "",
            ]

        lines += ["## 3. Exception detail", ""]
        for cid, r in sorted(self.test_results.items()):
            for e in r["exceptions"]:
                ref = e.get("ticket_id") or e.get("deploy_id")
                lines.append(f"- **{cid} / {ref}** — {e['attribute']}: {e['detail']}")
        lines += ["", "## 4. Conclusion", "", self.conclusion or "_Not concluded._", ""]
        return "\n".join(lines)
