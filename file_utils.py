import io


def extract_text_from_bytes(raw_bytes: bytes, mimetype: str) -> str:
    """
    Given the raw bytes of an uploaded file plus its mimetype,
    return the full text content.
    """
    # 1) Plain text
    if mimetype.startswith("text/"):
        return raw_bytes.decode("utf-8", errors="ignore")

    # 2) PDF
    if mimetype == "application/pdf":
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("Missing `pdfplumber`; run `pip install pdfplumber`")
        text_pages = []
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_pages.append(page_text)
        return "\n\n".join(text_pages)

    # 3) DOCX (Word)
    if mimetype in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        try:
            import docx  # from python-docx
        except ImportError:
            raise RuntimeError("Missing `python-docx`; run `pip install python-docx`")
        document = docx.Document(io.BytesIO(raw_bytes))
        return "\n\n".join(p.text for p in document.paragraphs)

    # 4) Unsupported
    raise ValueError(f"Unsupported file type: {mimetype}")
