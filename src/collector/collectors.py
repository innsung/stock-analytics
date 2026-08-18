import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from database.database import upsert_financials, upsert_prices
from src.dart.client import DartClient
from src.kis.client import KISClient


@dataclass(frozen=True)
class PriceCollectionResult:
    code: str
    saved: int
    api_skipped: bool
    existing_start: str | None
    existing_end: str | None
    requested_ranges: tuple[tuple[str, str], ...]


def collect_prices(conn: sqlite3.Connection, client: KISClient, code: str, days: int) -> int:
    rows = []
    for item in client.daily_prices(code, days):
        rows.append((code, item["stck_bsop_date"], float(item["stck_oprc"]), float(item["stck_hgpr"]),
                     float(item["stck_lwpr"]), float(item["stck_clpr"]), int(item["acml_vol"]), "KIS"))
    upsert_prices(conn, rows)
    return len(rows)


def collect_prices_incremental(conn: sqlite3.Connection, client: KISClient, code: str, days: int,
                               refresh_days: int = 0) -> PriceCollectionResult:
    today = date.today()
    desired_start = today - timedelta(days=days)
    row = conn.execute("SELECT MIN(date), MAX(date) FROM stock_prices WHERE code=?", (code,)).fetchone()
    old_start = datetime.strptime(row[0], "%Y%m%d").date() if row and row[0] else None
    old_end = datetime.strptime(row[1], "%Y%m%d").date() if row and row[1] else None
    ranges: list[tuple[date, date]] = []
    if old_start is None:
        ranges.append((desired_start, today))
    else:
        if old_start > desired_start:
            gap_end = old_start - timedelta(days=1)
            # 주말만 포함된 선행 공백은 거래 데이터 누락이 아니다.
            if any((desired_start + timedelta(days=i)).weekday() < 5
                   for i in range((gap_end - desired_start).days + 1)):
                ranges.append((desired_start, gap_end))
        # 주말·휴장일을 고려해 최근 4일 안의 데이터면 최신으로 간주한다.
        if old_end < today - timedelta(days=4):
            ranges.append((old_end + timedelta(days=1), today))
        if refresh_days > 0:
            # 일일 운용은 최근 구간을 다시 조회해 최근 4일 완충 규칙으로 인한 지연을 막는다.
            ranges.append((max(desired_start, today - timedelta(days=refresh_days)), today))
    # 겹치는 조회범위를 병합해 같은 날짜를 중복 호출하지 않는다.
    merged: list[tuple[date, date]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    ranges = merged
    items: dict[str, dict] = {}
    for start, end in ranges:
        for item in client.daily_prices_range(code, start, end):
            items[item["stck_bsop_date"]] = item
    rows_to_save = [(code, item["stck_bsop_date"], float(item["stck_oprc"]), float(item["stck_hgpr"]),
                     float(item["stck_lwpr"]), float(item["stck_clpr"]), int(item["acml_vol"]), "KIS")
                    for item in items.values()]
    upsert_prices(conn, rows_to_save)
    return PriceCollectionResult(code, len(rows_to_save), not ranges,
        old_start.strftime("%Y%m%d") if old_start else None, old_end.strftime("%Y%m%d") if old_end else None,
        tuple((start.strftime("%Y%m%d"), end.strftime("%Y%m%d")) for start, end in ranges))


def collect_financials(conn: sqlite3.Connection, client: DartClient, code: str, year: int, report_code: str) -> int:
    corp_code = client.corp_code_map().get(code)
    if not corp_code:
        raise ValueError(f"DART에서 종목코드 {code}의 고유번호를 찾지 못했습니다.")
    disclosed_at = client.disclosure_date(corp_code, year, report_code)
    rows = []
    # 금융지주 등 일부 회사·과거연도는 연결재무(CFS)가 DART 단일회사
    # 전체계정 API에 없을 수 있다. CFS를 우선하고 없을 때만 OFS를 사용한다.
    items = client.financials(corp_code, year, report_code, "CFS")
    if not items:
        items = client.financials(corp_code, year, report_code, "OFS")
    for item in items:
        raw = item.get("thstrm_amount", "0").replace(",", "")
        try:
            amount = float(raw) if raw else None
        except ValueError:
            amount = None
        try:
            account_order = int(item.get("ord", ""))
        except (TypeError, ValueError):
            account_order = None
        rows.append((
            code, year, report_code, item.get("fs_div", "CFS"),
            item.get("sj_div", ""), item.get("account_id", ""),
            item["account_nm"], amount, item.get("currency"), account_order,
            disclosed_at or item.get("rcept_no", "")[:8] or None, "DART",
        ))
    upsert_financials(conn, rows)
    return len(rows)


def collect_valuation(conn: sqlite3.Connection, client: KISClient, code: str, snapshot_date: str | None = None) -> int:
    item = client.valuation_snapshot(code)
    def number(key):
        try:
            raw = item.get(key)
            return float(str(raw).replace(",", "")) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None
    day = snapshot_date or date.today().strftime("%Y%m%d")
    # hts_avls는 KIS 응답상 억원 단위이므로 원 단위로 정규화한다.
    market_cap = number("hts_avls")
    market_cap = market_cap * 100_000_000 if market_cap is not None else None
    conn.execute("""INSERT INTO valuation_snapshots(
        code,snapshot_date,price,market_cap,per,pbr,eps,bps,dividend_yield,source
        ) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(code,snapshot_date) DO UPDATE SET
        price=excluded.price,market_cap=excluded.market_cap,per=excluded.per,pbr=excluded.pbr,
        eps=excluded.eps,bps=excluded.bps,dividend_yield=excluded.dividend_yield,source=excluded.source""",
        (code, day, number("stck_prpr"), market_cap, number("per"), number("pbr"),
         number("eps"), number("bps"), number("divi_rate"), "KIS"))
    conn.commit()
    return 1
