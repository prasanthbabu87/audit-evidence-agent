from pathlib import Path
from types import SimpleNamespace as NS
import json

import pytest

from agent.evidence import EvidenceStore, business_days_between
from agent.llm_agent import AuditTrail, run_agent
from agent.offline import run_offline
from agent.tools import Toolbox
from datetime import datetime

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture
def toolbox():
    return Toolbox(EvidenceStore(DATA))


def refs(result):
    return sorted(e.get("ticket_id") or e.get("deploy_id") for e in result["exceptions"])


# ---------- deterministic control tests ----------
@pytest.mark.parametrize("control,expected", [
    ("CM-01", ["CHG-1007", "CHG-1012"]),
    ("CM-02", ["CHG-1015", "CHG-1030"]),
    ("CM-03", ["CHG-1019"]),
    ("CM-04", ["CHG-1022", "CHG-1026"]),
    ("CM-05", ["DEP-5031", "DEP-5032"]),
])
def test_control_exceptions(control, expected):
    assert refs(EvidenceStore(DATA).test_control(control)) == expected


def test_business_days_skips_weekend():
    fri = datetime(2026, 10, 16, 10, 0)
    assert business_days_between(fri, datetime(2026, 10, 19, 9, 0)) == 1  # Fri -> Mon


def test_unknown_control_rejected(toolbox):
    out, err = toolbox.run("test_control", {"control_id": "CM-99"})
    assert err and "Unknown control" in out


# ---------- guardrails ----------
FINDING = dict(control_id="CM-03", title="t", condition="c", criteria="c", effect="e",
               recommendation="r", severity="Medium")


def test_finding_requires_tested_control(toolbox):
    out, err = toolbox.run("record_finding", {**FINDING, "references": ["CHG-1019"]})
    assert err and "not been tested" in out


def test_finding_cannot_cite_invented_evidence(toolbox):
    toolbox.run("test_control", {"control_id": "CM-03"})
    out, err = toolbox.run("record_finding", {**FINDING, "references": ["CHG-1001"]})
    assert err and "not flagged" in out


def test_cannot_finalize_with_uncovered_exceptions(toolbox):
    for c in ["CM-01", "CM-02", "CM-03", "CM-04", "CM-05"]:
        toolbox.run("test_control", {"control_id": c})
    out, err = toolbox.run("finalize_workpaper", {"conclusion": "all good"})
    assert err and "not covered" in out


# ---------- end-to-end ----------
def test_offline_run_produces_complete_workpaper(toolbox, tmp_path):
    run_offline(toolbox, AuditTrail(tmp_path / "trail.jsonl"), verbose=False)
    wp = toolbox.workpaper
    assert wp.finalized and len(wp.findings) == 5 and not wp.uncovered_exceptions()
    assert "Finding 1" in wp.to_markdown()


class FakeClient:
    """Replays a scripted conversation to exercise the real tool-use loop."""

    def __init__(self, turns):
        self.turns, self.calls = list(turns), []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        blocks, stop = self.turns.pop(0)
        return NS(content=blocks, stop_reason=stop)


def tool(id_, name, **inp):
    return NS(type="tool_use", id=id_, name=name, input=inp)


def test_llm_loop_executes_tools_and_feeds_back_errors(toolbox, tmp_path):
    client = FakeClient([
        ([NS(type="text", text="Scoping."), tool("t1", "get_audit_scope")], "tool_use"),
        ([tool("t2", "record_finding", **FINDING, references=["CHG-1019"])], "tool_use"),  # premature -> error
        ([NS(type="text", text="Done.")], "end_turn"),
    ])
    trail = AuditTrail(tmp_path / "trail.jsonl")
    run_agent(toolbox, trail, client=client, verbose=False)

    tool_results = client.calls[2]["messages"][-1]["content"]
    assert tool_results[0]["tool_use_id"] == "t2" and tool_results[0]["is_error"] is True
    events = [json.loads(l)["event"] for l in trail.path.read_text().splitlines()]
    assert events[0] == "run_started" and events[-1] == "run_ended" and events.count("tool_call") == 2
