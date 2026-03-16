# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Decision Agent — Dashboard schema and output normalization.

Commands:
  schema              Print the full Decision Dashboard JSON schema
  normalize JSON      Normalize/validate a raw dashboard JSON

Faithfully reproduces the Decision Dashboard output format from the
original project's orchestrator + DecisionAgent.
"""

import io
import json
import sys
import argparse

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

_CANONICAL_SIGNAL = {"strong_buy": "buy", "buy": "buy", "hold": "hold", "sell": "sell", "strong_sell": "sell"}

DASHBOARD_SCHEMA = {
    "stock_name": "str",
    "sentiment_score": "int 0-100",
    "trend_prediction": "str",
    "operation_advice": "str",
    "decision_type": "buy|hold|sell",
    "confidence_level": "str — 高|中|低",
    "analysis_summary": "str — 2-3 sentences",
    "key_points": ["str"],
    "risk_warning": "str",
    "dashboard": {
        "core_conclusion": {
            "one_sentence": "str <=30 chars",
            "time_sensitivity": "str",
            "signal_type": "str — e.g. 🟢买入信号",
            "position_advice": {
                "no_position": "str — advice for empty position",
                "has_position": "str — advice for holding position",
            },
        },
        "data_perspective": {
            "trend_status": {
                "ma_alignment": "bullish|neutral|bearish",
                "trend_score": "int 0-100",
                "is_bullish": "bool",
            },
            "price_position": {
                "current_price": "float",
                "ma5": "float",
                "ma10": "float",
                "ma20": "float",
                "bias_ma5": "float — percent",
                "bias_status": "str",
                "support_level": "float|str",
                "resistance_level": "float|str",
            },
            "volume_analysis": {
                "volume_ratio": "float",
                "turnover_rate": "float|str",
                "volume_status": "heavy|normal|light",
            },
        },
        "intelligence": {
            "risk_alerts": ["str"],
            "positive_catalysts": ["str"],
            "sentiment_label": "str",
            "latest_news": "str",
            "key_news": [{"title": "str", "impact": "positive|negative|neutral"}],
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "float|str",
                "secondary_buy": "float|str",
                "stop_loss": "float|str",
                "take_profit": "float|str",
            },
            "position_strategy": {
                "suggested_position": "str",
                "entry_plan": "str",
                "risk_control": "str",
            },
            "action_checklist": ["str — items with checkmarks"],
        },
    },
}


def normalize_signal(signal, default="hold"):
    if not isinstance(signal, str):
        return default
    return _CANONICAL_SIGNAL.get(signal.strip().lower(), default)


def confidence_label(confidence):
    if confidence >= 0.75:
        return "高"
    if confidence >= 0.45:
        return "中"
    return "低"


def estimate_score(signal, confidence):
    confidence = max(0.0, min(1.0, float(confidence)))
    bands = {"buy": (65, 79), "hold": (45, 59), "sell": (20, 39)}
    lo, hi = bands.get(signal, (45, 59))
    return int(round(lo + (hi - lo) * confidence))


def signal_type_label(signal):
    return {"buy": "🟢买入信号", "hold": "⚪观望信号", "sell": "🔴卖出信号"}.get(signal, "⚪观望信号")


def default_position_advice(signal):
    return {
        "buy": {"no_position": "可结合支撑位分批试仓，避免一次性追高。", "has_position": "可继续持有，回踩关键位不破再考虑加仓。"},
        "hold": {"no_position": "暂不追高，等待更清晰的入场条件。", "has_position": "以观察为主，跌破止损位再执行风控。"},
        "sell": {"no_position": "暂不参与，等待风险充分释放。", "has_position": "优先控制回撤，按计划减仓或离场。"},
    }.get(signal, {"no_position": "观望", "has_position": "持有观察"})


def default_position_size(signal):
    return {"buy": "轻仓试仓", "hold": "控制仓位", "sell": "降仓防守"}.get(signal, "控制仓位")


def downgrade_signal(signal, steps=1):
    order = ["buy", "hold", "sell"]
    try:
        idx = order.index(signal)
    except ValueError:
        return signal
    return order[min(len(order) - 1, idx + max(0, steps))]


def adjust_sentiment_score(score, signal):
    bands = {"buy": (60, 79), "hold": (40, 59), "sell": (0, 39)}
    lo, hi = bands.get(signal, (0, 100))
    return max(lo, min(hi, score))


def normalize_dashboard(raw: dict) -> dict:
    """Normalize a raw dashboard dict to the canonical schema.

    Fills in missing fields with sensible defaults. Mirrors the logic
    from the original project's AgentOrchestrator._normalize_dashboard_payload.
    """
    p = dict(raw)

    decision_type = normalize_signal(p.get("decision_type", "hold"))
    p["decision_type"] = decision_type

    score = p.get("sentiment_score")
    try:
        score = int(score)
    except (TypeError, ValueError):
        score = estimate_score(decision_type, 0.5)
    p["sentiment_score"] = score

    p.setdefault("stock_name", "")
    p.setdefault("trend_prediction", "")
    p.setdefault("operation_advice", {"buy": "买入", "hold": "观望", "sell": "减仓/卖出"}.get(decision_type, "观望"))
    p.setdefault("confidence_level", confidence_label(score / 100.0))
    p.setdefault("analysis_summary", "")
    p.setdefault("key_points", [])
    p.setdefault("risk_warning", "暂无额外风险提示")

    db = p.get("dashboard")
    if not isinstance(db, dict):
        db = {}
    db = dict(db)

    core = dict(db.get("core_conclusion") or {})
    core.setdefault("one_sentence", p.get("analysis_summary", "")[:60])
    core.setdefault("time_sensitivity", "本周内")
    core.setdefault("signal_type", signal_type_label(decision_type))
    pa = core.get("position_advice")
    if not isinstance(pa, dict):
        pa = default_position_advice(decision_type)
    else:
        defaults = default_position_advice(decision_type)
        pa.setdefault("no_position", defaults["no_position"])
        pa.setdefault("has_position", defaults["has_position"])
    core["position_advice"] = pa
    db["core_conclusion"] = core

    dp = db.get("data_perspective")
    if not isinstance(dp, dict):
        dp = {}
    db["data_perspective"] = dp

    intel = dict(db.get("intelligence") or {})
    intel.setdefault("risk_alerts", [])
    intel.setdefault("positive_catalysts", [])
    intel.setdefault("sentiment_label", "neutral")
    intel.setdefault("key_news", [])
    db["intelligence"] = intel

    bp = dict(db.get("battle_plan") or {})
    sp = dict(bp.get("sniper_points") or {})
    sp.setdefault("ideal_buy", "N/A")
    sp.setdefault("secondary_buy", "N/A")
    sp.setdefault("stop_loss", "待补充")
    sp.setdefault("take_profit", "N/A")
    bp["sniper_points"] = sp
    ps = dict(bp.get("position_strategy") or {})
    ps.setdefault("suggested_position", default_position_size(decision_type))
    ps.setdefault("entry_plan", pa["no_position"])
    ps.setdefault("risk_control", f"止损参考 {sp.get('stop_loss', '待补充')}")
    bp["position_strategy"] = ps
    bp.setdefault("action_checklist", [])
    db["battle_plan"] = bp

    p["dashboard"] = db
    return p


def apply_risk_override(dashboard: dict, risk_opinion: dict, risk_flags: list) -> dict:
    """Apply risk agent's veto/downgrade rules to the dashboard.

    Mirrors AgentOrchestrator._apply_risk_override from the original project.
    """
    d = dict(dashboard)
    adjustment = str(risk_opinion.get("signal_adjustment", "")).lower()
    has_high = any(str(f.get("severity", "")).lower() == "high" for f in risk_flags)
    veto_buy = bool(risk_opinion.get("veto_buy")) or adjustment == "veto" or has_high

    current = normalize_signal(d.get("decision_type", "hold"))
    new = current

    if veto_buy and current == "buy":
        new = "hold"
    elif adjustment == "downgrade_one":
        new = downgrade_signal(current, 1)
    elif adjustment == "downgrade_two":
        new = downgrade_signal(current, 2)

    if new == current:
        return d

    d["decision_type"] = new
    d["sentiment_score"] = adjust_sentiment_score(d.get("sentiment_score", 50), new)

    summary = d.get("analysis_summary", "")
    d["analysis_summary"] = f"[风控下调: {current} -> {new}] {summary}"

    op_map = {"buy": "买入", "hold": "观望", "sell": "减仓/卖出"}
    d["operation_advice"] = f"{op_map.get(new, '观望')}（原建议已被风控下调）"

    warnings = []
    if isinstance(d.get("risk_warning"), str) and d["risk_warning"].strip():
        warnings.append(d["risk_warning"].strip())
    reasoning = risk_opinion.get("reasoning", "")
    if reasoning:
        warnings.append(reasoning)
    for flag in risk_flags[:3]:
        desc = str(flag.get("description", "")).strip()
        if desc:
            warnings.append(f"[{flag.get('severity', 'risk')}] {desc}")
    d["risk_warning"] = f"风控接管：最终信号已下调为 {new}。" + " ".join(warnings)

    db = d.get("dashboard")
    if isinstance(db, dict):
        core = db.get("core_conclusion")
        if isinstance(core, dict):
            core["signal_type"] = {"hold": "🟡持有观望", "sell": "🔴卖出信号"}.get(new, "⚠️风险警告")
            s = core.get("one_sentence", "")
            if s:
                core["one_sentence"] = f"{s}（风控下调）"
            pa = core.get("position_advice", {})
            if isinstance(pa, dict):
                if new == "hold":
                    pa["no_position"] = "风险未解除前先观望，等待更清晰的入场条件。"
                    pa["has_position"] = "谨慎持有并收紧止损，待风险缓解后再考虑加仓。"
                elif new == "sell":
                    pa["no_position"] = "风险明显偏高，暂不新开仓。"
                    pa["has_position"] = "优先控制回撤，建议减仓或退出高风险仓位。"
    return d


def cmd_schema(_args):
    print(json.dumps(DASHBOARD_SCHEMA, ensure_ascii=False, indent=2))


def cmd_normalize(args):
    try:
        raw = json.loads(args.dashboard_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    result = normalize_dashboard(raw)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_risk_override(args):
    try:
        dashboard = json.loads(args.dashboard_json)
        risk_opinion = json.loads(args.risk_json)
        risk_flags = json.loads(args.flags_json) if args.flags_json else []
    except json.JSONDecodeError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    result = apply_risk_override(dashboard, risk_opinion, risk_flags)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Decision Agent — dashboard schema & normalization")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("schema", help="Print Decision Dashboard schema")

    p_n = sub.add_parser("normalize", help="Normalize raw dashboard JSON")
    p_n.add_argument("dashboard_json")

    p_r = sub.add_parser("risk-override", help="Apply risk override to dashboard")
    p_r.add_argument("dashboard_json")
    p_r.add_argument("risk_json", help="Risk agent opinion JSON")
    p_r.add_argument("--flags-json", default=None, help="Risk flags array JSON")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"schema": cmd_schema, "normalize": cmd_normalize, "risk-override": cmd_risk_override}[args.command](args)


if __name__ == "__main__":
    main()
