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
  const t = useTranslations("stores");
  const [runningTask, setRunningTask] = useState<string | null>(null);

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
  }, []);

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!domain) return;
    setConnecting(true);
    try {
      const r = await storesApi.initiateOAuth(domain);
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
        <form onSubmit={handleConnect} className="flex gap-2">
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
                <div className="flex gap-1">
                  <button
                    onClick={() => handleRunTask(store.id, "sku")}
                    disabled={runningTask === `${store.id}-sku`}
                    className="btn text-[10px] py-0.5 px-2"
                    title="Generate SKUs for all products"
                  >
                    {runningTask === `${store.id}-sku` ? "…" : "SKU"}
                  </button>
                  <button
                    onClick={() => handleRunTask(store.id, "tags")}
                    disabled={runningTask === `${store.id}-tags`}
                    className="btn text-[10px] py-0.5 px-2"
                    title="Update tags for all products"
                  >
                    {runningTask === `${store.id}-tags` ? "…" : "Tags"}
                  </button>
                  <button
                    onClick={() => handleRunTask(store.id, "pricing")}
                    disabled={runningTask === `${store.id}-pricing`}
                    className="btn text-[10px] py-0.5 px-2"
                    title="Recalculate prices for all products"
                  >
                    {runningTask === `${store.id}-pricing` ? "…" : "Pricing"}
                  </button>
                  <button
                    onClick={() => handleDisconnect(store.id, store.shop_domain)}
                    className="btn btn-danger text-[10px] py-0.5 px-2"
                  >
                    Disconnect
                  </button>
                </div>
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
