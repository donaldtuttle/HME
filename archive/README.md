# Historical snapshot

`v2.2/` preserves all 60 tracked files from commit `db01a9ffb9b618db74c974fe630c143110400b2d` byte-for-byte. This includes the old QOFT/QOSMOS integrations, governance, skill, source pins, experiments, and evidence. Its documents describe that historical version, not the active HME 3 contract.

The archive is excluded from the installed HME 3 module. To reproduce historical behavior from the repository root:

```bash
python -m pip install -e ".[legacy-test]"
sha256sum --check archive/v2.2.sha256
cd archive/v2.2
sha256sum --check SOURCE_PINS.sha256
python qosmos_hme_engine.py --self-test
python -m pytest -q
python integrations/sfd_to_hme_bridge.py --output outputs/sfd_hme_bridge.json
```

The archive's original experiment-specific pins remain in force. No historical result is relabeled as a new-schema result. The repository license applies throughout.

The original `MANIFEST.sha256` already contains a stale checksum for its README at the preserved source commit. That historical manifest is retained unchanged. `archive/v2.2.sha256` pins all 60 actual files from that commit and is verified from the repository root; it does not pretend to repair the historical manifest.
