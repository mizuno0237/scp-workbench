from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scp_workbench.mps import run_plan

MASTER = ROOT / "samples" / "master"
DEMAND = ROOT / "samples" / "demand" / "weekly.json"


def test_mps_explodes_flour_for_week_36() -> None:
    plan = run_plan(MASTER, DEMAND)
    flour = next(
        row
        for row in plan["mps"]
        if row["item"] == "RM-FLOUR" and row["week"] == "2026-W36"
    )
    assert flour["qty"] == 384.0
    assert flour["kind"] == "dependent"


def test_oven_breaches_only_on_peak_week() -> None:
    plan = run_plan(MASTER, DEMAND)
    weeks = {row["week"]: row["breach"] for row in plan["capacity"]}
    assert weeks["2026-W36"] is False
    assert weeks["2026-W38"] is True
    assert [row["week"] for row in plan["breaches"]] == ["2026-W38"]
