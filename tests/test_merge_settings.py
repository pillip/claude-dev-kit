import json
from pathlib import Path
import subprocess, sys, tempfile

def test_deep_merge():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        proj = td / "settings.json"
        snip = td / "snippet.json"
        proj.write_text(json.dumps({"a": {"b": 1}, "x": 1}), encoding="utf-8")
        snip.write_text(json.dumps({"a": {"c": 2}, "x": 9, "y": 3}), encoding="utf-8")

        script = Path(__file__).resolve().parents[1] / "scripts" / "merge_settings.py"
        subprocess.check_call([sys.executable, str(script), str(proj), str(snip)])

        out = json.loads(proj.read_text(encoding="utf-8"))
        assert out["a"]["b"] == 1
        assert out["a"]["c"] == 2
        assert out["x"] == 9
        assert out["y"] == 3
