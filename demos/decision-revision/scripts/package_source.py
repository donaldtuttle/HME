"""Build the core download from current source, with deterministic ZIP metadata."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

DEMO = Path(__file__).resolve().parents[1]
ROOT = DEMO.parents[1]
SOURCE = ROOT / 'experiments' / 'decision_revision_v1'
OUTPUT = DEMO / 'public' / 'decision_revision_v1.zip'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with ZipFile(OUTPUT, 'w', compression=ZIP_DEFLATED) as archive:
    for path in sorted(SOURCE.iterdir()):
        if not path.is_file() or path.suffix not in {'.ts', '.md', '.json'}:
            continue
        info = ZipInfo(path.relative_to(ROOT).as_posix(), (2026, 10, 2, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, path.read_bytes())
print(f'Packaged {OUTPUT.name}')
