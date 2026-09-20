"""Assemble local MFAAvalonia UI using the same native runtime as the agent."""
import shutil
import filecmp
from pathlib import Path
import maa

ROOT = Path(__file__).resolve().parents[1]

def main():
    destination = ROOT / "install"
    if not (destination / "MFAAvalonia.exe").is_file():
        raise SystemExit("Run setup.ps1 first to download MFAAvalonia.")
    shutil.copytree(ROOT / "assets/resource", destination / "resource", dirs_exist_ok=True)
    shutil.copytree(ROOT / "agent", destination / "agent", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "my_action.py", "my_reco.py"))
    for name in ("interface.json", "welcome.md"):
        shutil.copy2(ROOT / "assets" / name, destination / name)
    shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")
    binaries = Path(maa.__file__).parent / "bin"
    native = destination / "runtimes/win-x64/native"
    native.mkdir(parents=True, exist_ok=True)
    for path in binaries.glob("*.dll"):
        target = native / path.name
        if not target.exists() or not filecmp.cmp(path, target, shallow=False):
            shutil.copy2(path, target)
    if (binaries / "plugins").exists():
        shutil.copytree(binaries / "plugins", destination / "plugins/win-x64", dirs_exist_ok=True)
    print(f"Ready: {destination / 'MFAAvalonia.exe'}")

if __name__ == "__main__":
    main()
