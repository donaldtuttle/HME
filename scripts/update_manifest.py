"""Regenerate the repository payload manifest without traversing ignored output."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT,
).decode().split("\0")
entries = []
for name in sorted(set(paths)):
    path = ROOT / name
    if not name or name == "MANIFEST.sha256" or not path.is_file():
        continue
    entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}\n")
(ROOT / "MANIFEST.sha256").write_text("".join(entries), encoding="utf-8")
print(f"Pinned {len(entries)} files")
