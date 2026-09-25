"""Direct-script regression checks without an editable install or PYTHONPATH."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["tests/hme_independent_audit.py", "examples/runtime_demo.py"])
def test_script_works_from_unrelated_directory_without_install(tmp_path, script):
    checkout = tmp_path / "source"
    (checkout / Path(script).parent).mkdir(parents=True)
    for name in ("hme_engine.py", "hme_runtime.py", "hme_dynamics.py", script):
        shutil.copy2(ROOT / name, checkout / name)
    command = [sys.executable, "-I", str(checkout / script)]
    if script.startswith("tests/"):
        command += ["--memories", "3", "--noise", "0", "--output", str(tmp_path / "audit.json")]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    if script.startswith("examples/"):
        assert data["ticks"] == 16
        assert data["score_is_calibrated"] is False
    else:
        assert (tmp_path / "audit.json").is_file()
        assert str(checkout / "hme_engine.py") in result.stdout
