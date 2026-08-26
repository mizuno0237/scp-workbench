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
        utilization = round(100.0 * hours / cap, 1) if cap else 0.0
        loads.append(
            {
                "resource": "OVEN-A",
                "week": week,
                "hours": hours,
                "capacity": cap,
                "utilizationPct": utilization,
                "breach": hours > cap,
            }
        )
    return loads


def board_markdown(plan: dict[str, object]) -> str:
    """Human-readable oven board. A supervisor can read this without opening JSON."""
    lines = [
        "# Cedarline Plant 1 — weekly oven board (synthetic)",
        "",
        f"Plant `{plan['plant']}`. Peak-week breach is the demo.",
        "",
        "| Week | Hours | Capacity | Util % | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in plan["capacity"]:
        status = "BREACH" if row["breach"] else "ok"
        lines.append(
            f"| {row['week']} | {row['hours']} | {row['capacity']} | {row['utilizationPct']} | {status} |"
        )
    lines.append("")
    return "\n".join(lines)


def propose_cut(plan: dict[str, object], demand: dict) -> list[dict[str, object]]:
    """Cut independent demand so every week fits the oven. Do not invent extra capacity."""
    hours_each = float(demand["hoursPerLoaf"])
    qty_by_week = {line["week"]: float(line["qty"]) for line in demand["independentDemand"]}
    cuts: list[dict[str, object]] = []
    for row in plan["capacity"]:
        if not row["breach"]:
            continue
        cap_qty = int(float(row["capacity"]) / hours_each)
        current = qty_by_week[str(row["week"])]
        cuts.append(
            {
                "item": "FG-LOAF-500",
                "week": row["week"],
                "fromQty": current,
                "toQty": cap_qty,
                "cutQty": current - cap_qty,
                "reason": "oven hours exceed weekly capacity",
            }
        )
    return cuts


def cuts_markdown(plan: dict[str, object]) -> str:
    lines = [
        "# Cedarline Plant 1 — proposed cuts (synthetic)",
        "",
        "Do not invent extra oven hours. Cut independent demand instead.",
        "",
        "| Item | Week | From | To | Cut | Reason |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in plan["cuts"]:
        lines.append(
            f"| {row['item']} | {row['week']} | {row['fromQty']} | {row['toQty']} | {row['cutQty']} | {row['reason']} |"
        )
    if not plan["cuts"]:
        lines.append("| — | — | — | — | — | no breach |")
    lines.append("")
    return "\n".join(lines)


def pegging_markdown(plan: dict[str, object]) -> str:
    """Dependent qty by week. Flour and yeast are pegged to the loaf, not guessed."""
    lines = [
        "# Cedarline Plant 1 — component pegging (synthetic)",
        "",
        "Dependent demand follows the BOM. No live warehouse on-hand.",
        "",
        "| Item | Week | Qty | Parent |",
        "| --- | --- | ---: | --- |",
    ]
    rows = [row for row in plan["mps"] if row["kind"] == "dependent"]
    for row in rows:
        lines.append(f"| {row['item']} | {row['week']} | {row['qty']} | {row['parent']} |")
    if not rows:
        lines.append("| — | — | — | no dependent demand |")
    lines.append("")
    return "\n".join(lines)


def oven_gantt_model(plan: dict[str, object]) -> dict[str, object]:
    """Weekly oven load as a pixi-gantt model. One bar per week on OVEN-A."""
    week_ms = 7 * 24 * 3_600_000
    origin = 1_725_148_800_000
    loads = list(plan["capacity"])
    segments = []
    for index, row in enumerate(loads):
        start = origin + index * week_ms
        end = start + week_ms
        color = "#B5462A" if row["breach"] else "#3F7D6A"
        segments.append(
            {
                "id": f"seg-{row['week']}",
                "blockId": f"block-{row['week']}",
                "blockStartTime": start,
                "blockEndTime": end,
                "rowId": "oven-a",
                "startTime": start,
                "endTime": end,
                "label": f"{row['week']}  {row['hours']}h / {row['capacity']}h",
                "color": color,
                "taskType": "OVEN",
                "layer": 0,
            }
        )
    last_end = origin + max(len(loads), 1) * week_ms
    return {
        "rows": [
            {
                "id": "oven-a",
                "label": "OVEN-A  Cedarline Plant 1",
                "startTime": origin,
                "startLabel": str(loads[0]["week"]) if loads else "",
                "laneCount": 1,
                "height": 40,
            }
        ],
        "segments": segments,
        "links": [],
        "timeRange": {"min": origin - week_ms, "max": last_end + week_ms},
        "synthetic": True,
    }


def board_html(plan: dict[str, object]) -> str:
    """Standalone supervisor page. Open in a browser — no npm, no live factory."""
    bars = []
    for row in plan["capacity"]:
        width = min(float(row["utilizationPct"]), 140)
        klass = "breach" if row["breach"] else "ok"
        bars.append(
            f'<div class="week"><span class="wk">{row["week"]}</span>'
            f'<div class="track"><i class="{klass}" style="width:{width}%"></i></div>'
            f'<span class="num">{row["hours"]} / {row["capacity"]} h · {row["utilizationPct"]}%</span></div>'
        )
    cuts = "".join(
        f"<tr><td>{row['item']}</td><td>{row['week']}</td><td>{row['fromQty']}</td>"
        f"<td>{row['toQty']}</td><td>{row['cutQty']}</td></tr>"
        for row in plan["cuts"]
    ) or "<tr><td colspan='5'>no breach</td></tr>"
    peg = "".join(
        f"<tr><td>{row['item']}</td><td>{row['week']}</td><td>{row['qty']}</td><td>{row['parent']}</td></tr>"
        for row in plan["mps"]
        if row["kind"] == "dependent"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Cedarline Plant 1 — oven board (synthetic)</title>
  <style>
    body {{ font: 15px/1.45 Georgia, serif; margin: 32px; background: #f4f0e6; color: #1f241e; }}
    h1 {{ font-size: 22px; }}
    .note {{ color: #5c6158; }}
    .week {{ display: grid; grid-template-columns: 7rem 1fr 14rem; gap: 10px; align-items: center; margin: 8px 0; }}
    .track {{ background: #ddd6c4; height: 18px; border-radius: 2px; }}
    .track i {{ display: block; height: 18px; }}
    .ok {{ background: #3F7D6A; }}
    .breach {{ background: #B5462A; }}
    table {{ border-collapse: collapse; margin-top: 18px; width: 100%; }}
    th, td {{ border: 1px solid #cfc6b0; padding: 6px 8px; text-align: left; }}
    th {{ background: #ece6d4; }}
  </style>
</head>
<body>
  <p class="note">Synthetic plant · finite capacity is the demo · not a live bakery</p>
  <h1>Cedarline Plant 1 — weekly oven board</h1>
  <p>Plant <code>{plan["plant"]}</code>. Week 38 is the breach (90 h vs 80 h).</p>
  {''.join(bars)}
  <h2>Proposed cuts</h2>
  <table><thead><tr><th>Item</th><th>Week</th><th>From</th><th>To</th><th>Cut</th></tr></thead><tbody>{cuts}</tbody></table>
  <h2>Component pegging</h2>
  <table><thead><tr><th>Item</th><th>Week</th><th>Qty</th><th>Parent</th></tr></thead><tbody>{peg}</tbody></table>
</body>
</html>
"""


def run_plan(master_dir: Path, demand_path: Path) -> dict[str, object]:
    items = load_json(master_dir / "items.json")
    bom = load_json(master_dir / "bom.json")
    demand = load_json(demand_path)
    mps = explode(demand, bom)
    loads = load_oven(demand, items)
    plan = {
        "plant": items["plant"],
        "synthetic": True,
        "calendar": demand["calendar"],
        "mps": mps,
        "capacity": loads,
        "breaches": [row for row in loads if row["breach"]],
    }
    plan["cuts"] = propose_cut(plan, demand)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Demand → MPS + oven load (synthetic plant).")
    parser.add_argument("--master", type=Path, default=Path("samples/master"))
    parser.add_argument("--demand", type=Path, default=Path("samples/demand/weekly.json"))
    parser.add_argument("--out", type=Path, default=Path("samples/output/mps.json"))
    parser.add_argument("--board", type=Path, default=Path("samples/output/board.md"))
    parser.add_argument("--cuts", type=Path, default=Path("samples/output/cuts.md"))
    parser.add_argument("--peg", type=Path, default=Path("samples/output/pegging.md"))
    parser.add_argument("--html", type=Path, default=Path("samples/output/board.html"))
    parser.add_argument("--gantt", type=Path, default=Path("samples/output/gantt.json"))
    args = parser.parse_args()
    plan = run_plan(args.master, args.demand)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    args.board.write_text(board_markdown(plan), encoding="utf-8")
    args.cuts.write_text(cuts_markdown(plan), encoding="utf-8")
    args.peg.write_text(pegging_markdown(plan), encoding="utf-8")
    args.html.write_text(board_html(plan), encoding="utf-8")
    args.gantt.write_text(json.dumps(oven_gantt_model(plan), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"wrote {args.board}")
    print(f"wrote {args.cuts}")
    print(f"wrote {args.peg}")
    print(f"wrote {args.html}")
    print(f"wrote {args.gantt}")
    print(f"breaches: {len(plan['breaches'])}")
    print(f"cuts: {len(plan['cuts'])}")


if __name__ == "__main__":
    main()
