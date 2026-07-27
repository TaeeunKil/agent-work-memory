import re
from pathlib import Path

from workalmanac.database import open_database
from workalmanac.services.sessions.models import SearchResult
from workalmanac.services.sessions.service import SessionsService
from workalmanac.services.vault.service import VaultService


class SearchService:
    def __init__(
        self,
        database_path: Path,
        sessions: SessionsService,
        vault: VaultService,
    ):
        self.database_path = database_path
        self.sessions = sessions
        self.vault = vault

    def find(self, query: str, limit: int = 20) -> tuple[SearchResult, ...]:
        terms = query_terms(query)
        if not terms:
            return ()
        self.refresh()
        with open_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                  kind,
                  identity,
                  title,
                  snippet(search_documents, 3, '[', ']', ' ... ', 24) AS excerpt
                FROM search_documents
                WHERE search_documents MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query(terms), limit),
            ).fetchall()
        return tuple(
            SearchResult(
                kind=row["kind"],
                identity=row["identity"],
                title=row["title"],
                excerpt=row["excerpt"],
            )
            for row in rows
        )

    def refresh(self) -> None:
        documents: list[tuple[str, str, str, str]] = []
        for session in self.sessions.list():
            events = self.sessions.events(session.session_id)
            body = "\n".join(event.content for event in events)
            documents.append(("session", session.session_id, session.title, body))
        vault_path = self.vault.require_path()
        for path in self.vault.markdown_files():
            relative = path.relative_to(vault_path).as_posix()
            raw = path.read_text(encoding="utf-8")
            documents.append(("wiki", relative, markdown_title(path, raw), raw))
        with open_database(self.database_path) as connection:
            connection.execute("DELETE FROM search_documents")
            connection.executemany(
                """
                INSERT INTO search_documents (kind, identity, title, body)
                VALUES (?, ?, ?, ?)
                """,
                documents,
            )
            connection.commit()


def query_terms(query: str) -> tuple[str, ...]:
    return tuple(term for term in re.split(r"\s+", query.strip()) if term)


def fts_query(terms: tuple[str, ...]) -> str:
    escaped = tuple(term.replace('"', '""') for term in terms)
    return " AND ".join(f'"{term}"' for term in escaped)


def markdown_title(path: Path, raw: str) -> str:
    for line in raw.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem
