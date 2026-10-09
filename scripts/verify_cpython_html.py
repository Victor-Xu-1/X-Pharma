"""Probe the installed CPython HTML parser's bounded comment handling."""

from __future__ import annotations

from html.parser import HTMLParser


def verify_comment_stream() -> None:
    parser = HTMLParser()
    parser.feed("<!--")
    for _ in range(200_000):
        parser.feed("a" * 64)
    parser.feed("-->")
    parser.close()


if __name__ == "__main__":
    verify_comment_stream()
    print("html_comment_stream=protected")
