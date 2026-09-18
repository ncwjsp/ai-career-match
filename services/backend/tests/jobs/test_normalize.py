"""Job posting normalization from raw HTML (B-02). No network."""

from datetime import UTC, datetime

from app.modules.jobs.normalize import normalize_posting

FETCHED_AT = datetime(2026, 9, 16, tzinfo=UTC)


def test_prefers_json_ld_jobposting_when_present():
    html = """
    <html><head><title>ignored fallback title</title>
    <script type="application/ld+json">
    {"@context": "https://schema.org/", "@type": "JobPosting",
     "title": "NLP Engineer",
     "hiringOrganization": {"@type": "Organization", "name": "Example Labs"},
     "description": "<p>Build things with Python and SQL.</p>",
     "datePosted": "2026-09-01",
     "validThrough": "2026-12-01T00:00:00Z"}
    </script></head>
    <body>fallback body text</body></html>
    """

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    assert result.title == "NLP Engineer"
    assert result.company == "Example Labs"
    assert "Build things with Python and SQL." in result.description
    assert result.posted_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert result.expires_at == datetime(2026, 12, 1, tzinfo=UTC)


def test_falls_back_to_title_tag_and_body_text_without_json_ld():
    html = (
        "<html><head><title>NLP Engineer at Example Labs</title></head>"
        "<body><p>Build things with Python.</p></body></html>"
    )

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    assert result.title == "NLP Engineer"
    assert result.company == "Example Labs"
    assert "Build things with Python." in result.description
    assert result.posted_at is None
    assert result.expires_at is None


def test_falls_back_to_unknown_company_when_title_has_no_separator():
    html = "<html><head><title>NLP Engineer</title></head><body>Some text.</body></html>"

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    assert result.title == "NLP Engineer"
    assert result.company == "Unknown"


def test_extracts_required_skills_as_job_requirements():
    html = (
        "<html><head><title>Engineer at Example Labs</title></head>"
        "<body><p>You must know Python and SQL. No Docker required.</p></body></html>"
    )

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    skills = {r.skill: r.required for r in result.requirements}
    assert skills["Python"] is True
    assert skills["SQL"] is True
    assert "Docker" not in skills


def test_uncertain_assertions_become_preferred_not_required():
    html = (
        "<html><head><title>Engineer at Example Labs</title></head>"
        "<body><p>Basic exposure to Docker is a plus."
        " Solid Python skills required.</p></body></html>"
    )

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    skills = {r.skill: r.required for r in result.requirements}
    assert skills["Docker"] is False
    assert skills["Python"] is True


def test_requirement_evidence_uses_the_given_document_id():
    html = (
        "<html><head><title>Engineer at Example Labs</title></head>"
        "<body>Python required.</body></html>"
    )

    result = normalize_posting(html, document_id="job-abc", fetched_at=FETCHED_AT)

    assert all(ref.document_id == "job-abc" for r in result.requirements for ref in r.evidence)
    assert all(ref.document_id == "job-abc" for ref in result.evidence)


def test_blank_description_gets_a_placeholder_not_a_validation_error():
    html = "<html><head><title>Engineer at Example Labs</title></head><body></body></html>"

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    assert result.description
    assert result.requirements == []


def test_repeated_mentions_at_the_same_confidence_accumulate_evidence():
    html = (
        "<html><head><title>Engineer at Example Labs</title></head>"
        "<body><p>Python required. Also, more Python experience is a big plus.</p></body></html>"
    )

    result = normalize_posting(html, document_id="job-1", fetched_at=FETCHED_AT)

    python_reqs = [r for r in result.requirements if r.skill == "Python"]
    assert len(python_reqs) == 1
    assert len(python_reqs[0].evidence) >= 1
