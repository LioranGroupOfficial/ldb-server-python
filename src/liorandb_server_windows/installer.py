from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional


DEFAULT_ZIP_URL = "https://github.com/LioranGroupOfficial/Liorandb/releases/download/EarlyProduction/LioranDB-1.1.11.zip"
DEFAULT_TARGET_DIR = r"C:\LioranDB-Server"


def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_path_for_compare(path: str) -> str:
    try:
        resolved = str(Path(path).expanduser().resolve())
    except Exception:
        resolved = str(Path(path).expanduser())
    return os.path.normcase(os.path.normpath(resolved)).rstrip("\\/")


def _path_contains(path_value: str, folder: str) -> bool:
    folder_norm = _normalize_path_for_compare(folder)
    parts = [p for p in path_value.split(os.pathsep) if p.strip()]
    for part in parts:
        if _normalize_path_for_compare(part) == folder_norm:
            return True
    return False


def add_to_path(folder: str, scope: str = "user") -> None:
    folder = str(Path(folder))
    if scope not in {"user", "machine", "process"}:
        raise ValueError("scope must be one of: user, machine, process")

    if not _is_windows():
        raise RuntimeError("PATH installation is only supported on Windows.")

    if scope == "process":
        current = os.environ.get("PATH", "")
        if _path_contains(current, folder):
            print("PATH already contains the folder (process scope).")
            return
        os.environ["PATH"] = current + (os.pathsep if current else "") + folder
        print("Added to PATH for the current process.")
        return

    # Persistent PATH update on Windows via registry
    import winreg  # noqa: PLC0415

    hive = winreg.HKEY_CURRENT_USER if scope == "user" else winreg.HKEY_LOCAL_MACHINE
    subkey = r"Environment" if scope == "user" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

    access = winreg.KEY_READ | winreg.KEY_SET_VALUE
    try:
        key = winreg.OpenKey(hive, subkey, 0, access)
    except PermissionError as e:
        raise PermissionError(
            "Insufficient permissions to update PATH. Try --path-scope user, or run an elevated shell for machine scope."
        ) from e

    try:
        try:
            current_value, value_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current_value, value_type = ("", winreg.REG_EXPAND_SZ)

        current_value = current_value or ""
        if _path_contains(current_value, folder):
            print(f"PATH already contains the folder ({scope} scope).")
            return

        new_value = current_value + (";" if current_value and not current_value.endswith(";") else "") + folder
        winreg.SetValueEx(key, "Path", 0, value_type, new_value)
    finally:
        winreg.CloseKey(key)

    print(f"Added to PATH ({scope} scope). Open a new terminal to refresh PATH.")


def user_path_command_powershell(folder: str) -> str:
    folder = str(Path(folder))
    # Duplicate-safe append to User PATH.
    return (
        "$dir = '{dir}'; "
        "$p = [Environment]::GetEnvironmentVariable('Path', 'User'); "
        "if (-not ($p -split ';' | Where-Object {{ $_.TrimEnd('\\\\') -ieq $dir.TrimEnd('\\\\') }})) "
        "{{ [Environment]::SetEnvironmentVariable('Path', ($p + ';' + $dir), 'User') }}"
    ).format(dir=folder.replace("'", "''"))


def _safe_extract(zip_path: Path, dest: Path) -> None:
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = dest / member.filename
            # prevent Zip Slip
            try:
                member_resolved = member_path.resolve()
            except Exception:
                member_resolved = (dest / Path(member.filename).name).resolve()
            if not str(member_resolved).startswith(str(dest) + os.sep) and member_resolved != dest:
                raise RuntimeError(f"Unsafe path in zip: {member.filename}")
        zf.extractall(dest)


def _download(url: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "liorandb-server-windows/0.1.0"})
    with urllib.request.urlopen(req) as resp, open(out_path, "wb") as f:
        total = resp.headers.get("Content-Length")
        total_bytes = int(total) if total and total.isdigit() else None
        downloaded = 0
        chunk = 1024 * 256
        while True:
            data = resp.read(chunk)
            if not data:
                break
            f.write(data)
            downloaded += len(data)
            if total_bytes:
                pct = int(downloaded * 100 / total_bytes)
                print(f"\rDownloading... {pct}%", end="", file=sys.stderr)
        if total_bytes:
            print("", file=sys.stderr)


def _find_ldb_serve(root: Path) -> Optional[Path]:
    candidates = [
        root / "ldb-serve.exe",
        root / "ldb-serve",
        root / "bin" / "ldb-serve.exe",
        root / "bin" / "ldb-serve",
    ]
    for c in candidates:
        if c.exists():
            return c
    # fallback: search shallowly
    for c in root.rglob("ldb-serve.exe"):
        return c
    for c in root.rglob("ldb-serve"):
        return c
    return None


def install(
    *,
    url: str = DEFAULT_ZIP_URL,
    target_dir: str = DEFAULT_TARGET_DIR,
    path_scope: str = "user",
    force: bool = False,
    keep_zip: bool = False,
) -> None:
    if not _is_windows():
        raise RuntimeError("This installer is intended for Windows.")

    target = Path(target_dir)
    if target.exists():
        if not force:
            raise FileExistsError(f"Target folder already exists: {target}. Use --force to overwrite.")
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="liorandb-server-windows-") as td:
        tmp_dir = Path(td)
        zip_path = tmp_dir / "LioranDB.zip"
        print(f"Downloading: {url}")
        _download(url, zip_path)

        extract_dir = tmp_dir / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        print("Extracting ZIP...")
        _safe_extract(zip_path, extract_dir)

        # If the ZIP contains a single top-level folder, install its contents into target.
        children = [p for p in extract_dir.iterdir()]
        if len(children) == 1 and children[0].is_dir():
            source_root = children[0]
        else:
            source_root = extract_dir

        print(f"Installing to: {target}")
        shutil.copytree(source_root, target)

        if keep_zip:
            shutil.copy2(zip_path, target / Path(url).name)

    ldb_serve = _find_ldb_serve(target)
    if not ldb_serve:
        print(
            "Warning: could not find 'ldb-serve' in the install folder. The ZIP layout may have changed.",
            file=sys.stderr,
        )
    else:
        print(f"Found: {ldb_serve}")

    if path_scope != "none":
        add_to_path(str(target), scope=path_scope)
        print("Done. Open a new terminal and run: ldb-serve")
        return

    print("Add to User PATH (PowerShell):")
    print(user_path_command_powershell(str(target)))
    print("Then open a new terminal and run: ldb-serve")
