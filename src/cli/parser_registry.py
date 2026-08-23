from __future__ import annotations

import argparse
from functools import lru_cache
from importlib import import_module
from typing import Callable, NamedTuple


class ParserSpec(NamedTuple):
    module_name: str
    registrar_name: str


PARSER_SPECS = tuple(
    ParserSpec(f"src.cli.{name}_parsers", f"register_{name}_parsers")
    for name in (
        "core",
        "portfolio",
        "shadow",
        "ml",
        "data_operation",
        "event_reconciliation",
        "official_event",
        "cash_distribution",
        "kodex_distribution",
        "stock_dividend_evidence",
        "kind",
        "corporate_action",
        "spinoff",
        "subsidiary_action",
        "direct_action",
        "historical_dividend",
        "historical_kind",
        "dividend_resolution",
        "dividend_backlog",
        "historical_chain",
        "primary_adjustment",
        "adjustment_applicability",
        "company_audit",
        "release",
        "kind_followup",
        "diagnostic",
    )
)

if len(PARSER_SPECS) != len(set(PARSER_SPECS)):
    raise ValueError("Duplicate parser registrar specification")


@lru_cache(maxsize=None)
def load_parser_registrar(spec: ParserSpec) -> Callable:
    return getattr(import_module(spec.module_name), spec.registrar_name)


def register_all_parsers(subparsers) -> None:
    for spec in PARSER_SPECS:
        load_parser_registrar(spec)(subparsers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KIS + DART 분석·백테스트 MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_all_parsers(subparsers)
    return parser
