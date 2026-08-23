from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scp_workbench.mps import board_markdown, cuts_markdown, run_plan

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


def test_board_marks_week_38_as_breach() -> None:
    board = board_markdown(run_plan(MASTER, DEMAND))
    assert "| 2026-W38 |" in board
    assert "BREACH" in board


def test_cut_brings_week_38_down_to_oven_hours() -> None:
    plan = run_plan(MASTER, DEMAND)
    cut = plan["cuts"][0]
    assert cut["week"] == "2026-W38"
    assert cut["fromQty"] == 1800
    assert cut["toQty"] == 1600
    assert cut["cutQty"] == 200


def test_cuts_markdown_names_week_38() -> None:
    text = cuts_markdown(run_plan(MASTER, DEMAND))
    assert "2026-W38" in text
    assert "200" in text
