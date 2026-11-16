"""
Load source material and prepare it for the podcast pipeline.

Flow:

PDF files
    ↓
Extract text
    ↓
Clean text
    ↓
Attach source information
    ↓
Return content for the LLM
"""

from pathlib import Path

from pypdf import PdfReader


# Information about the source PDFs.
SOURCE_INFO = {
    "Potentially Harmful Consequences of AI.pdf": {
        "full_title": (
            "Potentially harmful consequences of artificial intelligence "
            "(AI) chatbot use among patients with mental illness"
        ),
        "author": (
            "Sidse Godske Olsen, Christian Jon Reinecke-Tellefsen, "
            "Soren Dinesen Ostergaard"
        ),
        "publication": "Acta Psychiatrica Scandinavica",
        "year": "2026",
        "type": "Research letter",
    },
    "AI going rogue.pdf": {
        "full_title": (
            "AI going rogue? An integrative narrative review of the "
            "tacit assumptions underlying existential AI-risks"
        ),
        "author": "Jascha Bareis, Clemens Ackerl, Reinhard Heil",
        "publication": "AI and Ethics",
        "year": "2026",
        "type": "Peer-reviewed narrative review",
    },
    "AI and the End of the World.pdf": {
    "full_title": "AI & the End of the World: What the Data Say",
    "author": "Alexander Rogul",
    "publication": "Working paper, Bentley University",
    "year": "2026",
    "type": "Working paper",
    },
}


def source_label(source: dict) -> str:
    """Create a readable description of a source."""

    label = source["author"]

    if source.get("publication"):
        label += f", {source['publication']}"

    if source.get("year"):
        label += f" ({source['year']})"

    return label


def strip_references(text: str) -> str:
    """
    Remove the reference list from the end of a paper when possible.
    """

    reference_markers = [
        "\nReferences",
        "\nREFERENCES",
        "\nBibliography",
        "\nBIBLIOGRAPHY",
    ]

    for marker in reference_markers:
        index = text.rfind(marker)

        # Only remove it if it appears in the second half
        # of the document.
        if index > len(text) * 0.5:
            return text[:index].strip()

    return text


def from_pdf(file_path: str | Path) -> dict:
    """
    Read one PDF and return its complete extracted text
    together with source information.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {path.name}")

    try:
        reader = PdfReader(str(path))

        # Extract text from every page.
        pages = [
            page.extract_text() or ""
            for page in reader.pages
        ]

        # Combine the pages into one complete text string.
        text = "\n".join(pages).strip()

        # Read optional metadata stored inside the PDF.
        metadata = reader.metadata

    except Exception as error:
        raise ValueError(
            f"Could not read PDF '{path.name}': {error}"
        ) from error

    if not text:
        raise ValueError(
            f"The PDF '{path.name}' contains no readable text."
        )

    # Remove the bibliography but keep all other extracted text.
    text = strip_references(text)

    known_info = SOURCE_INFO.get(path.name, {})

    metadata_author = None

    if metadata:
        metadata_author = metadata.get("/Author")

    # Store information about the paper in one dictionary.
    source = {
        "id": path.stem,
        "file_name": path.name,
        "full_title": known_info.get("full_title", path.stem),
        "author": (
            known_info.get("author")
            or metadata_author
            or "Unknown author"
        ),
        "publication": known_info.get("publication", ""),
        "year": known_info.get("year", ""),
        "type": known_info.get("type", ""),
    }

    # Return one standard format for the rest of the pipeline.
    return {
        "source_type": "pdf",
        "title": path.name,
        "text": text,
        "sources": [source],
    }


def from_multiple_pdfs(file_paths: list[str | Path]) -> dict:
    """
    Read several PDFs and combine them into one content object.
    """

    if not file_paths:
        raise ValueError("No PDF files were provided.")

    texts = []
    sources = []

    for file_path in file_paths:
        # Process each PDF using from_pdf().
        pdf_content = from_pdf(file_path)

        source = pdf_content["sources"][0]
        sources.append(source)

        # Add a clear source label before each paper's text.
        labelled_text = (
            f"--- SOURCE [{source['id']}]: "
            f"{source_label(source)} ---\n"
            f"{pdf_content['text']}"
        )

        texts.append(labelled_text)

    # Return all papers in one structured object.
    return {
        "source_type": "pdf",
        "title": " + ".join(source["id"] for source in sources),
        "text": "\n\n".join(texts),
        "sources": sources,
    }


# These compatibility functions allow your current main.py
# to keep working without changes.


def load_pdf_text(pdf_path: str | Path) -> str:
    """
    Return only the complete extracted text from one PDF.
    """

    return from_pdf(pdf_path)["text"]


def load_source_material(folder_path: str | Path) -> dict[str, str]:
    """
    Load every PDF in a folder.

    Returns a dictionary containing the complete text
    from every PDF.
    """

    folder = Path(folder_path)
    pdf_files = sorted(folder.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in: {folder}"
        )

    return {
        pdf.name: load_pdf_text(pdf)
        for pdf in pdf_files
    }
