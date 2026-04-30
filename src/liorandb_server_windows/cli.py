from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .installer import (
    DEFAULT_TARGET_DIR,
    add_to_path,
    install,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="liorandb-server-windows",
        description="Install the LioranDB Windows portable server ZIP and manage PATH.",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    p_install = sub.add_parser("install", help="Download and install LioranDB server.")
    p_install.add_argument(
        "--url",
        default=None,
        help="Override ZIP download URL (normally resolved from the release manifest).",
    )
    p_install.add_argument(
        "--manifest-url",
        default=None,
        help="Release manifest URL (default: https://db.lioransolutions.com/release.json).",
    )
    p_install.add_argument(
        "--channel",
        default=None,
        help="Release channel (default: manifest defaultChannel).",
    )
    p_install.add_argument(
        "--target",
        default=DEFAULT_TARGET_DIR,
        help=r"Install folder (default: %USERPROFILE%\.liorandb).",
    )
    p_install.add_argument(
        "--path-scope",
        choices=("user", "machine", "process", "none"),
        default="user",
        help="Where to add PATH entry (default: user). Use 'none' to only print a PowerShell command.",
    )
    p_install.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing target folder if it exists.",
    )
    p_install.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the downloaded ZIP in the target folder.",
    )

    p_path = sub.add_parser("add-to-path", help="Add an existing install folder to PATH.")
    p_path.add_argument(
        "--target",
        default=DEFAULT_TARGET_DIR,
        help=r"Folder to add to PATH (default: C:\LioranDB-Server).",
    )
    p_path.add_argument(
        "--path-scope",
        choices=("user", "machine", "process"),
        default="user",
        help="Where to add PATH entry (default: user).",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Convenience: running with no args performs a default install and prints PATH command.
    if not argv:
        install(path_scope="user")
        return 0

    args = _build_parser().parse_args(argv)

    if args.command == "install":
        install(
            url=args.url,
            target_dir=args.target,
            path_scope=args.path_scope,
            manifest_url=args.manifest_url or None,
            channel=args.channel or None,
            force=args.force,
            keep_zip=args.keep_zip,
        )
        return 0

    if args.command == "add-to-path":
        add_to_path(args.target, scope=args.path_scope)
        return 0

    _build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
