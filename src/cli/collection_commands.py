from __future__ import annotations

import sqlite3
from collections.abc import Callable

from src.collector.collectors import (
    collect_financials,
    collect_prices_incremental,
    collect_valuation,
)
from src.dart.client import DartClient
from src.kis.client import KISClient, KISRateLimitError


COLLECTION_COMMANDS = frozenset({
    "collect-price",
    "collect-financial",
    "collect-multi",
    "collect-valuation",
    "collect-financial-series",
})


def run_collection_command(
    conn: sqlite3.Connection,
    settings,
    args,
    resolve_codes: Callable,
) -> None:
    """Run a collection command with consistent partial-failure handling."""
    if args.command not in COLLECTION_COMMANDS:
        raise ValueError(f"지원하지 않는 수집 명령입니다: {args.command}")

    if args.command == "collect-price":
        result = collect_prices_incremental(
            conn, KISClient(settings), args.code, args.days
        )
        message = (
            "API 호출 생략: 기존 데이터가 충분합니다."
            if result.api_skipped
            else f"{result.saved}건 증분 저장 완료: {result.requested_ranges}"
        )
        print(message)
        return

    if args.command == "collect-financial":
        count = collect_financials(
            conn,
            DartClient(settings.dart_api_key),
            args.code,
            args.year,
            args.report_code,
        )
        print(f"{count}건 저장 완료")
        return

    codes, _ = resolve_codes(args)
    if args.command == "collect-multi":
        _collect_multiple_prices(conn, settings, codes, args.days)
    elif args.command == "collect-valuation":
        _collect_multiple_valuations(conn, settings, codes)
    else:
        _collect_financial_series(
            conn, settings, codes, args.start_year, args.end_year
        )


def _collect_multiple_prices(conn, settings, codes: list[str], days: int) -> None:
    client = KISClient(settings)
    for code in codes:
        try:
            result = collect_prices_incremental(conn, client, code, days)
            status = "API 생략(충분)" if result.api_skipped else f"{result.saved}건 증분 저장"
            print(f"{code}: {status}")
        except KISRateLimitError as exc:
            print(f"{code}: 수집 중단 - {exc}")
            print("KIS 제한 오류이므로 남은 종목의 API 호출을 중단합니다.")
            break
        except Exception as exc:
            print(f"{code}: 수집 오류 - {exc} (다음 종목 계속)")


def _collect_multiple_valuations(conn, settings, codes: list[str]) -> None:
    client = KISClient(settings)
    for code in codes:
        try:
            collect_valuation(conn, client, code)
            print(f"{code}: PER·PBR·EPS·BPS 가치지표 저장")
        except KISRateLimitError as exc:
            print(str(exc))
            break
        except Exception as exc:
            print(f"{code}: 가치지표 오류 - {exc}")


def _collect_financial_series(
    conn,
    settings,
    codes: list[str],
    start_year: int,
    end_year: int,
) -> None:
    client = DartClient(settings.dart_api_key)
    for code in codes:
        for year in range(start_year, end_year + 1):
            for report_code in ("11013", "11012", "11014", "11011"):
                try:
                    count = collect_financials(
                        conn, client, code, year, report_code
                    )
                    print(f"{code} {year} {report_code}: {count}건")
                except Exception as exc:
                    print(f"{code} {year} {report_code}: 생략 - {exc}")
