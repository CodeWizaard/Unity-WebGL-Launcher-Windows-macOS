"""Build on the target OS: python scripts/build.py."""
from pathlib import Path
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = "Unity WebGL Launcher"


def main():
    if sys.platform not in ("win32", "darwin"):
        raise SystemExit("Desktop packages are supported on Windows and macOS.")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", NAME]
    assets = ROOT / "unity_webgl_launcher" / "assets"
    for filename in ("launcher.ico", "launcher.png"):
        args += ["--add-data", f"{assets / filename}{os.pathsep}unity_webgl_launcher/assets"]
    if sys.platform == "win32":
        args += ["--onefile", "--icon", str(assets / "launcher.ico"), "--version-file", str(ROOT / "scripts" / "windows-version.txt")]
    else:
        args += ["--onedir", "--osx-bundle-identifier", "io.github.codewizaard.unitywebgllauncher"]
    args += ["launcher.py"]
    subprocess.run(args, cwd=ROOT, check=True)
    print(f"Built for {sys.platform}/{platform.machine()} in {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
