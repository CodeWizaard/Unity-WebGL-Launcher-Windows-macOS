"""Create a portable ZIP and checksum, preserving macOS bundle permissions."""
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    system = "windows" if sys.platform == "win32" else "macos"
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    name = f"Unity-WebGL-Launcher-{system}-{arch}"
    staging = ROOT / "build" / name
    staging.mkdir(parents=True, exist_ok=True)
    for filename in ("LICENSE", "README.md"):
        shutil.copy2(ROOT / filename, staging / filename)
    archive = release / f"{name}.zip"
    if sys.platform == "darwin":
        subprocess.run(["ditto", str(ROOT / "dist" / "Unity WebGL Launcher.app"), str(staging / "Unity WebGL Launcher.app")], check=True)
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(staging), str(archive)], check=True)
    else:
        shutil.copy2(ROOT / "dist" / "Unity WebGL Launcher.exe", staging)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
            for path in staging.rglob("*"):
                if path.is_file():
                    output.write(path, path.relative_to(staging.parent))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()
