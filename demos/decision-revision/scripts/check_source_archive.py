"""Require the built download to contain exactly the current core source bytes."""
from pathlib import Path
from zipfile import ZipFile

DEMO = Path(__file__).resolve().parents[1]
ROOT = DEMO.parents[1]
SOURCE = ROOT / 'experiments' / 'decision_revision_v1'
expected = {
    p.relative_to(ROOT).as_posix(): p.read_bytes()
    for p in SOURCE.iterdir()
    if p.is_file() and p.suffix in {'.ts', '.md', '.json'}
}
with ZipFile(DEMO / 'dist/client/decision_revision_v1.zip') as archive:
    assert len(archive.namelist()) == len(expected), 'Unexpected archive entry count'
    assert set(archive.namelist()) == set(expected), 'Unexpected archive paths'
    for name, data in expected.items():
        assert archive.read(name) == data, f'Stale download: {name}'
print(f'Source archive: {len(expected)} files match the current core byte-for-byte')
