"""HTML text/JSON-LD extraction (B-02). Pure functions; no network."""

from app.modules.jobs.html_text import (
    extract_json_ld_jobposting,
    extract_title_tag,
    extract_visible_text,
)


def test_extract_visible_text_strips_tags_and_scripts():
    html = """
    <html><head><title>ignored</title><style>.x{color:red}</style></head>
    <body>
      <script>var x = 1;</script>
      <h1>NLP Engineer</h1>
      <p>Build things with Python.</p>
    </body></html>
    """

    text = extract_visible_text(html)

    assert "NLP Engineer" in text
    assert "Build things with Python." in text
    assert "var x" not in text
    assert ".x{color:red}" not in text


def test_extract_visible_text_collapses_whitespace():
    html = "<p>Line   one</p><p>Line two</p>"

    text = extract_visible_text(html)

    assert text == "Line one\nLine two"


def test_extract_title_tag_returns_the_title_text():
    html = "<html><head><title>NLP Engineer at Example Corp</title></head><body></body></html>"

    assert extract_title_tag(html) == "NLP Engineer at Example Corp"


def test_extract_title_tag_returns_none_when_absent():
    assert extract_title_tag("<html><body>No title here.</body></html>") is None


def test_extract_json_ld_jobposting_finds_a_bare_object():
    html = """
    <script type="application/ld+json">
    {"@context": "https://schema.org/", "@type": "JobPosting", "title": "NLP Engineer",
     "hiringOrganization": {"@type": "Organization", "name": "Example Corp"}}
    </script>
    """

    result = extract_json_ld_jobposting(html)

    assert result is not None
    assert result["title"] == "NLP Engineer"
    assert result["hiringOrganization"]["name"] == "Example Corp"


def test_extract_json_ld_jobposting_finds_it_inside_a_list():
    html = """
    <script type="application/ld+json">
    [{"@type": "BreadcrumbList"}, {"@type": "JobPosting", "title": "Data Scientist"}]
    </script>
    """

    result = extract_json_ld_jobposting(html)

    assert result is not None
    assert result["title"] == "Data Scientist"


def test_extract_json_ld_jobposting_finds_it_inside_a_graph():
    html = """
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "name": "Example Corp"},
        {"@type": "JobPosting", "title": "Backend Engineer"}
    ]}
    </script>
    """

    result = extract_json_ld_jobposting(html)

    assert result is not None
    assert result["title"] == "Backend Engineer"


def test_extract_json_ld_jobposting_returns_none_when_absent():
    html = '<script type="application/ld+json">{"@type": "Organization"}</script>'

    assert extract_json_ld_jobposting(html) is None


def test_extract_json_ld_jobposting_ignores_unparseable_blocks():
    html = '<script type="application/ld+json">{not valid json</script>'

    assert extract_json_ld_jobposting(html) is None


def test_extract_json_ld_jobposting_handles_a_type_list():
    html = """
    <script type="application/ld+json">
    {"@type": ["JobPosting", "CreativeWork"], "title": "Designer"}
    </script>
    """

    result = extract_json_ld_jobposting(html)

    assert result is not None
    assert result["title"] == "Designer"
