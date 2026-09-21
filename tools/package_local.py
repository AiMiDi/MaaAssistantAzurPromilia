"""Assemble local MFAAvalonia UI using the same native runtime as the agent."""
import shutil
import filecmp
import json
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
    # MFA 2.16.1 runs pretasks from resource/base instead of the PI directory.
    # Absolute paths also work with clients that follow the PI CWD convention.
    (destination / "resource/base").mkdir(parents=True, exist_ok=True)
    interface_path = destination / "interface.json"
    interface = json.loads(interface_path.read_text(encoding="utf-8"))
    if "pretask" in interface:
        interface["pretask"]["exec"] = str(ROOT / ".venv/Scripts/python.exe")
        interface["pretask"]["args"] = ["-X", "utf8", str(destination / "agent/launcher.py")]
        interface_path.write_text(json.dumps(interface, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
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
