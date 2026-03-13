import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path("projects")


@dataclass
class CompanyInfo:
    name: str = ""
    cnpj: str = ""
    logo_path: str = ""


@dataclass
class ProductEntry:
    number: int = 0
    description: str = ""
    reference: str = ""
    image_path: str = ""
    image_url: str = ""
    custom_image: bool = False


@dataclass
class Project:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    company: CompanyInfo = field(default_factory=CompanyInfo)
    products: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return {
            "id": self.id,
            "company": asdict(self.company),
            "products": [asdict(p) for p in self.products],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def save_project(project: Project):
    project.updated_at = datetime.now().isoformat()
    project_dir = PROJECTS_DIR / project.id
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / "project.json"
    content = json.dumps(project.to_dict(), ensure_ascii=False, indent=2)
    # Escrita atômica: grava em .tmp e renomeia — evita JSON corrompido em leituras concorrentes
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_project(project_id: str):
    path = PROJECTS_DIR / project_id / "project.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    company = CompanyInfo(**data.get("company", {}))
    products = [ProductEntry(**p) for p in data.get("products", [])]
    return Project(
        id=data["id"],
        company=company,
        products=products,
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
    )


def list_projects():
    result = []
    if not PROJECTS_DIR.exists():
        return result
    for d in sorted(PROJECTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        path = d / "project.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        result.append({
            "id": data["id"],
            "company_name": data.get("company", {}).get("name", "Sem nome"),
            "cnpj": data.get("company", {}).get("cnpj", ""),
            "product_count": len(data.get("products", [])),
            "updated_at": data.get("updated_at", ""),
            "has_logo": bool(data.get("company", {}).get("logo_path")),
        })
    return result
