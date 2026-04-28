// PATH: src/app/(dashboard)/stores/page.tsx
"use client";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";
import toast from "react-hot-toast";
import api, { storesApi } from "@/lib/api";
import type { ShopifyStore } from "@/types";

export default function StoresPage() {
  const [stores, setStores] = useState<ShopifyStore[]>([]);
  const [domain, setDomain] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [limitError, setLimitError] = useState(false);
  const [tenant, setTenant] = useState<any>(null);
  const storeLimits: Record<string, number> = { free: 1, starter: 2, pro: 5, business: 999 };
  const atLimit = tenant ? stores.filter((s: any) => s.is_active).length >= (storeLimits[tenant.plan] ?? 1) : false;
  const t = useTranslations("stores");
  const [runningTask, setRunningTask] = useState<string | null>(null);

  async function handleReconnect(shopDomain: string) {
    try {
      const r = await api.post("/stores/connect", null, { params: { shop_domain: shopDomain } });
      window.location.href = r.data.oauth_url;
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: { code?: string; message?: string } | string } } })?.response?.data?.detail;
      if (typeof detail === "object" && detail?.code === "store_limit_reached") {
        toast.error(detail.message || "Store limit reached for your plan. Upgrade to connect more stores.");
      } else {
        toast.error(typeof detail === "string" ? detail : "Failed to reconnect store");
      }
    }
  }


  async function handleRunTask(storeId: string, task: string) {
    setRunningTask(`${storeId}-${task}`);
    try {
      await api.post(`/stores/${storeId}/tasks/${task}`);
      toast.success(`${task} task queued for entire store!`);
    } catch {
      toast.error(`Failed to run ${task}`);
    } finally {
      setRunningTask(null);
    }
  }

  useEffect(() => {
    storesApi.list().then((r) => setStores(r.data)).catch(() => null);
    api.get("/tenant").then((r) => {
      setTenant(r.data);
      const storeLimits: Record<string, number> = { free: 1, starter: 2, pro: 5, business: 999 };
      const limit = storeLimits[r.data.plan] ?? 1;
      // will be checked after stores load
    }).catch(() => null);
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!domain) return;
    setConnecting(true);
    // Sanitize domain
    const cleanDomain = domain
      .replace(/https?:\/\//, "")
      .replace(/\.myshopify\.com.*$/, "")
      .replace(/\/$/, "")
      .trim();
    try {
      const r = await storesApi.initiateOAuth(cleanDomain);
      // Redirect to Shopify OAuth
      window.location.href = r.data.redirect_url;
    } catch {
      toast.error("Failed to initiate store connection");
      setConnecting(false);
    }
  }

  async function handleDisconnect(storeId: string, storeDomain: string) {
    if (!confirm(`Disconnect ${storeDomain}?`)) return;
    try {
      await storesApi.disconnect(storeId);
      setStores((prev) => prev.filter((s) => s.id !== storeId));
      toast.success("Store disconnected");
    } catch {
      toast.error("Failed to disconnect store");
    }
  }

  return (
    <div className="p-5 max-w-2xl mx-auto space-y-5">
      <h1 className="text-base font-medium text-gray-900">Connected stores</h1>

      {/* Connect form */}
      <div className="card">
        <h2 className="text-xs font-medium text-gray-700 mb-3">
          Connect a new store
        </h2>
        {(() => {
          const storeLimits: Record<string, number> = { free: 1, starter: 2, pro: 5, business: 999 };
          const limit = tenant ? (storeLimits[tenant.plan] ?? 1) : 999;
          const activeStores = stores.filter((s: any) => s.is_active).length;
          if (activeStores >= limit) return (
            <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3">
              <span className="text-amber-500 text-lg flex-shrink-0">⚠️</span>
              <div className="flex-1">
                <p className="text-xs font-medium text-gray-800">Store limit reached</p>
                <p className="text-[10px] text-gray-500 mt-0.5">Your {tenant?.plan} plan allows up to {limit} store(s). Upgrade to connect more.</p>
                <a href="/billing" className="inline-block mt-2 text-xs font-medium text-white bg-brand-600 px-3 py-1.5 rounded-lg hover:bg-brand-700 transition-colors">
                  Upgrade plan →
                </a>
              </div>
            </div>
          );
          return null;
        })()}
        <form onSubmit={handleConnect} className={clsx("flex gap-2 transition-opacity", atLimit && "opacity-40 pointer-events-none select-none")}>
          <div className="flex flex-1 items-center border border-gray-200 rounded-lg overflow-hidden">
            <input
              className="flex-1 h-9 px-3 text-sm outline-none bg-white"
              placeholder="your-store"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              required
            />
            <span className="px-3 text-xs text-gray-400 border-l border-gray-200 h-9 flex items-center bg-gray-50 whitespace-nowrap">
              .myshopify.com
            </span>
          </div>
          <button
            type="submit"
            disabled={connecting}
            className="btn btn-primary text-xs whitespace-nowrap"
          >
            {connecting ? "Redirecting…" : "Conectar →"}
          </button>
        </form>
        <p className="text-[10px] text-gray-400 mt-2">
          You&apos;ll be redirected to Shopify to approve access.
        </p>
      </div>

      {/* Store list */}
      {stores.length > 0 && (
        <div className="card p-0 overflow-hidden">
          {stores.map((store, i) => (
            <div
              key={store.id}
              className={clsx(
                "flex items-center gap-3 px-4 py-3",
                i < stores.length - 1 && "border-b border-gray-100"
              )}
            >
              <div
                className={clsx(
                  "w-2 h-2 rounded-full flex-shrink-0",
                  store.is_active ? "bg-teal-500" : "bg-amber-500"
                )}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">
                  {store.shop_domain}
                </p>
                <p className="text-[10px] text-gray-400">
                  Connected{" "}
                  {formatDistanceToNow(new Date(store.connected_at), {
                    addSuffix: true,
                  })}
                  {store.last_synced_at &&
                    ` · last sync ${formatDistanceToNow(new Date(store.last_synced_at), { addSuffix: true })}`}
                </p>
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                {store.webhooks_registered ? (
                  <span className="text-teal-600">webhooks ✓</span>
                ) : (
                  <span className="text-amber-500">webhooks pending</span>
                )}
                {store.is_active ? (
                  <div className="flex gap-1">
                    <button onClick={() => handleRunTask(store.id, "sku")} disabled={runningTask === `${store.id}-sku`} className="btn text-[10px] py-0.5 px-2" title="Generate SKUs">
                      {runningTask === `${store.id}-sku` ? "…" : "SKU"}
                    </button>
                    <button onClick={() => handleRunTask(store.id, "tags")} disabled={runningTask === `${store.id}-tags`} className="btn text-[10px] py-0.5 px-2" title="Update tags">
                      {runningTask === `${store.id}-tags` ? "…" : "Tags"}
                    </button>
                    <button onClick={() => handleRunTask(store.id, "pricing")} disabled={runningTask === `${store.id}-pricing`} className="btn text-[10px] py-0.5 px-2" title="Recalculate prices">
                      {runningTask === `${store.id}-pricing` ? "…" : "Pricing"}
                    </button>
                    <button onClick={() => handleDisconnect(store.id, store.shop_domain)} className="btn btn-danger text-[10px] py-0.5 px-2">
                      Disconnect
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => handleReconnect(store.shop_domain)}
                    className="btn text-[10px] py-0.5 px-2 text-brand-600"
                  >
                    Reconnect →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {stores.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-6">
          No stores connected yet.
        </p>
      )}
    </div>
  );
}
