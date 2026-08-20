from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def explode(demand: dict, bom: dict) -> list[dict[str, object]]:
    """Independent FG demand plus dependent component qty. No live inventory."""
    parent_map = {row["parent"]: row["components"] for row in bom["boms"]}
    rows: list[dict[str, object]] = []
    for line in demand["independentDemand"]:
        item = line["item"]
        week = line["week"]
        qty = float(line["qty"])
        rows.append({"item": item, "week": week, "qty": qty, "kind": "independent"})
        for component in parent_map.get(item, []):
            rows.append(
                {
                    "item": component["item"],
                    "week": week,
                    "qty": round(qty * float(component["qty"]), 3),
                    "kind": "dependent",
                    "parent": item,
                }
            )
    return rows


def load_oven(demand: dict, items: dict) -> list[dict[str, object]]:
    oven = next(row for row in items["resources"] if row["id"] == "OVEN-A")
    cap = float(oven["hoursPerWeek"])
    hours_each = float(demand["hoursPerLoaf"])
    by_week: dict[str, float] = defaultdict(float)
    for line in demand["independentDemand"]:
        by_week[line["week"]] += float(line["qty"]) * hours_each
    loads = []
    for week in demand["calendar"]:
        hours = round(by_week[week], 2)
        loads.append(
            {
                "resource": "OVEN-A",
                "week": week,
                "hours": hours,
                "capacity": cap,
                "breach": hours > cap,
            }
        )
    return loads


def run_plan(master_dir: Path, demand_path: Path) -> dict[str, object]:
    items = load_json(master_dir / "items.json")
    bom = load_json(master_dir / "bom.json")
    demand = load_json(demand_path)
    mps = explode(demand, bom)
    loads = load_oven(demand, items)
    return {
        "plant": items["plant"],
        "synthetic": True,
        "calendar": demand["calendar"],
        "mps": mps,
        "capacity": loads,
        "breaches": [row for row in loads if row["breach"]],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Demand → MPS + oven load (synthetic plant).")
    parser.add_argument("--master", type=Path, default=Path("samples/master"))
    parser.add_argument("--demand", type=Path, default=Path("samples/demand/weekly.json"))
    parser.add_argument("--out", type=Path, default=Path("samples/output/mps.json"))
    args = parser.parse_args()
    plan = run_plan(args.master, args.demand)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"breaches: {len(plan['breaches'])}")


if __name__ == "__main__":
    main()
