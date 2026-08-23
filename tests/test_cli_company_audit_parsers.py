import argparse

from src.cli.company_audit_parsers import register_company_audit_parsers


def test_company_audit_parsers_register_all_commands():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_company_audit_parsers(sub)

    assert len(sub.choices) == 32
    args = parser.parse_args(["audit-shinhan-neoplux-share-exchange-v321"])
    assert args.command == "audit-shinhan-neoplux-share-exchange-v321"
    assert args.phase621_audit_csv.endswith("historical_amendment_duplicate_audit_phase621_v321.csv")
