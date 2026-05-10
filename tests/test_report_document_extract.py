"""Tests for ``build_report_document`` JSON (outline + parent)."""

from __future__ import annotations

import unittest

from relay_report_audit.sections.report_document_extract import build_report_document


class TestReportDocumentExtract(unittest.TestCase):
    def test_caps_parent_for_numbered_subsection(self) -> None:
        md = """
TRANSFORMER TESTING

| MAKE | X |
|------|---|
| A | B |

- 5.0WINDING RESISTANCE TEST:

| Tap | R |
|-----|---|
| 1 | 2 |

## NEXT CHAPTER
"""
        doc = build_report_document(md)
        by_slug = {s.section_slug: s for s in doc.sections}
        tt = by_slug.get("transformer-testing")
        w = by_slug.get("winding-resistance-test")
        self.assertIsNotNone(tt)
        self.assertIsNotNone(w)
        self.assertEqual(w.outline, [5, 0])
        self.assertEqual(w.parent_section_slug, tt.section_slug)

    def test_outline_prefix_parent(self) -> None:
        md = """
- 4 BRANCH

- 4.2 CHILD

- 4.3 SIBLING
"""
        doc = build_report_document(md)
        slugs = [s.section_slug for s in doc.sections if s.heading_kind != "preamble"]
        self.assertGreaterEqual(len(slugs), 2)
        child = next(s for s in doc.sections if s.outline == [4, 2])
        parent = next(s for s in doc.sections if s.outline == [4])
        self.assertEqual(child.parent_section_slug, parent.section_slug)


if __name__ == "__main__":
    unittest.main()
