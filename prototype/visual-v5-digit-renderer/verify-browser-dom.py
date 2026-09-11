from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ALLOWED_GLYPHS = frozenset("0123456789.:-@")


class DigitLabDomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.output_depth: int | None = None
        self.in_output = False
        self.output_glyphs: list[str] = []
        self.output_forbidden_elements: list[str] = []
        self.output_background_styles: list[str] = []
        self.status_columns_depth: int | None = None
        self.status_rows_depth: int | None = None
        self.render_status_depth: int | None = None
        self.status_columns_text: list[str] = []
        self.status_rows_text: list[str] = []
        self.render_status_text: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {name: value or "" for name, value in attrs}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        attr_map = self._attrs(attrs)
        element_id = attr_map.get("id")

        if element_id == "digit-output":
            self.output_depth = self.depth
            self.in_output = True

        if element_id == "status-columns":
            self.status_columns_depth = self.depth
        elif element_id == "status-rows":
            self.status_rows_depth = self.depth
        elif element_id == "render-status":
            self.render_status_depth = self.depth

        if self.in_output:
            if tag in {"img", "canvas", "svg", "video"}:
                self.output_forbidden_elements.append(tag)

            classes = set(attr_map.get("class", "").split())
            if "glyph-cell" in classes:
                glyph = attr_map.get("data-glyph", "")
                self.output_glyphs.append(glyph)
                style = attr_map.get("style", "").lower()
                if re.search(r"(?:^|;)\s*background(?:-color)?\s*:", style):
                    self.output_background_styles.append(style)

    def handle_endtag(self, tag: str) -> None:
        if self.output_depth is not None and self.depth == self.output_depth:
            self.in_output = False
            self.output_depth = None
        if self.status_columns_depth is not None and self.depth == self.status_columns_depth:
            self.status_columns_depth = None
        if self.status_rows_depth is not None and self.depth == self.status_rows_depth:
            self.status_rows_depth = None
        if self.render_status_depth is not None and self.depth == self.render_status_depth:
            self.render_status_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        if self.status_columns_depth is not None:
            self.status_columns_text.append(data)
        if self.status_rows_depth is not None:
            self.status_rows_text.append(data)
        if self.render_status_depth is not None:
            self.render_status_text.append(data)


def verify_dom(html: str, minimum_glyphs: int = 10_000) -> dict[str, int | str]:
    parser = DigitLabDomParser()
    parser.feed(html)

    glyph_count = len(parser.output_glyphs)
    if glyph_count < minimum_glyphs:
        raise AssertionError(f"expected at least {minimum_glyphs} glyph cells, found {glyph_count}")

    invalid_glyphs = sorted({glyph for glyph in parser.output_glyphs if glyph not in ALLOWED_GLYPHS})
    if invalid_glyphs:
        raise AssertionError(f"unexpected glyphs in output: {invalid_glyphs!r}")

    if parser.output_forbidden_elements:
        raise AssertionError(
            "forbidden raster/vector elements inside #digit-output: "
            + ", ".join(parser.output_forbidden_elements)
        )

    if parser.output_background_styles:
        raise AssertionError("glyph cells contain per-cell background styles")

    columns_text = "".join(parser.status_columns_text).strip()
    rows_text = "".join(parser.status_rows_text).strip()
    render_status = " ".join("".join(parser.render_status_text).split())

    if columns_text != "240":
        raise AssertionError(f"expected rendered column status 240, found {columns_text!r}")
    if not rows_text.isdigit() or int(rows_text) <= 0:
        raise AssertionError(f"expected positive rendered row status, found {rows_text!r}")
    if "Render failed" in render_status:
        raise AssertionError(render_status)
    if "selectable glyph cells" not in render_status:
        raise AssertionError(f"render did not reach completion status: {render_status!r}")

    return {
        "glyph_count": glyph_count,
        "columns": int(columns_text),
        "rows": int(rows_text),
        "render_status": render_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify rendered Visual v5 DOM proof")
    parser.add_argument("dom", type=Path)
    parser.add_argument("--minimum-glyphs", type=int, default=10_000)
    args = parser.parse_args()

    try:
        result = verify_dom(args.dom.read_text(encoding="utf-8"), args.minimum_glyphs)
    except (OSError, AssertionError) as exc:
        print(f"VISUAL V5 BROWSER PROOF FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        "VISUAL V5 BROWSER PROOF PASS: "
        f"{result['glyph_count']} glyphs, {result['columns']}x{result['rows']}; "
        f"{result['render_status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
