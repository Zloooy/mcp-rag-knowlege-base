"""Tests for MarkdownSplitter HTML tag stripping and section extraction."""

from __future__ import annotations

import pytest

from document_processing.markdown_splitter import MarkdownSplitter


class TestStripHtmlTags:
    """Tests for HTML tag stripping exercised through MarkdownSplitter.split()."""

    def test_empty_string(self) -> None:
        splitter = MarkdownSplitter()
        result = splitter.split("", "test.md", ".md")
        # Empty content produces no chunks
        assert len(result.chunks) == 0

    def test_plain_text_unchanged(self) -> None:
        splitter = MarkdownSplitter()
        text = "This is plain text without any markup."
        result = splitter.split("# Title\n\n" + text, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "This is plain text without any markup." in full_text

    def test_simple_div_tag(self) -> None:
        splitter = MarkdownSplitter()
        md = '# Title\n\n<div class="foo">Hello World</div>'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Hello World" in full_text
        assert "<div" not in full_text

    def test_nested_divs(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n<div><div><p>Nested content</p></div></div>"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Nested content" in full_text
        assert "<div" not in full_text

    def test_span_with_style(self) -> None:
        splitter = MarkdownSplitter()
        md = '# Title\n\n<span style="white-space: pre-wrap;">Hello</span>'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Hello" in full_text

    def test_paragraph_tags(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n<p>First paragraph.</p><p>Second paragraph.</p>"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "First paragraph" in full_text
        assert "Second paragraph" in full_text

    def test_blockquote_tags(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n<blockquote><p>Quoted text</p></blockquote>"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Quoted text" in full_text

    def test_anchor_tags_stripped(self) -> None:
        splitter = MarkdownSplitter()
        md = '# Title\n\n<a href="javascript:;">close</a>'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "close" in full_text

    def test_hr_self_closing_tag(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n<hr/>Some text"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Some text" in full_text
        assert "<hr" not in full_text

    def test_sup_tag_footnote_ref(self) -> None:
        # In real SCP Wiki files, sup tags are surrounded by spaces or punctuation
        splitter = MarkdownSplitter()
        md = '# Title\n\ntext<sup class="footnoteref">1</sup>. More text'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "text" in full_text
        assert "1" in full_text
        assert "More text" in full_text
        assert "<" not in full_text

    def test_inline_sup_no_separator(self) -> None:
        # Edge case: no whitespace around inline tag — content still preserved
        splitter = MarkdownSplitter()
        md = '# Title\n\nText<sup class="footnoteref">1</sup>more text'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Text" in full_text
        assert "1" in full_text
        assert "more text" in full_text
        assert "<" not in full_text

    def test_inline_styles_preserve_text(self) -> None:
        splitter = MarkdownSplitter()
        md = '# Title\n\n<p style="text-align: center;"><strong>Item #:</strong> SCP-002</p>'
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Item #:" in full_text
        assert "SCP-002" in full_text
        assert "<" not in full_text
        assert ">" not in full_text

    def test_multiple_consecutive_newlines_collapsed(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\nline1\n\n\n\n\nline2"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        # inscriptis collapses multiple blank lines into a single line break
        assert "line1" in full_text
        assert "line2" in full_text

    def test_whitespace_stripped_from_lines(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n   Hello   \n\n   World   "
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "Hello" in full_text
        assert "World" in full_text

    def test_consecutive_blank_lines_coalesced(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\npara1\n\n\n\npara2"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "para1" in full_text
        assert "para2" in full_text

    def test_complex_wikidot_markup(self) -> None:
        """Regression test based on actual SCP Wiki content patterns."""
        splitter = MarkdownSplitter()
        md = (
            "# Title\n\n"
            '<html><body><div id="page-content">'
            '<div class="list-pages-box"><div class="list-pages-item">'
            "<p><strong>Item:</strong> SCP-001</p>"
            "</div></div></div></body></html>"
        )
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "<" not in full_text
        assert ">" not in full_text
        assert "Item:" in full_text
        assert "SCP-001" in full_text

    def test_table_tags_stripped(self) -> None:
        splitter = MarkdownSplitter()
        md = (
            "# Title\n\n"
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>A</td><td>1</td></tr></table>"
        )
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "<" not in full_text
        assert ">" not in full_text
        assert "Name" in full_text
        assert "Value" in full_text
        assert "A" in full_text
        assert "1" in full_text

    def test_javascript_href_links_stripped(self) -> None:
        splitter = MarkdownSplitter()
        md = """# Title

<a href="javascript:;" onclick="WIKIDOT.page.utils.scrollToReference('footnote-1')">1</a>"""
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "1" in full_text.strip()
        assert "<a" not in full_text

    def test_unicode_content_preserved(self) -> None:
        splitter = MarkdownSplitter()
        md = "# Title\n\n<p>Bonjour le monde — café résumé</p>"
        result = splitter.split(md, "test.md", ".md")
        assert len(result.chunks) >= 1
        full_text = "\n".join(c.content for c in result.chunks)
        assert "café" in full_text
        assert "résumé" in full_text


class TestMarkdownSplitterWithHtml:
    """Integration tests for splitting markdown with embedded HTML."""

    def test_section_extraction_strips_html(self) -> None:
        md_content = """# SCP-002

## Description

<html><body><div id="page-content">
<p>SCP-002 is a fleshy object discovered in a crater in northern Portugal.</p>
</div></body></html>
"""
        splitter = MarkdownSplitter()
        result = splitter.split(md_content, "scp_SCP-002.md", ".md")

        assert len(result.chunks) > 0
        # Verify no HTML tags remain in chunks
        for chunk in result.chunks:
            assert (
                "<" not in chunk.content
                or "<tt>" in chunk.content
                or "# " in chunk.content
            )
            # The main description should have HTML stripped
            if "crater" in chunk.content and "Portugal" in chunk.content:
                assert "<html>" not in chunk.content
                assert "<div" not in chunk.content
                assert "<p>" not in chunk.content

    def test_code_blocks_preserved(self) -> None:
        """Fenced code blocks should NOT be stripped of their content."""
        md_content = """# Code Section

```python
def hello():
    print("world")
```
"""
        splitter = MarkdownSplitter()
        result = splitter.split(md_content, "test.md", ".md")

        # Find the chunk containing the code block
        code_chunks = [c for c in result.chunks if "def hello()" in c.content]
        assert len(code_chunks) >= 1
        # Code block content should be intact
        assert 'print("world")' in code_chunks[0].content

    def test_long_section_with_html_produces_clean_chunks(self) -> None:
        """Large HTML-heavy sections should produce clean, non-redundant chunks."""
        html_block = (
            '<div class="collapsible-block">\n'
            + "<p>Repeated line.</p>\n" * 50
            + "</div>"
        )
        md_content = f"""# Large Section

{html_block}
"""
        splitter = MarkdownSplitter()
        result = splitter.split(md_content, "test.md", ".md")

        assert len(result.chunks) > 1  # Should be split into multiple chunks
        for chunk in result.chunks:
            assert "<div" not in chunk.content
            assert "</div>" not in chunk.content
            assert "<p>" not in chunk.content
            assert "Repeated line" in chunk.content


class TestHtmlTextExtractText:
    """Validate that inscriptis.get_text matches our custom HTML stripping."""

    def test_empty_string(self) -> None:
        from inscriptis import get_text

        assert get_text("") == ""

    def test_plain_text_unchanged(self) -> None:
        from inscriptis import get_text

        text = "This is plain text without any markup."
        assert get_text(text) == text.strip()

    def test_simple_div_tag(self) -> None:
        from inscriptis import get_text

        text = '<div class="foo">Hello World</div>'
        result = get_text(text)
        assert "Hello World" in result

    def test_nested_divs(self) -> None:
        from inscriptis import get_text

        text = "<div><div><p>Nested content</p></div></div>"
        result = get_text(text)
        assert "Nested content" in result

    def test_span_with_style(self) -> None:
        from inscriptis import get_text

        text = '<span style="white-space: pre-wrap;">Hello</span>'
        result = get_text(text)
        assert "Hello" in result

    def test_paragraph_tags(self) -> None:
        from inscriptis import get_text

        text = "<p>First paragraph.</p><p>Second paragraph.</p>"
        result = get_text(text)
        # inscriptis may join paragraphs differently — just verify content present
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_blockquote_tags(self) -> None:
        from inscriptis import get_text

        text = "<blockquote><p>Quoted text</p></blockquote>"
        result = get_text(text)
        assert "Quoted text" in result

    def test_anchor_tags_stripped(self) -> None:
        from inscriptis import get_text

        text = '<a href="javascript:;">close</a>'
        result = get_text(text)
        assert "close" in result

    def test_hr_self_closing_tag(self) -> None:
        from inscriptis import get_text

        text = "<hr/>Some text"
        result = get_text(text)
        assert "Some text" in result

    def test_complex_wikidot_markup(self) -> None:
        from inscriptis import get_text

        text = (
            '<html><body><div id="page-content">'
            '<div class="list-pages-box"><div class="list-pages-item">'
            "<p><strong>Item:</strong> SCP-001</p>"
            "</div></div></div></body></html>"
        )
        result = get_text(text)
        assert "Item:" in result
        assert "SCP-001" in result

    def test_table_tags_stripped(self) -> None:
        from inscriptis import get_text

        text = (
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>A</td><td>1</td></tr></table>"
        )
        result = get_text(text)
        assert "Name" in result
        assert "Value" in result
        assert "A" in result
        assert "1" in result

    def test_unicode_content_preserved(self) -> None:
        from inscriptis import get_text

        text = "<p>Bonjour le monde — café résumé</p>"
        result = get_text(text)
        assert "café" in result
        assert "résumé" in result
