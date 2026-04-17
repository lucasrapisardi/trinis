#!/bin/bash
echo "🚀 Starting ProductSync dev environment..."

# Infrastructure
sudo service postgresql start
sudo service redis start
cd ~/trinis_ai/trinis && docker-compose up minio -d
echo "✅ PostgreSQL + Redis + MinIO started"

echo ""
echo "Now open 5 terminals and run:"
echo ""
echo "  Terminal 1 (API):"
echo "    cd ~/trinis_ai/trinis && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "  Terminal 2 (Celery Worker):"
echo "    cd ~/trinis_ai/trinis && source venv/bin/activate && celery -A app.tasks.celery_app worker --loglevel=info -Q scrape,enrich,image,sync,default"
echo ""
echo "  Terminal 3 (Celery Beat — scheduled jobs):"
echo "    cd ~/trinis_ai/trinis && source venv/bin/activate && celery -A app.tasks.celery_app beat --loglevel=info"
echo ""
echo "  Terminal 4 (Frontend):"
echo "    cd ~/trinis_ai/productsync-web && npm run dev"
echo ""
echo "  Terminal 5 (ngrok — Shopify OAuth + Stripe webhooks):"
echo "    ngrok http 8000"
echo ""
echo "  Terminal 6 (Stripe webhook listener):"
echo "    stripe listen --forward-to http://localhost:8000/api/billing/webhook"