import sys


def load_text(text: str | None, files: list[str]) -> str:
    """Resolve input: positional text, stdin ('-'), or one or more files."""
    if text and files:
        raise SystemExit("Provide either text or --file, not both.")
    if text == "-":
        return sys.stdin.read()
    if text:
        return text
    if files:
        parts = []
        for f in files:
            if f == "-":
                parts.append(sys.stdin.read())
                continue
            try:
                with open(f, encoding="utf-8") as fh:
                    parts.append(fh.read())
            except OSError as e:
                raise SystemExit(f"Cannot read '{f}': {e}") from None
        return "\n\n".join(parts)
    raise SystemExit("No text provided. Pass text, `-` for stdin, or --file.")
