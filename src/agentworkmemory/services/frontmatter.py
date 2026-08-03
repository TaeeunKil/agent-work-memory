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
