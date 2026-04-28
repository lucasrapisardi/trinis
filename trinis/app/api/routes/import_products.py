"""
Product import via CSV or XML.
"""
import csv
import io
import uuid
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user, get_current_tenant
from app.db.session import get_db
from app.models.models import Tenant, User, ShopifyStore

router = APIRouter(prefix="/import", tags=["import"])

TEMPLATE_FIELDS = ["nome", "descricao", "preco", "ean", "imagem_url", "categoria", "tags"]
REQUIRED_FIELDS = {"nome", "descricao", "preco"}


@router.get("/template/csv")
async def download_csv_template():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TEMPLATE_FIELDS)
    writer.writeheader()
    writer.writerow({
        "nome": "Exemplo: Camiseta Azul Tamanho M",
        "descricao": "Descrição do produto aqui",
        "preco": "49.90",
        "ean": "7891234567890",
        "imagem_url": "https://exemplo.com/imagem.jpg",
        "categoria": "Roupas",
        "tags": "camiseta,azul,masculino",
    })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=productsync_template.csv"},
    )


@router.get("/template/xml")
async def download_xml_template():
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<products>
  <product>
    <nome>Exemplo: Camiseta Azul Tamanho M</nome>
    <descricao>Descrição do produto aqui</descricao>
    <preco>49.90</preco>
    <ean>7891234567890</ean>
    <imagem_url>https://exemplo.com/imagem.jpg</imagem_url>
    <categoria>Roupas</categoria>
    <tags>camiseta,azul,masculino</tags>
  </product>
</products>
'''
    return StreamingResponse(
        iter([xml_content]),
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=productsync_template.xml"},
    )


@router.post("/parse")
async def parse_import_file(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
):
    content = await file.read()
    filename = file.filename or ""

    try:
        if filename.endswith(".csv"):
            products = _parse_csv(content)
        elif filename.endswith(".xml"):
            products = _parse_xml(content)
        else:
            raise HTTPException(400, "Unsupported file format. Use .csv or .xml")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to parse file: {str(e)}")

    errors = _validate_products(products)

    return {
        "total": len(products),
        "valid": len(products) - len(errors),
        "errors": errors,
        "preview": products[:5],
        "products": products,
    }


@router.post("/run")
async def run_import(
    payload: dict,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    products = payload.get("products", [])
    store_id = payload.get("store_id")
    enrich = payload.get("enrich", True)
    ai_model = payload.get("ai_model", "gpt-4o-mini")

    if not products:
        raise HTTPException(400, "No products provided")
    if not store_id:
        raise HTTPException(400, "store_id is required")

    # Validate store belongs to tenant
    store_result = await db.execute(
        select(ShopifyStore).where(
            ShopifyStore.id == uuid.UUID(store_id),
            ShopifyStore.tenant_id == tenant.id,
            ShopifyStore.is_active == True,
        )
    )
    if not store_result.scalar_one_or_none():
        raise HTTPException(404, "Store not found or not connected")

    # Create job record
    from app.models.models import Job, JobStatus, VendorConfig
    job = Job(
        tenant_id=tenant.id,
        store_id=uuid.UUID(store_id),
        status=JobStatus.queued,
        product_limit=len(products),
        ai_model=ai_model,
        skip_existing=False,
    )
    db.add(job)
    await db.flush()
    await db.commit()

    # Dispatch to Celery
    from app.tasks.import_task import import_products
    import_products.apply_async(
        args=[str(job.id), str(tenant.id), products, enrich],
        queue="scrape",
    )

    return {"job_id": str(job.id), "total": len(products), "enrich": enrich}


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    products = []
    for row in reader:
        # Skip example rows
        if row.get("nome", "").startswith("Exemplo:"):
            continue
        products.append({k.strip(): v.strip() for k, v in row.items() if k in TEMPLATE_FIELDS})
    return products


def _parse_xml(content: bytes) -> list[dict]:
    root = ET.fromstring(content)
    products = []
    for product_el in root.findall("product"):
        product = {}
        for field in TEMPLATE_FIELDS:
            el = product_el.find(field)
            if el is not None and el.text:
                product[field] = el.text.strip()
        if product:
            products.append(product)
    return products


def _validate_products(products: list[dict]) -> list[dict]:
    errors = []
    for i, p in enumerate(products):
        missing = REQUIRED_FIELDS - set(p.keys())
        if missing:
            errors.append({"row": i + 1, "error": f"Missing required fields: {', '.join(missing)}"})
        elif not p.get("nome"):
            errors.append({"row": i + 1, "error": "Field 'nome' is empty"})
        elif not p.get("preco"):
            errors.append({"row": i + 1, "error": "Field 'preco' is empty"})
    return errors
