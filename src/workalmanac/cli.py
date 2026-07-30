import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from workalmanac.app import WorkAlmanac, create_app
from workalmanac.services.automation.models import AutoSyncSettings
from workalmanac.services.curators.models import ContentAccess
from workalmanac.services.diagnostics.models import DiagnosticStatus
from workalmanac.services.sessions.models import AgentProvider
from workalmanac.services.synchronization.models import SyncReceipt, SyncStatus
from workalmanac.settings import load_config
from workalmanac.workflows.collect import CollectAgentRecords
from workalmanac.workflows.distill import DistillSessions
from workalmanac.workflows.import_legacy import ImportLegacyAlmanac
from workalmanac.workflows.setup import SetupWorkAlmanac
from workalmanac.workflows.sync import SyncAgentRecords


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
    parser.add_argument(
        "--ollama-url",
        help="Loopback Ollama origin (default: http://127.0.0.1:11434).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Initialize the private Wiki Vault.")
    init.add_argument("path", type=Path)

    setup = commands.add_parser(
        "setup",
        help="Initialize, collect, and optionally install automatic sync.",
    )
    setup.add_argument("path", type=Path)
    setup.add_argument("--auto", action="store_true")
    setup.add_argument("--every", type=int, default=5, metavar="MINUTES")
    add_collection_options(setup)

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

    sync = commands.add_parser(
        "sync",
        help="Run one locked incremental collection and refresh search.",
    )
    add_collection_options(sync)

    auto = commands.add_parser(
        "auto",
        help="Manage automatic Work Almanac collection.",
    )
    auto_commands = auto.add_subparsers(dest="auto_command", required=True)
    auto_install = auto_commands.add_parser(
        "install",
        help="Install periodic collection with the operating-system scheduler.",
    )
    auto_install.add_argument("--every", type=int, default=5, metavar="MINUTES")
    add_collection_options(auto_install)
    auto_commands.add_parser("status", help="Show scheduler and last-sync status.")
    auto_commands.add_parser("remove", help="Remove automatic collection.")

    import_records = commands.add_parser(
        "import",
        help="Import a provider-neutral agent record JSON bundle.",
    )
    import_records.add_argument("path", type=Path)

    migrate = commands.add_parser(
        "migrate-almanac",
        help="Copy a legacy repository .almanac/pages tree for review.",
    )
    migrate.add_argument("path", type=Path)

    distill = commands.add_parser(
        "distill",
        help="Promote selected sessions into durable Wiki knowledge.",
    )
    distill.add_argument("session_ids", nargs="+")
    distill.add_argument("--using", dest="runtime", default="codex")
    distill.add_argument("--model")
    content_access = distill.add_mutually_exclusive_group()
    content_access.add_argument(
        "--allow-local-content",
        action="store_true",
        help="Allow selected session bodies to be sent to a local runtime.",
    )
    content_access.add_argument(
        "--allow-remote-content",
        action="store_true",
        help="Allow selected session event bodies to be sent to the runtime.",
    )

    commands.add_parser("runtimes", help="Check available curator runtimes.")

    doctor = commands.add_parser("doctor", help="Check the local installation.")
    doctor.add_argument("--home", type=Path, default=Path.home())
    doctor.add_argument("--runtimes", action="store_true")

    serve = commands.add_parser("serve", help="Open the local Work Almanac viewer.")
    serve.add_argument("--port", type=int, default=3928)
    serve.add_argument("--no-open", action="store_true")

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
    app = (
        create_app(config)
        if args.ollama_url is None
        else create_app(config, ollama_url=args.ollama_url)
    )
    try:
        return dispatch(args, app)
    except (KeyError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def dispatch(args: argparse.Namespace, app: WorkAlmanac) -> int:
    if args.command == "init":
        path = app.vault.initialize(args.path)
        app.wiki.refresh()
        print(f"Initialized Work Almanac Vault at {path}")
        return 0
    if args.command == "setup":
        result = app.setup.run(
            SetupWorkAlmanac(
                vault_path=args.path,
                home=args.home.expanduser().resolve(),
                providers=tuple(
                    args.providers or (AgentProvider.CODEX, AgentProvider.CLAUDE)
                ),
                include_content=args.include_content,
                auto_interval_minutes=args.every if args.auto else None,
            )
        )
        print(f"Work Almanac ready at {result.vault_path}")
        print_sync_receipt(result.sync)
        if result.automation_installed:
            print(f"Automatic sync installed every {args.every} minute(s).")
        print("Open the Wiki with `wa serve` or Obsidian.")
        return 0
    if args.command == "import":
        app.vault.require_path()
        result = app.import_records.import_file(args.path)
        print(f"Imported {result.session_id}; added {result.events_added} event(s).")
        print(result.wiki_path)
        return 0
    if args.command == "migrate-almanac":
        app.vault.require_path()
        receipt = app.import_legacy.run(ImportLegacyAlmanac(source=args.path))
        print(
            f"Imported {receipt.files_copied} legacy page(s); "
            f"{receipt.files_unchanged} unchanged."
        )
        print(receipt.target.as_posix())
        return 0
    if args.command == "distill":
        app.vault.require_path()
        receipt = app.distill.run(
            DistillSessions(
                session_ids=tuple(args.session_ids),
                runtime=args.runtime,
                model=args.model,
                content_access=distill_content_access(args),
            )
        )
        print(f"Distill {receipt.run_id}: {receipt.status.value}")
        if receipt.changed_files:
            for path in receipt.changed_files:
                print(path.as_posix())
        else:
            print("No durable Wiki pages changed.")
        return 0
    if args.command == "runtimes":
        for readiness in app.curators.readiness():
            status = "ready" if readiness.available else "unavailable"
            print(f"{readiness.runtime:<8} {status:<11} {readiness.message}")
            if readiness.repair:
                print(f"                     {readiness.repair}")
        return 0
    if args.command == "doctor":
        checks = app.diagnostics.run(
            args.home.expanduser().resolve(),
            include_runtimes=args.runtimes,
        )
        for check in checks:
            print(f"{check.status.value:<7} {check.name:<20} {check.message}")
        return int(any(check.status is DiagnosticStatus.ERROR for check in checks))
    if args.command == "serve":
        app.vault.require_path()
        app.wiki.refresh()
        from workalmanac.viewer.runner import serve_viewer

        serve_viewer(
            app,
            port=args.port,
            open_browser=not args.no_open,
        )
        return 0
    if args.command == "sync":
        app.vault.require_path()
        receipt = app.sync.run(sync_request(args))
        print_sync_receipt(receipt)
        return 0 if receipt.status is not SyncStatus.FAILED else 1
    if args.command == "auto":
        return dispatch_auto(args, app)
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
        app.wiki.refresh()
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


def add_collection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from",
        dest="providers",
        action="append",
        choices=(AgentProvider.CODEX, AgentProvider.CLAUDE),
        help="Agent provider to collect. Repeat to select more than one.",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Retain transcript bodies in private local state and Wiki.",
    )
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="Home directory containing provider session stores.",
    )


def distill_content_access(args: argparse.Namespace) -> ContentAccess:
    if args.allow_local_content:
        return ContentAccess.SELECTED_LOCAL
    if args.allow_remote_content:
        return ContentAccess.SELECTED_REMOTE
    return ContentAccess.METADATA_ONLY


def sync_request(args: argparse.Namespace) -> SyncAgentRecords:
    return SyncAgentRecords(
        providers=tuple(args.providers or (AgentProvider.CODEX, AgentProvider.CLAUDE)),
        home=args.home.expanduser().resolve(),
        include_content=args.include_content,
    )


def dispatch_auto(args: argparse.Namespace, app: WorkAlmanac) -> int:
    if args.auto_command == "install":
        app.vault.require_path()
        settings = AutoSyncSettings(
            interval_minutes=args.every,
            providers=tuple(
                args.providers or (AgentProvider.CODEX, AgentProvider.CLAUDE)
            ),
            home=args.home.expanduser().resolve(),
            include_content=args.include_content,
        )
        status = app.automation.install(settings)
        print(status.message)
        return 0
    if args.auto_command == "status":
        status = app.automation.status()
        print(status.message)
        latest = app.synchronization.latest()
        if latest is None:
            print("No sync has run yet.")
        else:
            print_sync_receipt(latest)
        return 0
    if args.auto_command == "remove":
        app.automation.remove()
        print("Automatic Work Almanac collection removed.")
        return 0
    raise ValueError(f"unsupported auto command: {args.auto_command}")


def print_sync_receipt(receipt: SyncReceipt) -> None:
    status = receipt.status.value
    print(
        f"Sync {receipt.run_id}: {status}; "
        f"{receipt.sessions_discovered} session(s), "
        f"{receipt.events_added} new event(s)."
    )
    if receipt.error_type is not None:
        print(f"Failure type: {receipt.error_type}")


if __name__ == "__main__":
    raise SystemExit(main())
