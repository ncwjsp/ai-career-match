"""Small synthetic documents built in memory; no private files, network or office software."""

import os
from io import BytesIO
from uuid import uuid4
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from alembic import command
from alembic.config import Config
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from tests.conftest import BACKEND_ROOT

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"


@pytest.fixture
def app_db_url(app_db_url, monkeypatch):
    """Opt in to PostgreSQL using a fresh, test-owned schema per resume test."""
    postgres = os.environ.get("ACM_TEST_POSTGRES_URL")
    if not postgres:
        yield app_db_url
        return
    base_url = make_url(postgres)
    if base_url.get_backend_name() != "postgresql":
        pytest.fail("ACM_TEST_POSTGRES_URL must point to a disposable PostgreSQL database")
    schema = "resume_test_" + uuid4().hex
    engine = create_engine(base_url)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        url = base_url.update_query_dict(
            {"options": f"-csearch_path={schema} -cstatement_timeout=15000"}
        )
        rendered = url.render_as_string(hide_password=False)
        monkeypatch.setenv("APP_DATABASE_URL", rendered)
        command.upgrade(Config(str(BACKEND_ROOT / "alembic-app.ini")), "head")
        yield rendered
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.fixture
def pdf_factory():
    def build(pages=None, *, encrypted=False, image_only=False):
        writer = PdfWriter()
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        for lines in pages if pages is not None else [["Synthetic Plai", "C++ C# Python PyTorch"]]:
            page = writer.add_blank_page(612, 792)
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            commands = []
            for index, line in enumerate(lines):
                x, y = 50, 740 - index * 20
                if isinstance(line, tuple):
                    line, x, y = line
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.append(f"BT /F1 12 Tf {x} {y} Td ({escaped}) Tj ET")
            if image_only:
                image = DecodedStreamObject()
                image.set_data(b"\xff\xff\xff")
                image.update(
                    {
                        NameObject("/Type"): NameObject("/XObject"),
                        NameObject("/Subtype"): NameObject("/Image"),
                        NameObject("/Width"): NumberObject(1),
                        NameObject("/Height"): NumberObject(1),
                        NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                        NameObject("/BitsPerComponent"): NumberObject(8),
                    }
                )
                page["/Resources"][NameObject("/XObject")] = DictionaryObject(
                    {NameObject("/Im0"): writer._add_object(image)}
                )
                commands = ["q 100 0 0 100 50 600 cm /Im0 Do Q"]
            stream.set_data("\n".join(commands).encode("ascii"))
            page[NameObject("/Contents")] = writer._add_object(stream)
        if encrypted:
            writer.encrypt("synthetic-password", algorithm="RC4-128")
        output = BytesIO()
        writer.write(output)
        return output.getvalue()

    return build


@pytest.fixture
def paragraph():
    def build(text):
        return f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'

    return build


@pytest.fixture
def docx_factory(paragraph):
    def build(body=None, *, replacements=None, extras=None, header=None, footer=None):
        body = (
            body if body is not None else paragraph("Synthetic Plai") + paragraph("Python C++ C#")
        )
        relationships = []
        refs = []
        parts = {}
        for kind, text in [("header", header), ("footer", footer)]:
            if text is None:
                continue
            parts[f"word/{kind}1.xml"] = (
                f'<w:{"hdr" if kind == "header" else "ftr"} xmlns:w="{W}">'
                + paragraph(text)
                + f"</w:{'hdr' if kind == 'header' else 'ftr'}>"
            )
            relationships.append(
                f'<Relationship Id="{kind}" Type="{R}/{kind}" Target="{kind}1.xml"/>'
            )
            refs.append(f'<w:{kind}Reference w:type="default" r:id="{kind}"/>')
        parts.update(
            {
                "[Content_Types].xml": (
                    f'<Types xmlns="{CT}"><Default Extension="rels" '
                    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    f'<Override PartName="/word/document.xml" ContentType="{MAIN}"/></Types>'
                ),
                "_rels/.rels": (
                    f'<Relationships xmlns="{REL}"><Relationship Id="office" '
                    f'Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'
                ),
                "word/document.xml": (
                    f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}'
                    f"<w:sectPr>{''.join(refs)}</w:sectPr></w:body></w:document>"
                ),
                "word/_rels/document.xml.rels": (
                    f'<Relationships xmlns="{REL}">{"".join(relationships)}</Relationships>'
                ),
            }
        )
        for name, content in (replacements or {}).items():
            if content is None:
                parts.pop(name, None)
            else:
                parts[name] = content
        parts.update(extras or {})
        result = BytesIO()
        with ZipFile(result, "w", compression=ZIP_DEFLATED) as archive:
            for name, content in parts.items():
                archive.writestr(name, content)
        return result.getvalue()

    return build
