from __future__ import annotations


COMMAND_GROUPS = {
    "runtime": frozenset({
        "shadow-list", "daily-status", "ml-readiness", "shadow-report", "daily-shadow",
        "build-feature-store", "ml-train", "ml-walk-forward", "ml-predict",
    }),
    "data_operation": frozenset({
        "import-valuation-snapshots-v321", "build-data-foundation-v321", "krx-provider-check-v321",
        "acquire-historical-data-v321", "db-health-v321", "backup-db-v321",
    }),
    "event": frozenset({
        "acquire-payout-actions-v321", "build-event-reconciliation-v321", "build-total-return-v321",
        "prepare-event-verification-v321", "finalize-event-reconciliation-v321",
        "prepare-official-event-evidence-v321", "resolve-official-events-v321",
        "acquire-official-event-candidates-v321", "enrich-official-evidence-v321",
        "build-market-adjustment-evidence-v321", "merge-strict-evidence-v321",
    }),
    "dividend": frozenset({
        "build-stock-cash-amount-candidates-v321", "prepare-official-cash-events-v321",
        "validate-official-cash-events-v321", "compare-cash-amount-candidates-v321",
        "prepare-benchmark-etf-distributions-v321", "validate-benchmark-etf-distributions-v321",
        "inject-benchmark-etf-events-v321", "summarize-stock-dividend-resolution-v321",
        "acquire-kodex-distributions-v321", "build-stock-dividend-ambiguity-report-v321",
        "discover-kodex-dynamic-endpoints-v321", "refine-stock-dividend-candidates-v321",
        "rank-probe-kodex-endpoints-v321", "acquire-stock-dividend-decisions-v321",
        "build-stock-dividend-exdate-queue-v321", "inspect-kodex-high-signal-responses-v321",
        "extract-dart-dividend-record-dates-v321", "merge-dividend-date-candidates-v321",
        "build-explicit-stock-exdate-evidence-v321", "export-benchmark-calendar-v321",
        "build-record-date-calendar-candidates-v321", "parse-kodex-distribution-tables-v321",
        "build-market-exdate-verification-queue-v321", "validate-official-market-exdates-v321",
        "summarize-kodex-high-signal-bodies-v321",
    }),
}


def command_group(command: str) -> str | None:
    return next((group for group, commands in COMMAND_GROUPS.items() if command in commands), None)


def dispatch_foundation_command(
    conn,
    settings,
    args,
    *,
    resolve_codes,
    print_shadow_report,
    execute_daily_shadow,
    load_universe,
) -> bool:
    group = command_group(args.command)
    if group == "runtime":
        from src.cli.runtime_commands import run_runtime_command

        run_runtime_command(
            conn, settings, args, resolve_codes=resolve_codes,
            print_shadow_report=print_shadow_report, execute_daily_shadow=execute_daily_shadow,
        )
    elif group == "data_operation":
        from src.cli.data_operation_commands import run_data_operation_command

        run_data_operation_command(conn, settings, args)
    elif group == "event":
        from src.cli.event_commands import run_event_command

        run_event_command(conn, settings, args, load_universe=load_universe)
    elif group == "dividend":
        from src.cli.dividend_commands import run_dividend_command

        run_dividend_command(conn, settings, args)
    else:
        return False
    return True
