#!/usr/bin/env python3
"""
Virgil — Product Report Generator
Usage:
    python main.py products.txt "Nome da Empresa"
    python main.py products.txt "Nome da Empresa" --output output/report.html
"""

import argparse
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.text import Text

from parser import parse_products
from agent.search_agent import search_product_image
from agent.image_downloader import download_image
from report.generator import generate_report

console = Console()

_DELAY_BETWEEN_SEARCHES = 1.5  # seconds — be polite to DuckDuckGo


def main():
    parser = argparse.ArgumentParser(description="Generate a product image report.")
    parser.add_argument("products_file", help="Path to the products TXT file")
    parser.add_argument("company_name", help="Company name for the report header")
    parser.add_argument(
        "--output", default="output/report.html", help="Output HTML file path"
    )
    args = parser.parse_args()

    if not Path(args.products_file).exists():
        console.print(f"[red]File not found:[/red] {args.products_file}")
        sys.exit(1)

    # ── Parse ─────────────────────────────────────────────────
    products = parse_products(args.products_file)
    console.print(
        Panel(
            Text.assemble(
                ("Empresa: ", "bold"),
                (args.company_name, "cyan"),
                "\n",
                ("Produtos: ", "bold"),
                (str(len(products)), "green"),
            ),
            title="[bold blue]Virgil — Relatório de Produtos",
            expand=False,
        )
    )

    # ── Search + Download ──────────────────────────────────────
    found = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Buscando imagens...", total=len(products))

        for product in products:
            progress.update(
                task,
                description=f"#{product.number:02d} {product.description[:45]}…",
            )

            image_url = search_product_image(product.description, product.reference)

            if image_url:
                product.image_url = image_url
                local_path = download_image(image_url, product.number)
                if local_path:
                    product.image_path = local_path
                    found += 1

            progress.advance(task)
            time.sleep(_DELAY_BETWEEN_SEARCHES)

    console.print(
        f"\n[green]✓[/green] Imagens encontradas: [bold]{found}/{len(products)}[/bold]"
    )

    # ── Generate Report ────────────────────────────────────────
    output = generate_report(args.company_name, products, args.output)
    console.print(f"[green]✓[/green] Relatório gerado: [bold cyan]{output}[/bold cyan]")
    console.print("\nAbra o arquivo no navegador e clique em [bold]Exportar PDF[/bold].\n")


if __name__ == "__main__":
    main()
