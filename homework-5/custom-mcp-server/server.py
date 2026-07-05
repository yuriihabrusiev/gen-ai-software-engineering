from pathlib import Path

from fastmcp import FastMCP

LOREM_IPSUM_PATH = Path(__file__).parent / "lorem-ipsum.md"

mcp = FastMCP("custom-mcp-server")


def get_lorem_words(word_count: int = 30) -> str:
    """Return the first `word_count` words from lorem-ipsum.md, space-joined."""
    words = LOREM_IPSUM_PATH.read_text().split()
    return " ".join(words[:word_count])


@mcp.resource("lorem://lorem-ipsum")
def lorem_ipsum_default() -> str:
    """Resource: the first 30 words of lorem-ipsum.md."""
    return get_lorem_words()


@mcp.resource("lorem://lorem-ipsum/{word_count}")
def lorem_ipsum_with_count(word_count: int) -> str:
    """Resource: the first `word_count` words of lorem-ipsum.md."""
    return get_lorem_words(word_count)


@mcp.tool()
def read(word_count: int = 30) -> str:
    """Return the first `word_count` words from lorem-ipsum.md."""
    return get_lorem_words(word_count)


if __name__ == "__main__":
    mcp.run()
