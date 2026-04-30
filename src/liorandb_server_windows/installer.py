from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional, Tuple


RELEASE_MANIFEST_URL = "https://db.lioransolutions.com/release.json"
DEFAULT_CHANNEL = "earlyProduction"

DEFAULT_ZIP_URL = "https://github.com/LioranGroupOfficial/Liorandb/releases/download/EarlyProduction/LioranDB-1.1.11.zip"
INSTALL_DIR = os.path.join(os.path.expanduser("~"), ".liorandb")
DEFAULT_TARGET_DIR = INSTALL_DIR


def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_path_for_compare(path: str) -> str:
    try:
        expanded = os.path.expandvars(str(path))
        resolved = str(Path(expanded).expanduser().resolve())
    except Exception:
        expanded = os.path.expandvars(str(path))
        resolved = str(Path(expanded).expanduser())
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


def _read_json_url(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "liorandb-server-windows/0.1.2"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def resolve_latest_zip_url(
    *,
    manifest_url: str = RELEASE_MANIFEST_URL,
    channel: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """
    Returns (version, zip_url). Version may be None if it can't be determined.
    """
    try:
        manifest = _read_json_url(manifest_url)
        channel_name = channel or manifest.get("defaultChannel") or DEFAULT_CHANNEL
        channel_obj = manifest["channels"][channel_name]
        version = channel_obj.get("version")
        zip_url = channel_obj["platforms"]["windows"]["artifacts"]["zip"]["url"]
        return version, zip_url
    except Exception as e:
        print(
            f"Warning: failed to fetch/parse manifest ({manifest_url}); falling back to pinned ZIP. ({e})",
            file=sys.stderr,
        )
        return None, DEFAULT_ZIP_URL


def _install_marker_path(target: Path) -> Path:
    return target / ".liorandb-install.json"


def _read_install_marker(target: Path) -> Optional[dict]:
    marker = _install_marker_path(target)
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_install_marker(target: Path, *, version: Optional[str], zip_url: str) -> None:
    marker = _install_marker_path(target)
    payload = {
        "version": version,
        "zipUrl": zip_url,
        "targetDir": str(target),
    }
    marker.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
    req = urllib.request.Request(url, headers={"User-Agent": "liorandb-server-windows/0.1.2"})
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
    url: Optional[str] = None,
    target_dir: str = DEFAULT_TARGET_DIR,
    path_scope: str = "user",
    manifest_url: Optional[str] = None,
    channel: Optional[str] = None,
    force: bool = False,
    keep_zip: bool = False,
) -> None:
    if not _is_windows():
        raise RuntimeError("This installer is intended for Windows.")

    latest_version, latest_zip_url = resolve_latest_zip_url(
        manifest_url=manifest_url or RELEASE_MANIFEST_URL,
        channel=channel,
    )
    chosen_url = url or latest_zip_url

    target = Path(target_dir)
    if target.exists():
        ldb_serve = _find_ldb_serve(target)
        marker = _read_install_marker(target)
        marker_version = marker.get("version") if isinstance(marker, dict) else None
        marker_url = marker.get("zipUrl") if isinstance(marker, dict) else None

        # If it looks installed and matches the latest we resolved, do not download again.
        already_latest = False
        if ldb_serve and marker_url == chosen_url:
            if latest_version is None:
                already_latest = True
            elif marker_version == latest_version:
                already_latest = True

        if already_latest:
            print(f"Already installed{f' (version {marker_version})' if marker_version else ''} at: {target}")
            if path_scope != "none":
                add_to_path(str(target), scope=path_scope)
                print("Done. Open a new terminal and run: ldb-serve")
                return

            print("Add to User PATH (PowerShell):")
            print(user_path_command_powershell(str(target)))
            print("Then open a new terminal and run: ldb-serve")
            return

        # If we previously installed here (marker present), allow updating in-place without --force.
        if marker and ldb_serve:
            print(f"Updating existing install at: {target}")
            shutil.rmtree(target)
        else:
            if not force:
                raise FileExistsError(
                    f"Target folder already exists: {target}. Use --force to overwrite, or choose a different --target."
                )
            shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="liorandb-server-windows-") as td:
        tmp_dir = Path(td)
        zip_path = tmp_dir / "LioranDB.zip"
        print(f"Downloading: {chosen_url}")
        _download(chosen_url, zip_path)

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
            name = Path(chosen_url).name or "LioranDB.zip"
            shutil.copy2(zip_path, target / name)

    _write_install_marker(target, version=latest_version, zip_url=chosen_url)

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
