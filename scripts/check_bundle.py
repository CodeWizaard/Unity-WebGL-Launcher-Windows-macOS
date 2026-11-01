"""Launch the real packaged executable and require a successful smoke report."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    executable = ROOT / "dist" / "Unity WebGL Launcher.exe"
    if sys.platform == "darwin":
        executable = ROOT / "dist" / "Unity WebGL Launcher.app" / "Contents" / "MacOS" / "Unity WebGL Launcher"
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "smoke.json"
        completed = subprocess.run([str(executable), "--smoke-test", str(report)], timeout=60)
        if not report.exists():
            raise SystemExit(f"Packaged app did not produce a smoke report (exit {completed.returncode})")
        result = json.loads(report.read_text(encoding="utf-8"))
        print(json.dumps(result, indent=2))
        if completed.returncode != 0 or not result.get("ok"):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
