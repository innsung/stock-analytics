"""Run daily-shadow while teeing output to a persistent scheduler log."""

from datetime import datetime
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "daily_shadow.log"

command = [
    sys.executable, "-m", "src.main", "daily-shadow",
    "--universe-csv", "config/universe_kr_24.example.csv",
    "--portfolio-id", "shadow_24_filtered", "--benchmark-code", "069500",
    "--capital", "100000000", "--top-n", "12", "--rebalance-band", "0.02",
    "--min-order", "500000", "--stock-cap", "0.10", "--sector-cap", "0.25",
    "--min-liquidity", "1000000000", "--output-prefix", "shadow_24_filtered",
]

with LOG_PATH.open("a", encoding="utf-8") as log:
    heading = f"\n===== {datetime.now().astimezone().isoformat()} =====\n"
    print(heading, end="")
    log.write(heading)
    process = subprocess.Popen(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        log.write(line)
        log.flush()
    exit_code = process.wait()
    ending = f"===== exit_code={exit_code} =====\n"
    print(ending, end="")
    log.write(ending)

raise SystemExit(exit_code)
