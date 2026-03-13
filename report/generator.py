"""Generate the HTML report from product data."""

import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


_TEMPLATE_DIR = Path(__file__).parent
_PLACEHOLDER = Path(__file__).parent / "placeholder.png"


def _image_to_base64(path) -> str:
    """Embed image as base64 data URI so the HTML is self-contained."""
    if path and Path(path).exists():
        data = Path(path).read_bytes()
        b64 = base64.b64encode(data).decode()
        return f"data:image/jpeg;base64,{b64}"

    # Return a simple grey placeholder SVG
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
        '<rect width="200" height="200" fill="#e5e7eb"/>'
        '<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" '
        'font-family="sans-serif" font-size="13" fill="#9ca3af">Sem imagem</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"


def generate_report(
    company_name: str,
    products: list,
    output_path: str = "output/report.html",
    cnpj: str = "",
    logo_path: str = "",
) -> str:
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    env.globals["image_to_base64"] = _image_to_base64

    template = env.get_template("template.html")

    html = template.render(
        company_name=company_name,
        cnpj=cnpj,
        logo_b64=_image_to_base64(logo_path) if logo_path else "",
        products=products,
        total=len(products),
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)
