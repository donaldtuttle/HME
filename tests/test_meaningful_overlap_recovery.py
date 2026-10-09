"""Exercise the proposed protocol's guard through the complete runner."""
import json

import pytest

from experiments.meaningful_overlap_v1 import dataset, evaluate


@pytest.mark.parametrize("commit,approval", [(None, None), ("a" * 40, "unused.json")])
def test_proposed_runner_cannot_generate_reserved_corpora(tmp_path, monkeypatch, commit, approval):
    def forbidden(*args, **kwargs):
        pytest.fail("Proposed confirmatory run reached data generation")

    monkeypatch.setattr(dataset, "rng", forbidden)
    monkeypatch.setattr(evaluate, "one_corpus", forbidden)
    out = tmp_path / "blocked-run"
    with pytest.raises(PermissionError, match="DESIGN / DEVELOP"):
        evaluate.run("confirmatory", out, commit, approval)
    assert not list(out.glob("corpus_*"))
    assert not (out / "RUN_MANIFEST.json").exists()
    assert not (out / "summary.json").exists()
    assert "DESIGN / DEVELOP" in json.loads((out / "FAILURE.json").read_text())["error"]
