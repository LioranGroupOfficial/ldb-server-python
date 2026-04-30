# liorandb-server-windows

This package installs the **LioranDB Windows portable ZIP** and (optionally) adds the install folder to your PATH.

It resolves the **latest Windows ZIP** from `https://db.lioransolutions.com/release.json` (default channel), and will **not download again** if the latest version is already installed in the target folder.

## Install

```powershell
py -m pip install liorandb-server-windows
```

## One-command setup (recommended)

Installs into `%USERPROFILE%\.liorandb`, adds it to **User** PATH, and tells you what to run next:

```powershell
liorandb-server-windows
```

If that command is not found (your Python Scripts folder isn’t on PATH), run:

```powershell
py -m liorandb_server_windows
```

Open a **new terminal**, then run:

```powershell
ldb-serve
```

## Add to PATH manually (PowerShell)

Avoids adding duplicates:

```powershell
$dir = 'C:\LioranDB-Server'
$p = [Environment]::GetEnvironmentVariable('Path', 'User')
if (-not ($p -split ';' | Where-Object { $_.TrimEnd('\') -ieq $dir.TrimEnd('\') })) {
  [Environment]::SetEnvironmentVariable('Path', ($p + ';' + $dir), 'User')
}
```

Or via this package:

```powershell
liorandb-server-windows add-to-path --target $env:USERPROFILE\.liorandb
```

Open a new terminal afterwards.

## Fix “command not found” for `liorandb-server-windows`

Add Python’s Scripts directory to **User** PATH:

```powershell
$scripts = py -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$p = [Environment]::GetEnvironmentVariable('Path','User')
if (-not ($p -split ';' | Where-Object { $_.TrimEnd('\') -ieq $scripts.TrimEnd('\') })) {
  [Environment]::SetEnvironmentVariable('Path', ($p + ';' + $scripts), 'User')
}
```

## CLI help

```powershell
liorandb-server-windows --help
liorandb-server-windows install --help
```

To auto-add to PATH instead of printing a command:

```powershell
liorandb-server-windows install --path-scope user
```

To only print a command (no PATH changes):

```powershell
liorandb-server-windows install --path-scope none
```
