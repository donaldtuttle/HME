# Manifest scope

`MANIFEST.sha256` covers tracked release files, including the complete historical snapshot. It excludes itself and Git/runtime/build output. `archive/v2.2.sha256` independently pins the 60 preserved source-commit files. The original archived manifest remains unchanged, including its pre-existing stale README checksum; see `archive/README.md`.

Regenerate the root manifest after any payload change:

```bash
python scripts/update_manifest.py
sha256sum --check MANIFEST.sha256
```

The generator reads the Git index path list plus untracked, non-ignored files. Stage only intended deliverables before committing, and inspect the resulting manifest. Source pins and provenance must also be updated when their target source changes.
