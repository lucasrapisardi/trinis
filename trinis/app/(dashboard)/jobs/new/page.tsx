// PATH: src/app/(dashboard)/jobs/new/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { vendorApi, storesApi, jobsApi } from "@/lib/api";
import type { VendorConfig, ShopifyStore } from "@/types";

type ScheduleType = "now" | "later";

export default function NewJobPage() {
  const router = useRouter();
  const [vendors, setVendors] = useState<VendorConfig[]>([]);
  const [stores, setStores] = useState<ShopifyStore[]>([]);
  const [vendorId, setVendorId] = useState("");
  const [storeId, setStoreId] = useState("");
  const [scheduleType, setScheduleType] = useState<ScheduleType>("now");
  const [scheduledAt, setScheduledAt] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    vendorApi.list().then((r) => setVendors(r.data)).catch(() => null);
    storesApi.list().then((r) => setStores(r.data)).catch(() => null);

    // Default scheduled time to 1 hour from now
    const oneHourFromNow = new Date(Date.now() + 60 * 60 * 1000);
    const local = new Date(oneHourFromNow.getTime() - oneHourFromNow.getTimezoneOffset() * 60000);
    setScheduledAt(local.toISOString().slice(0, 16));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!vendorId || !storeId) return;
    setLoading(true);
    try {
      const r = await jobsApi.create(
        vendorId,
        storeId,
        limitType === "custom" ? productLimit : null,
        scheduleType === "later" ? new Date(scheduledAt).toISOString() : null,
      );
      router.push(`/jobs/${r.data.id}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })
        ?.response?.data?.detail;
      if (detail && typeof detail === "object" && "code" in detail) {
        const d = detail as { code: string; upgrade_url: string };
        if (d.code === "plan_limit_reached") {
          toast.error("Plan limit reached — please upgrade your plan");
          router.push(d.upgrade_url);
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
            <select
              className="input text-sm"
              value={vendorId}
              onChange={(e) => setVendorId(e.target.value)}
              required
            >
              <option value="">Select a vendor…</option>
              {vendors.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                  {v.categoria ? ` — ${v.categoria}` : ""}
                  {v.subcategoria ? `/${v.subcategoria}` : ""}
                </option>
              ))}
            </select>
            {vendors.length === 0 && (
              <p className="text-[10px] text-amber-600 mt-1">
                No vendors configured.{" "}
                <a href="/settings" className="underline">Add one in Settings →</a>
              </p>
            )}
          </div>

          {/* Store */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Shopify store</label>
            <select
              className="input text-sm"
              value={storeId}
              onChange={(e) => setStoreId(e.target.value)}
              required
            >
              <option value="">Select a store…</option>
              {stores.filter((s) => s.is_active).map((s) => (
                <option key={s.id} value={s.id}>{s.shop_domain}</option>
              ))}
            </select>
            {stores.length === 0 && (
              <p className="text-[10px] text-amber-600 mt-1">
                No stores connected.{" "}
                <a href="/stores" className="underline">Connect one →</a>
              </p>
            )}
          </div>

          {/* Schedule */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">When to run</label>
            <div className="flex gap-2 mb-2">
              <button
                type="button"
                onClick={() => setScheduleType("now")}
                className={`flex-1 py-2 text-xs rounded-lg border transition-colors ${
                  scheduleType === "now"
                    ? "bg-brand-600 text-brand-50 border-brand-600"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                Start immediately
              </button>
              <button
                type="button"
                onClick={() => setScheduleType("later")}
                className={`flex-1 py-2 text-xs rounded-lg border transition-colors ${
                  scheduleType === "later"
                    ? "bg-brand-600 text-brand-50 border-brand-600"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                Schedule for later
              </button>
            </div>

            {scheduleType === "later" && (
              <div>
                <input
                  type="datetime-local"
                  className="input text-sm"
                  value={scheduledAt}
                  onChange={(e) => setScheduledAt(e.target.value)}
                  min={new Date(Date.now() + 60000).toISOString().slice(0, 16)}
                  required
                />
                <p className="text-[10px] text-gray-400 mt-1">
                  Job will be queued at the selected time.
                </p>
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

          <button
            type="submit"
            disabled={loading || !vendorId || !storeId}
            className="btn btn-primary w-full justify-center text-sm"
          >
            {loading
              ? "Starting…"
              : scheduleType === "now"
              ? "Start sync →"
              : "Schedule sync →"}
          </button>
        </form>
      </div>
    </div>
  );
}
