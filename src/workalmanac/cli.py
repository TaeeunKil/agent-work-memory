import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from workalmanac.app import WorkAlmanac, create_app
from workalmanac.services.sessions.models import AgentProvider
from workalmanac.settings import load_config
from workalmanac.workflows.collect import CollectAgentRecords


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wa",
        description="Keep agent work records in a private personal Wiki.",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        help="Override the local Work Almanac state directory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Initialize the private Wiki Vault.")
    init.add_argument("path", type=Path)

    note = commands.add_parser("note", help="Save a manual work note.")
    note.add_argument("text")
    note.add_argument("--title")
    note.add_argument("--cwd", type=Path)

    collect = commands.add_parser(
        "collect",
        help="Discover agent sessions and optionally retain their content.",
    )
    collect.add_argument(
        "--from",
        dest="providers",
        action="append",
        choices=(AgentProvider.CODEX, AgentProvider.CLAUDE),
        help="Agent provider to collect. Repeat to select more than one.",
    )
    collect.add_argument(
        "--include-content",
        action="store_true",
        help=(
            "Copy transcript content into private state and Wiki; "
            "it may contain sensitive text."
        ),
    )
    collect.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Home directory containing provider session stores.",
    )

    import_records = commands.add_parser(
        "import",
        help="Import a provider-neutral agent record JSON bundle.",
    )
    import_records.add_argument("path", type=Path)

    commands.add_parser("sessions", help="List retained agent sessions.")

    show = commands.add_parser("show", help="Show one retained session.")
    show.add_argument("session_id")

    search = commands.add_parser("search", help="Search sessions and Wiki Markdown.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.state_dir)
    app = create_app(config)
    try:
        return dispatch(args, app)
    except (KeyError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def dispatch(args: argparse.Namespace, app: WorkAlmanac) -> int:
    if args.command == "init":
        path = app.vault.initialize(args.path)
        print(f"Initialized Work Almanac Vault at {path}")
        return 0
    if args.command == "import":
        app.vault.require_path()
        result = app.import_records.import_file(args.path)
        print(f"Imported {result.session_id}; added {result.events_added} event(s).")
        print(result.wiki_path)
        return 0
    if args.command == "note":
        app.vault.require_path()
        session = app.sessions.add_manual_note(
            args.text,
            title=args.title,
            cwd=args.cwd,
        )
        page = app.vault.refresh_session(
            session,
            app.sessions.events(session.session_id),
        )
        print(f"Saved {session.session_id}")
        print(page)
        return 0
    if args.command == "collect":
        app.vault.require_path()
        selected = args.providers or [
            AgentProvider.CODEX,
            AgentProvider.CLAUDE,
        ]
        receipt = app.collect.collect(
            CollectAgentRecords(
                providers=tuple(selected),
                home=args.home.expanduser().resolve(),
                include_content=args.include_content,
            )
        )
        print(
            f"Discovered {receipt.sessions_discovered} session(s); "
            f"added {receipt.events_added} event(s)."
        )
        if args.include_content:
            print("Content retained locally; review the private Wiki before sharing.")
        else:
            print("Metadata only. Use --include-content to retain transcript bodies.")
        return 0
    if args.command == "sessions":
        for session in app.sessions.list():
            captured = "content" if session.content_captured else "metadata"
            print(
                f"{session.session_id}  {session.provider:<6}  "
                f"{captured:<8}  {session.title}"
            )
        return 0
    if args.command == "show":
        session = app.sessions.get(args.session_id)
        print(f"{session.title} [{session.provider}]")
        if session.cwd is not None:
            print(f"workspace: {session.cwd}")
        for event in app.sessions.events(session.session_id):
            print(f"\n[{event.kind.value}] {event.label}")
            print(event.content)
        return 0
    if args.command == "search":
        for result in app.search.find(args.query, args.limit):
            print(f"{result.kind:<7} {result.identity}  {result.title}")
            if result.excerpt:
                print(f"        {result.excerpt}")
        return 0
    raise ValueError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
