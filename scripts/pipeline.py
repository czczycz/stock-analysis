# /// script
# requires-python = ">=3.10"
# dependencies = ['akshare', 'yfinance', 'pandas', 'numpy', 'scipy', 'pyyaml']
# ///
# NOTE: akshare is still needed here because intel_agent and risk_agent
# import it at runtime for news fetching.
"""
Pipeline Manager — configurable multi-stage stock analysis.

Commands:
  analyze TICKER [--mode MODE]   Run analysis pipeline (default: full)
  modes                          List available pipeline modes and stages
  schema                         Print Decision Dashboard JSON schema

Built-in modes:
  full       — Technical + Intel + Risk + Strategy (default)
  quick      — Technical + Strategy (skip news/risk)
  news       — Intel + Risk (sentiment & risk only)
  technical  — Technical only
"""

import json
import sys
import argparse
from typing import Any, Callable, Dict, List

from _bootstrap import bootstrap; bootstrap()  # noqa: E702


# ---------------------------------------------------------------------------
# Stage runners — each takes (ticker, context) and returns a dict
# ---------------------------------------------------------------------------

def _run_technical(ticker: str, _ctx: dict) -> dict:
    from tools import get_technical_indicators
    return get_technical_indicators(ticker)


def _run_intel(ticker: str, _ctx: dict) -> dict:
    from intel_agent import fetch_intel
    return fetch_intel(ticker)


def _run_risk(ticker: str, _ctx: dict) -> dict:
    from risk_agent import fetch_risk_data
    return fetch_risk_data(ticker)


def _run_strategy(ticker: str, ctx: dict) -> dict:
    from strategy_manager import detect_regime, load_all_strategies
    from tools import is_stock_hot
    from tools._providers import is_a_share

    tech_data = ctx.get("technical", {})

    is_hot = False
    hot_reason = ""
    if is_a_share(ticker):
        stock_name = ""
        if "_error" not in tech_data:
            stock_name = tech_data.get("realtime_quote", {}).get("name", "")
        if stock_name:
            try:
                hot_result = is_stock_hot(stock_name)
                is_hot = hot_result.get("is_hot", False)
                if is_hot:
                    sectors = [s["sector_name"] for s in hot_result["matched_sectors"]]
                    hot_reason = f"Leading stock in: {', '.join(sectors)}"
            except Exception as e:
                print(f"[strategy/is_stock_hot] {e}", file=sys.stderr)

    regime_info = detect_regime(
        tech_data if "_error" not in tech_data else {},
        is_hot=is_hot,
        hot_reason=hot_reason,
    )
    strategies = load_all_strategies()
    recommended = []
    for name in regime_info["recommended_strategies"][:3]:
        s = strategies.get(name)
        if s:
            recommended.append({
                "name": s["name"],
                "display_name": s.get("display_name", ""),
                "description": s.get("description", ""),
                "instructions": s.get("instructions", ""),
            })
    return {
        "regime": regime_info["regime"],
        "reason": regime_info["reason"],
        "strategies": recommended,
    }


# ---------------------------------------------------------------------------
# PipelineManager
# ---------------------------------------------------------------------------

# Global registry of stage runner functions.
# Custom stages can be added via PipelineManager.register_stage().
STAGE_REGISTRY: Dict[str, Callable[[str, dict], dict]] = {
    "technical": _run_technical,
    "intel": _run_intel,
    "risk": _run_risk,
    "strategy": _run_strategy,
}


class PipelineManager:
    """Configurable multi-mode analysis pipeline manager.

    Built-in modes run different combinations of stages.
    Register custom modes via ``register_mode()`` or custom stages
    via ``register_stage()`` to extend the pipeline.
    """

    BUILTIN_MODES: Dict[str, Dict[str, Any]] = {
        "full": {
            "stages": ["technical", "intel", "risk", "strategy"],
            "description": "Full 5-stage analysis (default)",
        },
        "quick": {
            "stages": ["technical", "strategy"],
            "description": "Technical + Strategy — skip news/risk for speed",
        },
        "news": {
            "stages": ["intel", "risk"],
            "description": "Intel + Risk — sentiment & risk screening only",
        },
        "technical": {
            "stages": ["technical"],
            "description": "Technical indicators only",
        },
    }

    def __init__(self) -> None:
        self._modes: Dict[str, Dict[str, Any]] = {
            k: dict(v) for k, v in self.BUILTIN_MODES.items()
        }

    # -- Mode management ----------------------------------------------------

    def register_mode(
        self,
        name: str,
        stages: List[str],
        description: str = "",
    ) -> None:
        """Register a custom pipeline mode.

        ``stages`` must be a list of registered stage names.
        """
        unknown = [s for s in stages if s not in STAGE_REGISTRY]
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}. "
                             f"Available: {list(STAGE_REGISTRY)}")
        self._modes[name] = {
            "stages": stages,
            "description": description or f"Custom: {' → '.join(stages)}",
        }

    def list_modes(self) -> Dict[str, str]:
        return {k: v["description"] for k, v in self._modes.items()}

    # -- Stage management ---------------------------------------------------

    @staticmethod
    def register_stage(name: str, runner: Callable[[str, dict], dict]) -> None:
        """Register a custom stage runner globally."""
        STAGE_REGISTRY[name] = runner

    @staticmethod
    def available_stages() -> List[str]:
        return list(STAGE_REGISTRY)

    # -- Execution ----------------------------------------------------------

    def run(self, ticker: str, mode: str = "full") -> dict:
        if mode not in self._modes:
            return {
                "_error": f"Unknown mode '{mode}'",
                "available_modes": list(self._modes),
            }

        stage_names = self._modes[mode]["stages"]
        result: Dict[str, Any] = {"ticker": ticker, "mode": mode}
        ctx: Dict[str, Any] = {}

        for stage_name in stage_names:
            runner = STAGE_REGISTRY.get(stage_name)
            if not runner:
                result[stage_name] = {"_error": f"No runner for stage '{stage_name}'"}
                continue
            try:
                data = runner(ticker, ctx)
            except Exception as e:
                print(f"[{stage_name}] {e}", file=sys.stderr)
                data = {"_error": str(e)}
            result[stage_name] = data
            ctx[stage_name] = data

        from decision_agent import DASHBOARD_SCHEMA
        result["dashboard_schema"] = DASHBOARD_SCHEMA
        return result


# Module-level singleton
manager = PipelineManager()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_analyze(args: argparse.Namespace) -> None:
    result = manager.run(args.ticker.strip(), args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_modes(_args: argparse.Namespace) -> None:
    print(json.dumps({
        "modes": manager.list_modes(),
        "available_stages": manager.available_stages(),
    }, ensure_ascii=False, indent=2))


def cmd_schema(_args: argparse.Namespace) -> None:
    from decision_agent import DASHBOARD_SCHEMA
    print(json.dumps(DASHBOARD_SCHEMA, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline Manager — configurable stock analysis")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("analyze", help="Run analysis pipeline")
    p.add_argument("ticker", help="Stock ticker / code (e.g. 601919, AAPL)")
    p.add_argument("--mode", default="full",
                   help="Pipeline mode (default: full). Run 'modes' to list all.")

    sub.add_parser("modes", help="List available pipeline modes")
    sub.add_parser("schema", help="Print Decision Dashboard schema")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"analyze": cmd_analyze, "modes": cmd_modes, "schema": cmd_schema}[
        args.command
    ](args)


if __name__ == "__main__":
    main()
