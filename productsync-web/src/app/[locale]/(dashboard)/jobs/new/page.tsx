// PATH: src/app/(dashboard)/jobs/new/page.tsx
"use client";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import clsx from "clsx";
import api, { vendorApi, storesApi, jobsApi } from "@/lib/api";
import type { VendorConfig, ShopifyStore } from "@/types";

type ScheduleType = "now" | "later";
type LimitType = "all" | "custom";
type LimitType = "all" | "custom";

export default function NewJobPage() {
  const router = useRouter();
  const [vendors, setVendors] = useState<VendorConfig[]>([]);
  const [stores, setStores] = useState<ShopifyStore[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [storeId, setStoreId] = useState("");
  const [scheduleType, setScheduleType] = useState<ScheduleType | null>(null);
  const [scheduledAt, setScheduledAt] = useState("");
  const [limitType, setLimitType] = useState<LimitType | null>(null);
  const [productLimit, setProductLimit] = useState(50);
  const [loading, setLoading] = useState(false);
  const [planJobLimit, setPlanJobLimit] = useState<number | null>(null);
  const [skipExisting, setSkipExisting] = useState(true);
  const t = useTranslations("jobs");
  const [workersOnline, setWorkersOnline] = useState<boolean | null>(null);

  const selectedVendor = vendors.find((v) => v.id === vendorId);

  useEffect(() => {
    api.get("/tenant").then((r) => {
      const limits: Record<string, number | null> = { free: 10, starter: 50, pro: null, business: null };
      setPlanJobLimit(limits[r.data.plan] ?? null);
    }).catch(() => null);
  }, []);

  useEffect(() => {
    vendorApi.list().then((r) => setVendors(r.data)).catch(() => null);
    storesApi.list().then((r) => setStores(r.data)).catch(() => null);
    // Check if workers are online
    api.get("/jobs/workers/status").then((r) => {
      setWorkersOnline(r.data.online);
    }).catch(() => setWorkersOnline(false));

    const oneHourFromNow = new Date(Date.now() + 60 * 60 * 1000);
    const local = new Date(oneHourFromNow.getTime() - oneHourFromNow.getTimezoneOffset() * 60000);
    setScheduledAt(local.toISOString().slice(0, 16));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!vendorId || !storeId) return;
    setLoading(true);
    try {
      const payload = {
        vendor_config_id: vendorId,
        store_id: storeId,
        product_limit: limitType === "custom" ? productLimit : null,
        skip_existing: skipExisting,
        scheduled_at: scheduleType === "later" ? new Date(scheduledAt).toISOString() : null,
      };
      const r = await jobsApi.create(payload.vendor_config_id, payload.store_id, payload.product_limit, payload.scheduled_at);
      toast.success(scheduleType === "now" ? "Sync job queued!" : `Job scheduled for ${new Date(scheduledAt).toLocaleString()}`);
      router.push(`/jobs/${r.data.id}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (detail && typeof detail === "object" && "code" in detail) {
        const d = detail as { code: string; upgrade_url: string; is_free_plan: boolean; message: string };
        if (d.code === "plan_limit_reached") {
          if (d.is_free_plan) {
            toast.error("Free plan limit reached — upgrade or cancel your account");
            router.push("/billing");
          } else {
            toast.error(d.message || "Plan limit reached — please upgrade");
            router.push(d.upgrade_url);
          }
          return;
        }
      }
      toast.error("Failed to create job");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-5 max-w-md mx-auto">
      <div className="flex items-center gap-3 mb-5">
        <a href="/jobs" className="text-gray-400 hover:text-gray-600 text-sm">←</a>
        <h1 className="text-base font-medium text-gray-900">New sync</h1>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Vendor */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Vendor source</label>
            <select className="input text-sm" value={vendorId} onChange={(e) => setVendorId(e.target.value)} required>
              <option value="">Select a vendor…</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}{v.categoria ? ` — ${v.categoria}` : ""}{v.subcategoria ? `/${v.subcategoria}` : ""}
                </option>
              ))}
            </select>
            {selectedVendor && (
              <p className="text-[10px] text-gray-400 mt-1">
                Scope: <span className="font-medium capitalize text-brand-600">{selectedVendor.scrape_scope ?? "pagina"}</span>
                {selectedVendor.categoria && ` · ${selectedVendor.categoria}`}
                {selectedVendor.subcategoria && `/${selectedVendor.subcategoria}`}
                {selectedVendor.pagina_especifica && `/${selectedVendor.pagina_especifica}`}
              </p>
            )}
            {vendors.length === 0 && (
              <p className="text-[10px] text-amber-600 mt-1">No vendors configured. <a href="/settings" className="underline">Add one →</a></p>
            )}
          </div>

          {/* Store */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Shopify store</label>
            <select className="input text-sm" value={storeId} onChange={(e) => setStoreId(e.target.value)} required>
              <option value="">Select a store…</option>
              {stores.filter((s) => s.is_active).map((s) => (
                <option key={s.id} value={s.id}>{s.shop_domain}</option>
              ))}
            </select>
            {stores.length === 0 && (
              <p className="text-[10px] text-amber-600 mt-1">No stores connected. <a href="/stores" className="underline">Connect one →</a></p>
            )}
          </div>

          {/* Product limit */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Products to sync</label>
            <div className="flex gap-2 mb-2">
              <button type="button" onClick={() => setLimitType("all")} className={clsx("flex-1 py-2 text-xs rounded-lg border transition-colors", limitType === "all" ? "bg-brand-600 text-brand-50 border-brand-600" : limitType === null ? "bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600" : "bg-white text-gray-400 border-gray-200 hover:bg-gray-50")}>
                All products
              </button>
              <button type="button" onClick={() => setLimitType("custom")} className={clsx("flex-1 py-2 text-xs rounded-lg border transition-colors", limitType === "custom" ? "bg-brand-600 text-brand-50 border-brand-600" : limitType === null ? "bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600" : "bg-white text-gray-400 border-gray-200 hover:bg-gray-50")}>
                Custom limit
              </button>
            </div>
            {limitType === "custom" && planJobLimit && (
                <p className="text-[10px] text-amber-600 mt-1">
                  Your plan allows up to {planJobLimit} products per job.
                </p>
              )}
              {limitType === "custom" && (
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  className="input text-sm w-28"
                  min={1}
                  max={10000}
                  step={1}
                  value={productLimit}
                  onChange={(e) => setProductLimit(parseInt(e.target.value) || 1)}
                />
                <span className="text-xs text-gray-400">products max</span>
              </div>
            )}
          </div>

          {/* Schedule */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">When to run</label>
            <div className="flex gap-2 mb-2">
              <button type="button" onClick={() => setScheduleType("now")} className={clsx("flex-1 py-2 text-xs rounded-lg border transition-colors", scheduleType === "now" ? "bg-brand-600 text-brand-50 border-brand-600" : scheduleType === null ? "bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600" : "bg-white text-gray-400 border-gray-200 hover:bg-gray-50")}>
                Start immediately
              </button>
              <button type="button" onClick={() => setScheduleType("later")} className={clsx("flex-1 py-2 text-xs rounded-lg border transition-colors", scheduleType === "later" ? "bg-brand-600 text-brand-50 border-brand-600" : scheduleType === null ? "bg-white text-gray-400 border-gray-200 hover:bg-gray-50 hover:text-gray-600" : "bg-white text-gray-400 border-gray-200 hover:bg-gray-50")}>
                Schedule for later
              </button>
            </div>
            {scheduleType === null && <p className="text-[10px] text-gray-400 mt-1">Please select when to run this sync.</p>}
            {scheduleType === "later" && (
              <div>
                <input type="datetime-local" className="input text-sm" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} min={new Date(Date.now() + 60000).toISOString().slice(0, 16)} required />
                <p className="text-[10px] text-gray-400 mt-1">Job will be queued at the selected time.</p>
              </div>
            )}
          </div>

          {/* Pipeline summary */}
          <div className="bg-gray-50 rounded-lg px-3 py-2.5 text-xs text-gray-500 space-y-1">
            <p className="font-medium text-gray-600">This will run:</p>
            <p>1. Scrape products from the vendor</p>
            <p>2. Enrich descriptions + SEO with GPT-4o</p>
            <p>3. Upgrade images with gpt-image-1</p>
            <p>4. Push to your Shopify store</p>
          </div>

          {/* Worker status warning */}
          {workersOnline === false && (
            <div className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5 text-xs text-amber-700 flex items-start gap-2">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="flex-shrink-0 mt-0.5"><path d="M7 1L13 12H1L7 1Z" stroke="#B45309" strokeWidth="1.2" strokeLinejoin="round"/><line x1="7" y1="5" x2="7" y2="8" stroke="#B45309" strokeWidth="1.2" strokeLinecap="round"/><circle cx="7" cy="10" r="0.6" fill="#B45309"/></svg>
              <div>
                <p className="font-medium">Sync service temporarily unavailable</p>
                <p className="text-amber-600 mt-0.5">Your job will be queued and will start automatically once the service is back online.</p>
              </div>
            </div>
          )}

          {/* Skip existing checkbox */}
          <div className="card">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={skipExisting}
                onChange={(e) => setSkipExisting(e.target.checked)}
                className="mt-0.5 accent-brand-600"
              />
              <div>
                <p className="text-xs font-medium text-gray-700">Skip existing products</p>
                <p className="text-[10px] text-gray-400 mt-0.5">
                  Products already synced will reuse cached descriptions and images, saving time and AI costs.
                  Disable to force re-enrichment of all products.
                </p>
              </div>
            </label>
          </div>

          <button type="submit" disabled={loading || !vendorId || !storeId || !scheduleType || !limitType} className="btn btn-primary w-full justify-center text-sm">
            {loading ? "Starting…" : scheduleType === "now" ? t("startSync") : t("scheduleSync")}
          </button>
        </form>
      </div>
    </div>
  );
}
