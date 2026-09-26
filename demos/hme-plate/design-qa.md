# HME Plate design QA

Final result: **blocked** (rendered local-browser verification).

The source is the updated https://hme-plate.grok.me/ application captured on
2026-09-26; resource hashes and recovery details are in [SOURCE.md](SOURCE.md).
The source was inspected in a browser, including reset after disabling Hann,
probe threshold changes, and an all-zero decoded vector after dropping the
ledger. Those observations concern the source, not the local port.

The local preview attempt failed with `sites-previewd mailbox is unavailable
at /tmp/sites-previewd/requests`. No rendered local screenshots were obtained.
Build and jsdom interaction checks cannot substitute for browser rendering.

| Surface | Current evidence | Remaining browser check |
| --- | --- | --- |
| Desktop composition and typography | Original CSS and locally bundled source fonts | Compare local screenshot with source at matching viewport |
| Field magnitude/phase canvas | Numeric field parity; DOM control regression | Confirm canvas drawing, pointer placement and resize behavior |
| Retrieval, score mix and decoded surface | Scores, decoding and magnitude parity; DOM state checks | Confirm chart geometry, labels and visual zero state |
| Ledger and write controls | Numeric/symbol writes and reset pass DOM checks | Confirm scrolling, focus visibility and keyboard interaction |
| Mobile layout | Original responsive CSS retained | Check narrow viewport, overflow, touch targets and field sizing |

Keep the PR draft until desktop and mobile browser checks are completed.
No deployment or visual-fidelity signoff is claimed.
