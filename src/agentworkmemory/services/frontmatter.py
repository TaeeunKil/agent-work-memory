import re

import yaml

FRONTMATTER = re.compile(
    r"\A---\r?\n(?P<yaml>.*?)\r?\n---(?:\r?\n|\Z)",
    re.DOTALL,
)


def split_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    match = FRONTMATTER.match(raw)
    if match is None:
        return {}, raw
    loaded = yaml.safe_load(match.group("yaml"))
    metadata = (
        {str(key): value for key, value in loaded.items()}
        if isinstance(loaded, dict)
        else {}
    )
    return metadata, raw[match.end() :]


def normalize_newlines(raw: str) -> str:
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def merge_frontmatter(
    base: dict[str, object],
    extra: dict[str, object],
) -> dict[str, object]:
    merged = dict(base)
    for key, value in extra.items():
        if key == "sources":
            merged["sources"] = merge_sources(
                merged.get("sources"),
                value,
            )
            continue
        if isinstance(value, str):
            if value.strip() or key not in merged:
                merged[key] = value
            continue
        merged[key] = value
    return merged


def merge_sources(existing: object, extra: object) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen: set[str] = set()
    for value in (existing, extra):
        if not isinstance(value, list):
            continue
        for item in flatten_source_items(value):
            session_id = item.get("session_id")
            if not isinstance(session_id, str) or not session_id.strip():
                continue
            if session_id in seen:
                continue
            seen.add(session_id)
            provider = item.get("provider")
            entry: dict[str, object] = {"session_id": session_id}
            if isinstance(provider, str) and provider.strip():
                entry["provider"] = provider
            merged.append(entry)
    return merged


def flatten_source_items(value: list[object]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            nested = item.get("session_id")
            # Malformed YAML sometimes nests another sources list under a key.
            if isinstance(nested, list):
                items.extend(flatten_source_items(nested))
                continue
            items.append({str(key): entry for key, entry in item.items()})
            continue
        if isinstance(item, list):
            items.extend(flatten_source_items(item))
    return items


def peel_frontmatter_blocks(raw: str) -> tuple[dict[str, object], str]:
    """Collapse stacked frontmatter blocks left by repeated distill merges."""
    body = normalize_newlines(raw)
    metadata: dict[str, object] = {}
    while True:
        match = FRONTMATTER.match(body)
        if match is None:
            break
        try:
            loaded = yaml.safe_load(match.group("yaml"))
        except yaml.YAMLError:
            loaded = None
        block = (
            {str(key): value for key, value in loaded.items()}
            if isinstance(loaded, dict)
            else {}
        )
        metadata = merge_frontmatter(metadata, block)
        body = body[match.end() :]
    return metadata, body


def body_from_heading(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# ") and line[2:].strip():
            cleaned = "\n".join(lines[index:]).strip() + "\n"
            return collapse_blank_lines(cleaned)
    return collapse_blank_lines(body.lstrip("\n"))


def collapse_blank_lines(body: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", body)


def enrich_sources_from_body(
    metadata: dict[str, object],
    body: str,
) -> dict[str, object]:
    cited = re.findall(r"ses_[0-9a-f]+", body)
    if not cited:
        return metadata
    merged = dict(metadata)
    merged["sources"] = merge_sources(
        merged.get("sources"),
        [{"session_id": session_id} for session_id in cited],
    )
    return merged


def render_frontmatter(metadata: dict[str, object], body: str) -> str:
    dumped = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip()
    cleaned = body_from_heading(body)
    return f"---\n{dumped}\n---\n{cleaned.lstrip()}".rstrip() + "\n"


def normalize_durable_markdown(raw: str) -> str:
    metadata, body = peel_frontmatter_blocks(raw)
    if not metadata:
        return normalize_newlines(raw)
    body = body_from_heading(body)
    metadata = enrich_sources_from_body(metadata, body)
    return render_frontmatter(metadata, body)


def split_normalized_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    return peel_frontmatter_blocks(raw)
