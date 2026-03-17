# /// script
# requires-python = ">=3.10"
# dependencies = ['pyyaml', 'rich']
# ///
"""
Strategy Manager — trading strategy lifecycle management.

Commands:
  list                          List all available strategies
  load NAME [NAME2 ...]         Load strategy instructions by name
  recommend TECH_JSON            Auto-select strategies by market regime
  aggregate EVALUATIONS_JSON    Aggregate strategy evaluations into consensus
  schema                        Print strategy evaluation output schema

Strategy files are loaded from strategies/ and custom_strategies/ directories.
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from _bootstrap import bootstrap; bootstrap()  # noqa: E702

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required", file=sys.stderr)
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    console = Console()
except ImportError:
    console = None

SKILL_ROOT = Path(__file__).resolve().parent.parent
STRATEGIES_DIR = SKILL_ROOT / "strategies"
CUSTOM_STRATEGIES_DIR = SKILL_ROOT / "custom_strategies"

REGIME_STRATEGIES = {
    "trending_up": ["bull_trend", "volume_breakout", "ma_golden_cross"],
    "trending_down": ["shrink_pullback", "bottom_volume"],
    "sideways": ["box_oscillation", "shrink_pullback"],
    "volatile": ["chan_theory", "wave_theory"],
    "sector_hot": ["dragon_head", "emotion_cycle"],
}
DEFAULT_STRATEGIES = ["bull_trend", "shrink_pullback"]

SIGNAL_SCORES = {"strong_buy": 5.0, "buy": 4.0, "hold": 3.0, "sell": 2.0, "strong_sell": 1.0}
SCORE_TO_SIGNAL = [(4.5, "strong_buy"), (3.5, "buy"), (2.5, "hold"), (1.5, "sell"), (0.0, "strong_sell")]

EVAL_SCHEMA = {
    "strategy_id": "str",
    "signal": "strong_buy|buy|hold|sell|strong_sell",
    "confidence": "float 0.0-1.0",
    "conditions_met": ["str"],
    "conditions_missed": ["str"],
    "score_adjustment": "int -20 to +20",
    "reasoning": "str — 2-3 sentence strategy evaluation",
}


def load_strategy(filepath: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and data.get("name"):
            data["_source"] = str(filepath)
            return data
    except Exception:
        pass
    return None


def load_all_strategies() -> Dict[str, Dict[str, Any]]:
    strategies = {}
    for directory in [STRATEGIES_DIR, CUSTOM_STRATEGIES_DIR]:
        if not directory.is_dir():
            continue
        for f in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
            s = load_strategy(f)
            if s:
                strategies[s["name"]] = s
    return strategies


def detect_regime(
    tech_data: Dict[str, Any],
    is_hot: bool = False,
    hot_reason: str = "",
) -> Dict[str, Any]:
    """Detect market regime from technical data + optional hot-sector flag.

    Regime priority: sector_hot > trending_up > trending_down > volatile > sideways.
    ``sector_hot`` triggers when ``is_hot`` is True (determined by ``is_stock_hot`` tool).
    """
    ma = str(tech_data.get("ma_alignment", "neutral")).lower()
    try:
        ts = float(tech_data.get("trend_score", 50))
    except (TypeError, ValueError):
        ts = 50.0
    vs = str(tech_data.get("volume_status", "normal")).lower()

    if is_hot:
        regime, reason = "sector_hot", hot_reason or "Stock is leading stock of a hot sector"
    elif ma == "bullish" and ts >= 70:
        regime, reason = "trending_up", f"MA bullish + trend_score={ts:.0f}"
    elif ma == "bearish" and ts <= 30:
        regime, reason = "trending_down", f"MA bearish + trend_score={ts:.0f}"
    elif vs == "heavy" and 30 < ts < 70:
        regime, reason = "volatile", f"Heavy volume + mixed trend_score={ts:.0f}"
    elif ma == "neutral" or 35 <= ts <= 65:
        regime, reason = "sideways", f"Neutral/range-bound trend_score={ts:.0f}"
    else:
        regime, reason = "sideways", "Default"

    return {"regime": regime, "reason": reason, "recommended_strategies": REGIME_STRATEGIES.get(regime, DEFAULT_STRATEGIES)}


def aggregate_evaluations(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not evaluations:
        return {"_error": "No evaluations provided"}

    weights = [max(0.1, float(ev.get("confidence", 0.5))) for ev in evaluations]
    total_w = sum(weights)

    weighted_score = sum(SIGNAL_SCORES.get(ev.get("signal", "hold"), 3.0) * w for ev, w in zip(evaluations, weights)) / total_w
    weighted_conf = sum(float(ev.get("confidence", 0.5)) * w for ev, w in zip(evaluations, weights)) / total_w
    total_adj = sum(float(ev.get("score_adjustment", 0)) for ev in evaluations if isinstance(ev.get("score_adjustment"), (int, float)))

    signal = "hold"
    for threshold, sig in SCORE_TO_SIGNAL:
        if weighted_score >= threshold:
            signal = sig
            break

    return {
        "consensus_signal": signal,
        "consensus_confidence": round(min(1.0, weighted_conf), 3),
        "weighted_score": round(weighted_score, 2),
        "total_adjustment": round(total_adj, 1),
        "strategy_count": len(evaluations),
        "individual": {ev.get("strategy_id", f"s{i}"): {"signal": ev.get("signal"), "confidence": ev.get("confidence")} for i, ev in enumerate(evaluations)},
    }


def cmd_list(args):
    strategies = load_all_strategies()
    if args.json:
        result = [{"name": s["name"], "display_name": s.get("display_name", ""), "description": s.get("description", ""), "category": s.get("category", "trend"), "regimes": [r for r, ids in REGIME_STRATEGIES.items() if s["name"] in ids], "source": "custom" if "custom_strategies" in s.get("_source", "") else "builtin"} for s in strategies.values()]
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif console:
        t = Table(title="Available Trading Strategies", box=box.ROUNDED)
        t.add_column("#", style="dim", width=3)
        t.add_column("ID", style="cyan")
        t.add_column("Name", style="bold")
        t.add_column("Category", style="yellow")
        t.add_column("Regimes", style="green")
        for i, s in enumerate(strategies.values(), 1):
            regimes = [r for r, ids in REGIME_STRATEGIES.items() if s["name"] in ids]
            t.add_row(str(i), s["name"], s.get("display_name", ""), s.get("category", "trend"), ", ".join(regimes) or "-")
        console.print(t)
    else:
        for s in strategies.values():
            print(f"  {s['name']:24s} {s.get('display_name', '')}")


def cmd_load(args):
    strategies = load_all_strategies()
    results = []
    for name in args.names:
        s = strategies.get(name)
        if not s:
            results.append({"name": name, "_error": "not found"}) if args.json else print(f"Not found: {name}", file=sys.stderr)
            continue
        entry = {"name": s["name"], "display_name": s.get("display_name", ""), "description": s.get("description", ""), "category": s.get("category", "trend"), "instructions": s.get("instructions", ""), "required_tools": s.get("required_tools", [])}
        if args.json:
            results.append(entry)
        else:
            print(f"\n=== {s['name']} ({s.get('display_name', '')}) ===")
            print(f"Category: {s.get('category', 'trend')}")
            print(f"Description: {s.get('description', '')}")
            print(f"\nInstructions:\n{s.get('instructions', 'N/A')}")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))


def cmd_recommend(args):
    try:
        tech_data = json.loads(args.tech_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"_error": str(e)}))
        sys.exit(1)

    regime_result = detect_regime(tech_data)
    names = regime_result["recommended_strategies"][:args.max]
    strategies = load_all_strategies()
    strats = [{"name": s["name"], "display_name": s.get("display_name", ""), "description": s.get("description", ""), "instructions": s.get("instructions", "")} for name in names if (s := strategies.get(name))]
    print(json.dumps({"regime": regime_result["regime"], "reason": regime_result["reason"], "strategies": strats}, ensure_ascii=False, indent=2))


def cmd_aggregate(args):
    try:
        evaluations = json.loads(args.evaluations_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"_error": str(e)}))
        sys.exit(1)
    if not isinstance(evaluations, list):
        evaluations = [evaluations]
    print(json.dumps(aggregate_evaluations(evaluations), ensure_ascii=False, indent=2))


def cmd_schema(_args):
    print(json.dumps(EVAL_SCHEMA, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Strategy Manager")
    parser.add_argument("--json", action="store_true", help="JSON output")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List strategies")
    p_l = sub.add_parser("load", help="Load strategy instructions")
    p_l.add_argument("names", nargs="+")
    p_r = sub.add_parser("recommend", help="Recommend strategies by regime")
    p_r.add_argument("tech_json")
    p_r.add_argument("--max", type=int, default=3)
    p_a = sub.add_parser("aggregate", help="Aggregate evaluations")
    p_a.add_argument("evaluations_json")
    sub.add_parser("schema", help="Strategy evaluation schema")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"list": cmd_list, "load": cmd_load, "recommend": cmd_recommend, "aggregate": cmd_aggregate, "schema": cmd_schema}[args.command](args)


if __name__ == "__main__":
    main()
