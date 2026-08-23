import argparse

from src.cli.release_parsers import register_release_parsers


def test_release_parsers_register_all_commands():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    register_release_parsers(sub)

    assert len(sub.choices) == 15
    args = parser.parse_args(["build-final-release-bundle-v321"])
    assert args.command == "build-final-release-bundle-v321"
    assert args.bundle_zip.endswith("stock-analytics-v321-final-release-bundle-20260818.zip")
