from __future__ import annotations

from unittest.mock import MagicMock, patch

from event_maintainer.search.ddg import _parse_ddg_results, search_web

_SAMPLE_HTML = """
<html><body>
<a class="result__a" href="https://example.com/fed">Fed holds rates</a>
<a class="result__snippet">The Federal Reserve kept rates unchanged.</a>
</body></html>
"""


def test_parse_ddg_results_extracts_title_and_url() -> None:
    results = _parse_ddg_results(_SAMPLE_HTML)
    assert len(results) >= 1
    assert results[0]["url"] == "https://example.com/fed"
    assert "Fed" in results[0]["title"]


@patch("event_maintainer.search.ddg.urlopen")
def test_search_web_returns_parsed_results(mock_urlopen: MagicMock) -> None:
    response = MagicMock()
    response.headers.get_content_charset.return_value = "utf-8"
    response.read.return_value = _SAMPLE_HTML.encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    mock_urlopen.return_value = response

    results = search_web("fed rates", count=5)
    assert len(results) >= 1
    assert results[0]["title"]
