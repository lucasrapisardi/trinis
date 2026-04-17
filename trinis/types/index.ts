// PATH: src/types/index.ts
// ── Auth ─────────────────────────────────────────────────────────────────
export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  tenant_id: string;
  is_owner: boolean;
  access_token: string;
  refresh_token: string;
}

// ── Tenant ────────────────────────────────────────────────────────────────
export type PlanName = "free" | "pro" | "business";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: PlanName;
  products_synced_this_month: number;
  plan_limit: number;
  payment_past_due: boolean;
  created_at: string;
}

// ── Shopify Store ─────────────────────────────────────────────────────────
export interface ShopifyStore {
  id: string;
  shop_domain: string;
  is_active: boolean;
  webhooks_registered: boolean;
  connected_at: string;
  last_synced_at: string | null;
}

// ── Vendor Config ─────────────────────────────────────────────────────────
export interface VendorConfig {
  id: string;
  name: string;
  base_url: string;
  categoria: string | null;
  subcategoria: string | null;
  pagina_especifica: string | null;
  brand_name: string | null;
  price_multiplier: number;
  sync_schedule: string | null;
  is_active: boolean;
  created_at: string;
}

// ── Job ───────────────────────────────────────────────────────────────────
export type JobStatus = "queued" | "running" | "done" | "failed" | "cancelled";

export interface Job {
  id: string;
  status: JobStatus;
  products_scraped: number;
  products_enriched: number;
  products_pushed: number;
  products_failed: number;
  progress_pct: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  attempt: number;
}

export interface JobLog {
  line: number;
  level: "info" | "warn" | "error";
  message: string;
  ts: string;
}

// ── Dashboard ─────────────────────────────────────────────────────────────
export interface DashboardSummary {
  products_synced_this_month: number;
  plan_limit: number;
  plan: PlanName;
  jobs_this_month: number;
  jobs_failed_this_month: number;
  running_jobs: number;
  last_sync_at: string | null;
}
