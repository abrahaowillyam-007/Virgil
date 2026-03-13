import re
from dataclasses import dataclass, field


@dataclass
class Product:
    number: int
    description: str
    reference: str = ""
    image_path: str = ""
    image_url: str = ""


def parse_products(file_path: str) -> list[Product]:
    """Parse a product list TXT file.

    Expected format per line:
        N-Description. Referência: CODE
    or:
        N-Description.
    """
    products = []
    current_number = None
    current_lines = []

    with open(file_path, encoding="utf-8") as f:
        raw = f.read()

    # Split on newlines and re-join continuation lines
    lines = [line.strip() for line in raw.splitlines()]

    for line in lines:
        if not line:
            continue

        # Check if line starts a new product (digits followed by -)
        match = re.match(r"^(\d+)-(.+)", line)
        if match:
            # Save previous product if any
            if current_number is not None:
                _flush(current_number, current_lines, products)
            current_number = int(match.group(1))
            current_lines = [match.group(2).strip()]
        else:
            # Continuation of current product description
            if current_number is not None:
                current_lines.append(line)

    # Flush last product
    if current_number is not None:
        _flush(current_number, current_lines, products)

    return products


def _flush(number: int, lines: list[str], products: list[Product]):
    full_text = " ".join(lines)

    # Extract reference if present
    ref_match = re.search(r"[Rr]efer[eê]ncia[:\s]+([A-Za-z0-9/_\-\.]+)", full_text)
    reference = ref_match.group(1).strip() if ref_match else ""

    # Clean description (remove reference part)
    description = re.sub(r"\.?\s*[Rr]efer[eê]ncia[:\s]+\S*", "", full_text).strip()
    description = description.rstrip(".,").strip()

    products.append(Product(number=number, description=description, reference=reference))
