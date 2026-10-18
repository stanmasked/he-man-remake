"""Read-only CLI for inspecting level metadata inside a locally supplied IPA."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from .lvl import LevelFormatError, parse_level_header

def audit_ipa(ipa: Path, screen: str = "screen-med") -> dict:
    if screen not in {"screen-med", "screen-xlarge"}:
        raise ValueError("unsupported screen group")
    prefix = f"Payload/MOTU.app/{screen}/levels/"
    records = []
    with zipfile.ZipFile(ipa, "r") as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith(prefix) or not name.endswith(".lvl"):
                continue
            info = archive.getinfo(name)
            if info.file_size > 8_000_000:
                raise LevelFormatError(f"level exceeds size limit: {name}")
            raw = archive.read(info)
            header = parse_level_header(raw)
            if header.embedded_name != PurePosixPath(name).name:
                raise LevelFormatError(f"embedded name differs from archive name: {name}")
            records.append({
                "name": header.embedded_name,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "header": header.as_dict(),
            })
    return {
        "source": ipa.name, "screen_group": screen, "level_files": len(records),
        "levels": records,
        "note": "Only metadata was parsed; record bodies and game logic were not decoded.",
    }

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local read-only He-Man .lvl header inspector")
    ap.add_argument("--ipa", type=Path, required=True, help="local IPA, never uploaded")
    ap.add_argument("--screen", choices=["screen-med", "screen-xlarge"], default="screen-med")
    ap.add_argument("--out", type=Path, help="optional local JSON report")
    args = ap.parse_args(argv)
    report = audit_ipa(args.ipa, args.screen)
    txt = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(txt, encoding="utf-8")
        print(f"Analysed {report['level_files']} level headers; report: {args.out}")
    else:
        print(txt)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
