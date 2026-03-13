#!/usr/bin/env python3
"""Virgil — Interface gráfica web para geração de catálogos de produtos."""

import io
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

import requests
import uvicorn
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image as PilImage

sys.path.insert(0, str(Path(__file__).parent))

from agent.search_agent import search_product_image
from core.project import (
    CompanyInfo,
    ProductEntry,
    Project,
    load_project,
    list_projects,
    save_project,
)
from product_parser import parse_products, parse_text
from report.generator import generate_report

PROJECTS_DIR = Path("projects")
PROJECTS_DIR.mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)

_DL_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def _download_to(url: str, dest: Path) -> bool:
    """Baixa uma imagem diretamente para dest. Retorna True se bem-sucedido."""
    try:
        resp = requests.get(url, timeout=10, headers=_DL_HEADERS)
        resp.raise_for_status()
        img = PilImage.open(io.BytesIO(resp.content)).convert("RGB")
        img.thumbnail((600, 600), PilImage.LANCZOS)
        img.save(dest, format="JPEG", quality=85)
        return True
    except Exception as e:
        print(f"  [download] {e}")
        return False

app = FastAPI(title="Virgil")

# Track search progress: project_id -> {total, done, status}
_search_progress: dict = {}

# ── Static files ──────────────────────────────────────────────
app.mount("/projects-data", StaticFiles(directory="projects"), name="projects-data")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


# ── Projects ──────────────────────────────────────────────────

@app.get("/api/projects")
def get_projects():
    return list_projects()


@app.post("/api/projects")
async def create_project(
    name: str = Form(""),
    cnpj: str = Form(""),
    logo: UploadFile = File(None),
):
    project = Project()
    project.company.name = name
    project.company.cnpj = cnpj

    project_dir = PROJECTS_DIR / project.id
    project_dir.mkdir(parents=True)
    (project_dir / "images").mkdir()

    if logo and logo.filename:
        logo_ext = Path(logo.filename).suffix or ".png"
        logo_path = project_dir / f"logo{logo_ext}"
        logo_path.write_bytes(await logo.read())
        project.company.logo_path = str(logo_path)

    save_project(project)
    return {"id": project.id, "project": project.to_dict()}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    return project.to_dict()


@app.put("/api/projects/{project_id}/company")
async def update_company(project_id: str, data: dict):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)
    project.company.name = data.get("name", project.company.name)
    project.company.cnpj = data.get("cnpj", project.company.cnpj)
    save_project(project)
    return {"ok": True}


@app.post("/api/projects/{project_id}/logo")
async def upload_logo(project_id: str, logo: UploadFile = File(...)):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)
    project_dir = PROJECTS_DIR / project_id
    logo_ext = Path(logo.filename).suffix or ".png"
    logo_path = project_dir / f"logo{logo_ext}"
    logo_path.write_bytes(await logo.read())
    project.company.logo_path = str(logo_path)
    save_project(project)
    return {"logo_url": f"/projects-data/{project_id}/logo{logo_ext}"}


# ── Products ──────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/products/add-txt")
async def add_products_txt(project_id: str, file: UploadFile = File(...)):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)

    tmp = Path(f"/tmp/virgil_{project_id}.txt")
    tmp.write_bytes(await file.read())
    new_products = parse_products(str(tmp))
    tmp.unlink(missing_ok=True)

    max_num = max((p.number for p in project.products), default=0)
    for np in new_products:
        entry = ProductEntry(
            number=max_num + np.number,
            description=np.description,
            reference=np.reference,
        )
        project.products.append(entry)

    save_project(project)
    return {"added": len(new_products), "total": len(project.products)}


@app.post("/api/projects/{project_id}/products/add-text")
async def add_products_text(project_id: str, data: dict):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)

    raw_text = data.get("text", "").strip()
    if not raw_text:
        raise HTTPException(400, "Texto vazio")

    new_products = parse_text(raw_text)
    if not new_products:
        raise HTTPException(400, "Nenhum produto encontrado no texto. Verifique o formato (ex: 1-Descrição do produto).")

    max_num = max((p.number for p in project.products), default=0)
    for np in new_products:
        entry = ProductEntry(
            number=max_num + np.number,
            description=np.description,
            reference=np.reference,
        )
        project.products.append(entry)

    save_project(project)
    return {"added": len(new_products), "total": len(project.products)}


@app.post("/api/projects/{project_id}/products/preview-text")
async def preview_text(project_id: str, data: dict):
    """Pré-visualiza quantos produtos seriam importados de um texto."""
    raw_text = data.get("text", "").strip()
    products = parse_text(raw_text) if raw_text else []
    return {
        "count": len(products),
        "preview": [{"number": p.number, "description": p.description[:80]} for p in products[:5]],
    }


@app.post("/api/projects/{project_id}/products/{product_num}/image")
async def replace_product_image(
    project_id: str,
    product_num: int,
    image: UploadFile = File(...),
):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)
    product = next((p for p in project.products if p.number == product_num), None)
    if not product:
        raise HTTPException(404, "Produto não encontrado")

    from PIL import Image as PilImage

    img_dir = PROJECTS_DIR / project_id / "images"
    img_dir.mkdir(exist_ok=True)
    dest = img_dir / f"product_{product_num:03d}.jpg"

    data = await image.read()
    img = PilImage.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((600, 600))
    img.save(dest, format="JPEG", quality=85)

    product.image_path = str(dest)
    product.custom_image = True
    save_project(project)

    return {"image_url": f"/projects-data/{project_id}/images/product_{product_num:03d}.jpg"}


@app.delete("/api/projects/{project_id}/products/{product_num}")
def delete_product(project_id: str, product_num: int):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)
    project.products = [p for p in project.products if p.number != product_num]
    save_project(project)
    return {"ok": True}


# ── Image search ──────────────────────────────────────────────

def _run_search(project_id: str):
    project = load_project(project_id)
    if not project:
        return

    targets = [p for p in project.products if not p.custom_image]
    _search_progress[project_id] = {
        "total": len(targets),
        "done": 0,
        "status": "running",
        "current": "",
    }

    img_dir = PROJECTS_DIR / project_id / "images"
    img_dir.mkdir(exist_ok=True)

    for i, product in enumerate(targets):
        _search_progress[project_id]["current"] = product.description[:50]
        try:
            url = search_product_image(product.description, product.reference)
            if url:
                product.image_url = url
                dest = img_dir / f"product_{product.number:03d}.jpg"
                if _download_to(url, dest):
                    product.image_path = str(dest)
        except Exception as e:
            print(f"  [search] product {product.number}: {e}")

        _search_progress[project_id]["done"] = i + 1
        save_project(project)
        time.sleep(1.5)

    _search_progress[project_id]["status"] = "done"


@app.post("/api/projects/{project_id}/search-images")
def start_search(project_id: str):
    if _search_progress.get(project_id, {}).get("status") == "running":
        return {"status": "already_running"}
    t = threading.Thread(target=_run_search, args=(project_id,), daemon=True)
    t.start()
    return {"status": "started"}


@app.get("/api/projects/{project_id}/search-progress")
def get_search_progress(project_id: str):
    return _search_progress.get(
        project_id, {"status": "idle", "total": 0, "done": 0, "current": ""}
    )


# ── Export ────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/export")
def export_report(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(404)
    output_path = f"output/report_{project_id}.html"
    generate_report(
        company_name=project.company.name,
        products=project.products,
        output_path=output_path,
        cnpj=project.company.cnpj,
        logo_path=project.company.logo_path,
    )
    return FileResponse(
        output_path,
        filename=f"relatorio_{project.company.name[:20].strip()}.html",
        media_type="text/html",
    )


# ── Run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Iniciando Virgil em http://localhost:8000 ...")
    webbrowser.open("http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
