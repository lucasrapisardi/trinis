// PATH: src/app/(dashboard)/settings/page.tsx
"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { vendorApi } from "@/lib/api";
import type { VendorConfig } from "@/types";

type Tab = "vendors" | "enrichment" | "schedule";

const TABS: { id: Tab; label: string }[] = [
  { id: "vendors",    label: "Vendor sources" },
  { id: "enrichment", label: "AI enrichment" },
  { id: "schedule",   label: "Sync schedule" },
];

const BLANK_VENDOR: Partial<VendorConfig> = {
  name: "",
  base_url: "https://www.comercialgomes.com.br",
  categoria: "",
  subcategoria: "",
  pagina_especifica: "",
  brand_name: "",
  price_multiplier: 2.0,
  sync_schedule: "0 2 * * *",
};

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("vendors");
  const [vendors, setVendors] = useState<VendorConfig[]>([]);
  const [editing, setEditing] = useState<Partial<VendorConfig> | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    vendorApi.list().then((r) => setVendors(r.data)).catch(() => null);
  }, []);

  async function handleSaveVendor() {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) {
        const r = await vendorApi.update(editing.id, editing);
        setVendors((prev) => prev.map((v) => v.id === editing.id ? r.data : v));
        toast.success("Vendor updated");
      } else {
        const r = await vendorApi.create(editing);
        setVendors((prev) => [...prev, r.data]);
        toast.success("Vendor added");
      }
      setEditing(null);
    } catch {
      toast.error("Failed to save vendor");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteVendor(id: string) {
    if (!confirm("Delete this vendor config?")) return;
    try {
      await vendorApi.delete(id);
      setVendors((prev) => prev.filter((v) => v.id !== id));
      toast.success("Vendor deleted");
    } catch {
      toast.error("Failed to delete vendor");
    }
  }

  return (
    <div className="p-5 max-w-3xl mx-auto">
      <h1 className="text-base font-medium text-gray-900 mb-5">Settings</h1>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={clsx(
              "px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors",
              tab === id
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-400 hover:text-gray-600"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Vendors tab ─────────────────────────────────────── */}
      {tab === "vendors" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-xs text-gray-400">
              Configure the vendor sites to scrape products from.
            </p>
            <button
              onClick={() => setEditing({ ...BLANK_VENDOR })}
              className="btn btn-primary text-xs"
            >
              + Add vendor
            </button>
          </div>

          {/* Vendor list */}
          {vendors.length > 0 && (
            <div className="card p-0 overflow-hidden">
              {vendors.map((v, i) => (
                <div
                  key={v.id}
                  className={clsx(
                    "flex items-center gap-3 px-4 py-3",
                    i < vendors.length - 1 && "border-b border-gray-100"
                  )}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{v.name}</p>
                    <p className="text-[10px] text-gray-400 truncate">{v.base_url}</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>{v.price_multiplier}x</span>
                    {v.sync_schedule && <span className="font-mono">{v.sync_schedule}</span>}
                    <span className={clsx(
                      "badge",
                      v.is_active ? "badge-done" : "badge-queued"
                    )}>
                      {v.is_active ? "active" : "paused"}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditing(v)}
                      className="btn text-[10px] py-0.5 px-2"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteVendor(v.id)}
                      className="btn btn-danger text-[10px] py-0.5 px-2"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {vendors.length === 0 && !editing && (
            <p className="text-sm text-gray-400 text-center py-8">
              No vendors configured yet.
            </p>
          )}

          {/* Vendor form */}
          {editing && (
            <div className="card space-y-3">
              <h2 className="text-xs font-medium text-gray-700">
                {editing.id ? "Edit vendor" : "New vendor"}
              </h2>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Name</label>
                  <input
                    className="input text-xs"
                    value={editing.name ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, name: e.target.value }))}
                    placeholder="Comercial Gomes"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Brand name</label>
                  <input
                    className="input text-xs"
                    value={editing.brand_name ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, brand_name: e.target.value }))}
                    placeholder="Dimora Mediterranea"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-[10px] text-gray-400 mb-1">Base URL</label>
                  <input
                    className="input text-xs"
                    value={editing.base_url ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, base_url: e.target.value }))}
                    placeholder="https://www.comercialgomes.com.br"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Categoria</label>
                  <input
                    className="input text-xs"
                    value={editing.categoria ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, categoria: e.target.value }))}
                    placeholder="mesa-posta"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Subcategoria</label>
                  <input
                    className="input text-xs"
                    value={editing.subcategoria ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, subcategoria: e.target.value }))}
                    placeholder="servir"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Página específica</label>
                  <input
                    className="input text-xs"
                    value={editing.pagina_especifica ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, pagina_especifica: e.target.value }))}
                    placeholder="pratos"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">
                    Price multiplier
                  </label>
                  <input
                    className="input text-xs"
                    type="number"
                    step="0.1"
                    min="1"
                    value={editing.price_multiplier ?? 2}
                    onChange={(e) =>
                      setEditing((p) => ({ ...p, price_multiplier: parseFloat(e.target.value) }))
                    }
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleSaveVendor}
                  disabled={saving}
                  className="btn btn-primary text-xs"
                >
                  {saving ? "Saving…" : "Save vendor"}
                </button>
                <button
                  onClick={() => setEditing(null)}
                  className="btn text-xs"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Enrichment tab ───────────────────────────────────── */}
      {tab === "enrichment" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-400">
            Customize how AI enriches your product descriptions and images.
            These settings are stored per vendor config — edit individual vendors to
            set custom prompts.
          </p>

          <div className="card space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Default brand prompt
              </label>
              <textarea
                className="input h-32 py-2 resize-none text-xs font-mono"
                placeholder="You are a product description expert for [brand]. Generate SEO-optimized descriptions with Mediterranean lifestyle storytelling…"
                rows={6}
              />
              <p className="text-[10px] text-gray-400 mt-1">
                Used when no custom prompt is set on a vendor config.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">
                Image style prompt
              </label>
              <textarea
                className="input h-24 py-2 resize-none text-xs font-mono"
                placeholder="Replace plain white backgrounds with: Pedra Clara Texturizada — light stone surface in beige and sand tones…"
                rows={4}
              />
            </div>

            <button className="btn btn-primary text-xs">Save defaults</button>
          </div>
        </div>
      )}

      {/* ── Schedule tab ─────────────────────────────────────── */}
      {tab === "schedule" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-400">
            Sync schedules are configured per vendor using cron expressions.
            The scheduler checks every 5 minutes.
          </p>

          <div className="card space-y-3">
            <h2 className="text-xs font-medium text-gray-700">Common schedules</h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Every day at 2am",    cron: "0 2 * * *" },
                { label: "Every 6 hours",        cron: "0 */6 * * *" },
                { label: "Every Monday at 9am",  cron: "0 9 * * 1" },
                { label: "Every hour",           cron: "0 * * * *" },
              ].map(({ label, cron }) => (
                <div
                  key={cron}
                  className="flex items-center justify-between p-2.5 border border-gray-100 rounded-lg text-xs"
                >
                  <span className="text-gray-600">{label}</span>
                  <span className="font-mono text-gray-400 text-[10px] bg-gray-50 px-2 py-0.5 rounded">
                    {cron}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-gray-400">
              To set a schedule, edit the vendor config in the Vendor sources tab.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
