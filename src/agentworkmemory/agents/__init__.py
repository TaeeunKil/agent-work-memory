from importlib.resources import files


def distill_instructions() -> str:
    return (
        files("agentworkmemory.agents").joinpath("distill.md").read_text(encoding="utf-8")
    )


__all__ = ["distill_instructions"]
