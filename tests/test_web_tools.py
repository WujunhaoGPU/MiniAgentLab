from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniagentlab.web_tools import extract_text, fetch_page, search_web, summarize_text


class WebToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.page_path = Path(self.tempdir.name) / "reflection.html"
        self.search_path = Path(self.tempdir.name) / "search.html"
        self.page_path.write_text(
            """
            <html>
              <head><title>MiniAgentLab Reflection</title><style>.x{}</style></head>
              <body>
                <h1>Reflection</h1>
                <p>Reflection analyzes failed plans and tool execution errors.</p>
                <script>console.log('skip me')</script>
                <p>TraceLogger records every tool call.</p>
              </body>
            </html>
            """,
            encoding="utf-8",
        )
        self.search_path.write_text(
            f"""
            <html>
              <body>
                <a class="result__a" href="{self.page_path.as_uri()}">MiniAgentLab Reflection Guide</a>
              </body>
            </html>
            """,
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_search_web_parses_local_search_results(self) -> None:
        results = search_web("reflection", search_url=self.search_path.as_uri())

        self.assertEqual(results[0]["title"], "MiniAgentLab Reflection Guide")
        self.assertEqual(results[0]["url"], self.page_path.as_uri())

    def test_fetch_page_reads_file_url(self) -> None:
        page = fetch_page(self.page_path.as_uri())

        self.assertEqual(page["title"], "MiniAgentLab Reflection")
        self.assertIn("Reflection analyzes", page["html"])

    def test_extract_text_skips_script_and_style(self) -> None:
        text = extract_text(fetch_page(self.page_path.as_uri()))

        self.assertIn("Reflection analyzes failed plans", text["text"])
        self.assertNotIn("skip me", text["text"])
        self.assertNotIn(".x", text["text"])

    def test_summarize_text_selects_query_relevant_sentence(self) -> None:
        text = extract_text(fetch_page(self.page_path.as_uri()))

        summary = summarize_text(text, query="What does Reflection analyze?", max_sentences=1)

        self.assertEqual(summary["source"]["title"], "MiniAgentLab Reflection")
        self.assertIn("Reflection analyzes failed plans", summary["summary"])


if __name__ == "__main__":
    unittest.main()
