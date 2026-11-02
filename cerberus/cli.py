"""CLI for scripts, integrations and GUI-independent recovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .vault import CaptureError, Vault


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cerberus", description="Cerberus local memory vault")
    p.add_argument("--vault", type=Path, help="Use a custom local data directory")
    cmds = p.add_subparsers(dest="command", required=True)
    t = cmds.add_parser("add-text", help="Store text")
    t.add_argument("text")
    t.add_argument("--title")
    u = cmds.add_parser("add-url", help="Store a URL")
    u.add_argument("url")
    u.add_argument("--title")
    f = cmds.add_parser("add-file", help="Copy a file into the vault")
    f.add_argument("path", type=Path)
    for name in ("list", "search"):
        cmd = cmds.add_parser(name)
        if name == "search":
            cmd.add_argument("query")
        cmd.add_argument("--limit", type=int, default=50)
    d = cmds.add_parser("delete", help="Delete captured item by ID")
    d.add_argument("id", type=int)
    e = cmds.add_parser("export", help="Export text/URLs and file metadata to JSON")
    e.add_argument("destination", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        with Vault(args.vault) as vault:
            if args.command == "add-text":
                result = vault.add_text(args.text, title=args.title)
            elif args.command == "add-url":
                result = vault.add_url(args.url, title=args.title)
            elif args.command == "add-file":
                result = vault.add_file(args.path)
            elif args.command == "list":
                result = vault.list(limit=args.limit)
            elif args.command == "search":
                result = vault.search(args.query, limit=args.limit)
            elif args.command == "delete":
                result = {"deleted": vault.delete(args.id)}
            else:
                result = {"exported_to": str(vault.export_json(args.destination))}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CaptureError, OSError, ValueError) as exc:
        parser().exit(2, f"Error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
