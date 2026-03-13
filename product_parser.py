"""Parser flexível de listas de produtos em texto."""

import re
from dataclasses import dataclass

# Padrões de separador após o número:  1-  1.  1)  1–  1—  1:  (e variações com espaço)
_LINE_START = re.compile(r"^\s*(\d+)\s*[-–—.):\s]\s*(.+)", re.UNICODE)

# Padrões de referência: Referência, Referencia, Ref., REF:, etc.
_REF_PATTERN = re.compile(
    r"[Rr]efer[eê]n[cs]ia[:\s.]*([A-Za-z0-9/_\-\.]+)"
    r"|[Rr]ef[\.:\s]+([A-Za-z0-9/_\-\.]+)",
)

# Encodings a tentar (em ordem de prioridade)
_ENCODINGS = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]


@dataclass
class Product:
    number: int
    description: str
    reference: str = ""
    image_path: str = ""
    image_url: str = ""


def parse_text(raw: str) -> list:
    """Parse a string with a product list and return list of Product."""
    products = []
    current_number = None
    current_lines = []

    lines = [line.strip() for line in raw.splitlines()]

    for line in lines:
        if not line:
            continue

        match = _LINE_START.match(line)
        if match:
            if current_number is not None:
                _flush(current_number, current_lines, products)
            current_number = int(match.group(1))
            current_lines = [match.group(2).strip()]
        else:
            if current_number is not None:
                current_lines.append(line)

    if current_number is not None:
        _flush(current_number, current_lines, products)

    return products


def parse_products(file_path: str) -> list:
    """Read a product list TXT file and return list of Product."""
    raw = _read_file(file_path)
    return parse_text(raw)


def _read_file(path: str) -> str:
    """Try multiple encodings to read the file robustly."""
    for enc in _ENCODINGS:
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    # Last resort: ignore decode errors
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _flush(number: int, lines: list, products: list):
    full_text = " ".join(lines)

    # Extract reference
    ref_match = _REF_PATTERN.search(full_text)
    if ref_match:
        reference = (ref_match.group(1) or ref_match.group(2) or "").strip()
        reference = reference.rstrip(".,;").strip()
    else:
        reference = ""

    # Clean description — remove reference portion and trailing punctuation
    description = _REF_PATTERN.sub("", full_text)
    description = re.sub(r"\s{2,}", " ", description).strip().rstrip(".,;:").strip()

    if description:
        products.append(Product(number=number, description=description, reference=reference))
