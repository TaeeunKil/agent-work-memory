import re
from hashlib import sha256
from pathlib import Path

from workalmanac.database import open_database
from workalmanac.services.search.models import SearchSourceSignature
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
        self.refresh_if_stale()
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

    def refresh_if_stale(self) -> None:
        signature = self.source_signature()
        if self.indexed_signature() != signature:
            self.refresh(signature)

    def refresh(self, signature: SearchSourceSignature | None = None) -> None:
        indexed_signature = signature or self.source_signature()
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
            connection.execute(
                """
                INSERT INTO search_index_state (
                  id, session_count, session_version, event_count,
                  event_rowid, vault_digest
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  session_count = excluded.session_count,
                  session_version = excluded.session_version,
                  event_count = excluded.event_count,
                  event_rowid = excluded.event_rowid,
                  vault_digest = excluded.vault_digest
                """,
                signature_values(indexed_signature),
            )
            connection.commit()

    def source_signature(self) -> SearchSourceSignature:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM agent_sessions) AS session_count,
                  COALESCE(
                    (SELECT MAX(updated_at) FROM agent_sessions),
                    ''
                  ) AS session_version,
                  (SELECT COUNT(*) FROM agent_events) AS event_count,
                  COALESCE(
                    (SELECT MAX(rowid) FROM agent_events),
                    0
                  ) AS event_rowid
                """
            ).fetchone()
        return SearchSourceSignature(
            session_count=row["session_count"],
            session_version=row["session_version"],
            event_count=row["event_count"],
            event_rowid=row["event_rowid"],
            vault_digest=vault_digest(self.vault),
        )

    def indexed_signature(self) -> SearchSourceSignature | None:
        with open_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM search_index_state WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return SearchSourceSignature(
            session_count=row["session_count"],
            session_version=row["session_version"],
            event_count=row["event_count"],
            event_rowid=row["event_rowid"],
            vault_digest=row["vault_digest"],
        )


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


def vault_digest(vault: VaultService) -> str:
    root = vault.require_path()
    digest = sha256()
    for path in vault.markdown_files():
        stat = path.stat()
        relative = path.relative_to(root).as_posix()
        digest.update(f"{relative}\0{stat.st_mtime_ns}\0{stat.st_size}\n".encode())
    return digest.hexdigest()


def signature_values(signature: SearchSourceSignature) -> tuple[object, ...]:
    return (
        signature.session_count,
        signature.session_version,
        signature.event_count,
        signature.event_rowid,
        signature.vault_digest,
    )
