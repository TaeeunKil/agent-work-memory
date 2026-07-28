from pathlib import Path

from agentworkmemory.services.distillation.models import (
    SessionDistillDisposition,
    SessionDistillOutcome,
)
from agentworkmemory.services.wiki.models import WikiPage


def classify_session_outcomes(
    session_ids: tuple[str, ...],
    *,
    before: tuple[WikiPage, ...],
    after: tuple[WikiPage, ...],
    changed_files: tuple[Path, ...],
) -> tuple[SessionDistillOutcome, ...]:
    before_paths = {page.path for page in before}
    changed = frozenset(changed_files)
    return tuple(
        classify_session_outcome(
            session_id,
            before=before,
            after=after,
            before_paths=before_paths,
            changed=changed,
        )
        for session_id in session_ids
    )


def classify_session_outcome(
    session_id: str,
    *,
    before: tuple[WikiPage, ...],
    after: tuple[WikiPage, ...],
    before_paths: set[Path],
    changed: frozenset[Path],
) -> SessionDistillOutcome:
    previous = pages_citing(before, session_id)
    current = pages_citing(after, session_id)
    touched = tuple(path for path in current if path in changed)
    created = tuple(path for path in touched if path not in before_paths)
    if created:
        return SessionDistillOutcome(
            session_id=session_id,
            disposition=SessionDistillDisposition.CREATED,
            reason="Created durable Wiki knowledge from this session.",
            pages=current,
        )
    if touched:
        return SessionDistillOutcome(
            session_id=session_id,
            disposition=SessionDistillDisposition.MERGED,
            reason="Merged this session into existing Wiki knowledge.",
            pages=current,
        )
    if previous or current:
        return SessionDistillOutcome(
            session_id=session_id,
            disposition=SessionDistillDisposition.ALREADY_COVERED,
            reason=(
                "Existing Wiki knowledge already cites this session; "
                "no duplicate page was needed."
            ),
            pages=current or previous,
        )
    return SessionDistillOutcome(
        session_id=session_id,
        disposition=SessionDistillDisposition.NO_DURABLE_KNOWLEDGE,
        reason="Reviewed; no new durable knowledge was promoted.",
    )


def pages_citing(
    pages: tuple[WikiPage, ...],
    session_id: str,
) -> tuple[Path, ...]:
    return tuple(
        page.path
        for page in pages
        if session_id in page.source_session_ids
    )


def summarize_session_outcomes(
    outcomes: tuple[SessionDistillOutcome, ...],
) -> str:
    counts = {
        disposition: sum(
            outcome.disposition is disposition for outcome in outcomes
        )
        for disposition in SessionDistillDisposition
    }
    return ", ".join(
        (
            f"{counts[SessionDistillDisposition.CREATED]} created",
            f"{counts[SessionDistillDisposition.MERGED]} merged",
            f"{counts[SessionDistillDisposition.ALREADY_COVERED]} already covered",
            f"{counts[SessionDistillDisposition.NO_DURABLE_KNOWLEDGE]} "
            "no durable knowledge",
        )
    )
