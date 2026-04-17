# ProductSync

SaaS para sincronização de produtos entre fornecedores e Shopify.

## Estrutura

- `trinis/` — Backend (FastAPI + Celery + PostgreSQL + Redis + MinIO)
- `productsync-web/` — Frontend (Next.js + Tailwind)

## Setup

### Backend
```bash
cd trinis
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend
```bash
cd productsync-web
npm install
npm run dev
```

## Serviços necessários
- PostgreSQL
- Redis
- MinIO (docker-compose up minio -d)
- ngrok (para Shopify OAuth)
