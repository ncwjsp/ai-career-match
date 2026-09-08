import pytest

from app.nlp.skills import find_skills
from app.nlp.text import normalize_text
from tests.nlp.test_text import source


def mentions(text):
    return find_skills(source(text), normalize_text(text))


def test_aliases_and_technical_terms():
    found = mentions("C++ CSharp PYTORCH sklearn postgres Node.js .NET java script")
    assert [x.canonical for x in found] == [
        "C++",
        "C#",
        "PyTorch",
        "scikit-learn",
        "PostgreSQL",
        "Node.js",
        ".NET",
        "JavaScript",
    ]
    assert all(x.evidence[0].excerpt == x.text for x in found)


def test_no_substrings_or_framework_parent_inference():
    found = mentions("JavaScript SQLAlchemy GitHub PyTorch C++++ React.js")
    assert [x.canonical for x in found] == ["JavaScript", "PyTorch", "React"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("No experience with Python or SQL.", ["negated", "negated"]),
        ("Never used Python.", ["negated"]),
        ("Without Python experience", ["negated"]),
        ("Learning Python and SQL", ["uncertain", "uncertain"]),
        ("Basic Python", ["uncertain"]),
        ("Python is not required", ["negated"]),
        ("Not only Python but SQL", ["mentioned", "mentioned"]),
        ("No Python but SQL", ["negated", "mentioned"]),
        ("No sales experience. Used Python.", ["mentioned"]),
        ("No Python\nSQL", ["negated", "mentioned"]),
        ("Python. No Python.", ["mentioned", "negated"]),
    ],
)
def test_assertion_scope(text, expected):
    assert [x.assertion for x in mentions(text)] == expected


def test_normalized_alias_keeps_original_unicode_evidence():
    found = mentions("Ｐｙｔｈｏｎ\tand C#")
    assert found[0].canonical == "Python"
    assert found[0].evidence[0].excerpt == "Ｐｙｔｈｏｎ"


def test_unknown_ambiguous_names_are_not_invented():
    assert mentions("R C ML AI and quantum basket weaving") == ()


@pytest.mark.parametrize("text", ["I don't know Python", "I haven’t used Python"])
def test_contracted_negation(text):
    assert mentions(text)[0].assertion == "negated"
