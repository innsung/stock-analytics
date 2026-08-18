from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

RESEARCH_SEEN_THROUGH = "20260709"

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def create_result_bundle_v321(*, output_prefix: str, result_dir: str | None = None,
                              zip_results: bool = True, minimum_files: int = 1) -> dict:
    """Collect one diagnostic run into an isolated folder and optionally ZIP it.

    output_prefix may already include a directory. If result_dir is supplied,
    diagnostics are expected to have been written there. Only files sharing
    the exact prefix basename are bundled, preventing accidental mixing of
    prior runs.
    """
    prefix_path = Path(output_prefix)
    base = prefix_path.name
    source_dir = prefix_path.parent if str(prefix_path.parent) != "." else Path(".")
    target = Path(result_dir) if result_dir else source_dir
    target.mkdir(parents=True, exist_ok=True)

    # If diagnostics were written outside target, copy only this run's files.
    candidates = sorted(source_dir.glob(base + "*"))
    copied = []
    for src in candidates:
        if not src.is_file() or src.suffix.lower() == ".zip":
            continue
        dst = target / src.name
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        copied.append(dst)

    # If run already wrote directly into target, discover there.
    if not copied:
        copied = [p for p in sorted(target.glob(base + "*"))
                  if p.is_file() and p.suffix.lower() != ".zip"]

    if len(copied) < int(minimum_files):
        raise RuntimeError(
            f"결과 번들 검증 실패: 예상 최소 {minimum_files}개 파일, 실제 {len(copied)}개. "
            f"output_prefix={output_prefix}, result_dir={target}"
        )

    manifest = {
        "phase": "V3.2.1 Phase 5 - isolated research result bundle",
        "created_at": datetime.now().astimezone().isoformat(),
        "research_seen_through": RESEARCH_SEEN_THROUGH,
        "output_prefix": base,
        "file_count": len(copied),
        "files": [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)}
            for p in copied
        ],
        "safety": {
            "research_only": True,
            "live_orders_blocked": True,
            "credentials_included": False,
        },
    }
    manifest_path = target / f"{base}_bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    zip_path = None
    if zip_results:
        zip_path = target.parent / f"{target.name}.zip"
        tmp = zip_path.with_suffix(".zip.tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(target.iterdir()):
                if p.is_file():
                    z.write(p, arcname=f"{target.name}/{p.name}")
        tmp.replace(zip_path)

    return {
        "result_dir": str(target),
        "zip_path": str(zip_path) if zip_path else "",
        "file_count": len(copied),
        "manifest": str(manifest_path),
    }
