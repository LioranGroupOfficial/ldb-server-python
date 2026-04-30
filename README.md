# liorandb-server-windows

This package installs the **LioranDB Windows portable ZIP** and (optionally) adds the install folder to your PATH.

## Install

```powershell
pip install liorandb-server-windows
```

## One-command setup (recommended)

Installs into `C:\LioranDB-Server`, adds it to **User** PATH, and tells you what to run next:

```powershell
liorandb-server-windows
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
liorandb-server-windows add-to-path --target C:\LioranDB-Server
```

Open a new terminal afterwards.

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
