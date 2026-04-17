// PATH: src/app/(dashboard)/settings/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import clsx from "clsx";
import toast from "react-hot-toast";
import { vendorApi } from "@/lib/api";
import type { VendorConfig } from "@/types";

type Tab = "vendors" | "enrichment" | "schedule" | "team" | "cancel";
type ScrapeScope = "categoria" | "subcategoria" | "pagina";

const TABS: { id: Tab; label: string }[] = [
  { id: "vendors",    label: "Vendor sources" },
  { id: "enrichment", label: "AI enrichment" },
  { id: "schedule",   label: "Sync schedule" },
  { id: "team",     label: "Team" },
  { id: "cancel",    label: "Cancel account" },
];

const BLANK_VENDOR = {
  name: "",
  base_url: "https://www.comercialgomes.com.br",
  scrape_scope: "pagina" as ScrapeScope,
  categoria: "",
  subcategoria: "",
  pagina_especifica: "",
  brand_name: "",
  price_multiplier: 2.0,
  sync_schedule: "0 2 * * *",
};

const SCOPE_OPTIONS: { value: ScrapeScope; label: string; description: string }[] = [
  {
    value: "categoria",
    label: "Entire category",
    description: "Scrape all subcategories and pages under the category",
  },
  {
    value: "subcategoria",
    label: "Subcategory",
    description: "Scrape all pages under a specific subcategory",
  },
  {
    value: "pagina",
    label: "Specific page",
    description: "Scrape only a single product listing page",
  },
];

// ── Team Tab Component ────────────────────────────────────────────────────

interface Member {
  id: string;
  email: string;
  full_name: string | null;
  is_owner: boolean;
  email_confirmed: boolean;
  last_login_at: string | null;
}

interface AuditLogEntry {
  id: string;
  action: string;
  target: string | null;
  performed_by: string;
  created_at: string;
}

function TeamTab() {
  const [members, setMembers] = useState<Member[]>([]);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviting, setInviting] = useState(false);
  const [isPro, setIsPro] = useState<boolean | null>(null);

  const [userLimit, setUserLimit] = useState<number>(5);

  const load = useCallback(async () => {
    try {
      const [membersRes, logsRes, tenantRes] = await Promise.all([
        api.get("/team/members"),
        api.get("/team/audit-logs"),
        api.get("/tenant"),
      ]);
      setMembers(membersRes.data);
      setLogs(logsRes.data);
      setUserLimit(tenantRes.data.user_limit ?? 5);
      setIsPro(true);
    } catch (err: unknown) {
      const code = (err as { response?: { data?: { detail?: { code?: string } } } })?.response?.data?.detail?.code;
      if (code === "plan_upgrade_required") setIsPro(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    try {
      await api.post("/team/invite", { email: inviteEmail, full_name: inviteName });
      toast.success(`Invite sent to ${inviteEmail}`);
      setInviteEmail("");
      setInviteName("");
      load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: { message?: string } | string } } })?.response?.data?.detail;
      const msg = typeof detail === "object" ? detail?.message : detail;
      toast.error(msg || "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleRemove(userId: string, email: string) {
    if (!confirm(`Remove ${email} from the team?`)) return;
    try {
      await api.delete(`/team/members/${userId}`);
      toast.success("Member removed");
      load();
    } catch {
      toast.error("Failed to remove member");
    }
  }

  if (isPro === false) {
    return (
      <div className="card text-center space-y-3">
        <p className="text-sm font-medium text-gray-700">Team members require Pro plan</p>
        <p className="text-xs text-gray-400">Upgrade to Pro to invite up to 5 team members.</p>
        <a href="/billing" className="btn btn-primary text-xs inline-block">Upgrade to Pro →</a>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Usage bar */}
      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-gray-700">Team members</p>
          <span className="text-xs text-gray-400">{members.length} / {userLimit} used</span>
        </div>
        <div className="h-1.5 rounded-full bg-gray-100">
          <div
            className={clsx(
              "h-full rounded-full transition-all",
              members.length >= userLimit ? "bg-red-500" :
              members.length >= userLimit * 0.8 ? "bg-amber-500" :
              "bg-teal-500"
            )}
            style={{ width: `${Math.min((members.length / userLimit) * 100, 100)}%` }}
          />
        </div>
        {members.length >= userLimit && (
          <p className="text-[10px] text-red-600 mt-1">
            Member limit reached.{" "}
            <a href="/billing" className="underline">Upgrade your plan →</a>
          </p>
        )}
      </div>

      {/* Invite form */}
      <div className="card">
        <h3 className="text-xs font-medium text-gray-700 mb-3">Invite a team member</h3>
        <form onSubmit={handleInvite} className="flex gap-2">
          <input
            className="input text-xs flex-1"
            placeholder="Name (optional)"
            value={inviteName}
            onChange={(e) => setInviteName(e.target.value)}
          />
          <input
            type="email"
            className="input text-xs flex-1"
            placeholder="email@example.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
          />
          <button type="submit" disabled={inviting} className="btn btn-primary text-xs flex-shrink-0">
            {inviting ? "Sending…" : "Send invite"}
          </button>
        </form>
      </div>

      {/* Members list */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-700">Team members ({members.length})</p>
        </div>
        {members.map((m, i) => (
          <div key={m.id} className={clsx("flex items-center gap-3 px-4 py-3", i < members.length - 1 && "border-b border-gray-100")}>
            <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center text-xs font-medium text-brand-700 flex-shrink-0">
              {(m.full_name || m.email)[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-800">{m.full_name || m.email}</p>
              <p className="text-[10px] text-gray-400">{m.email}</p>
            </div>
            <div className="flex items-center gap-2">
              {m.is_owner && <span className="badge badge-done text-[10px]">Owner</span>}
              {!m.email_confirmed && <span className="badge badge-queued text-[10px]">Pending</span>}
              {m.last_login_at && <span className="text-[10px] text-gray-400">Last seen {new Date(m.last_login_at).toLocaleDateString()}</span>}
              {!m.is_owner && (
                <button onClick={() => handleRemove(m.id, m.email)} className="btn btn-danger text-[10px] py-0.5 px-2">Remove</button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Audit logs */}
      {logs.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-700">Activity log</p>
          </div>
          {logs.slice(0, 10).map((log) => (
            <div key={log.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 last:border-0">
              <div className="flex-1 min-w-0">
                <span className="text-xs text-gray-700 font-medium">{log.performed_by}</span>
                <span className="text-xs text-gray-400 ml-1">{log.action.replace(/_/g, " ")}</span>
                {log.target && <span className="text-xs text-gray-500 ml-1">→ {log.target}</span>}
              </div>
              <span className="text-[10px] text-gray-400 flex-shrink-0">
                {new Date(log.created_at).toLocaleDateString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>(() => {
    if (typeof window !== "undefined" && window.location.search.includes("cancel=1")) return "cancel";
    return "vendors";
  });
  const [vendors, setVendors] = useState<VendorConfig[]>([]);
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    vendorApi.list().then((r) => setVendors(r.data)).catch(() => null);
  }, []);

  async function handleSaveVendor() {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) {
        const r = await vendorApi.update(editing.id as string, editing);
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

  const scope = (editing?.scrape_scope ?? "pagina") as ScrapeScope;

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
              Configure vendor sites to scrape products from.
            </p>
            <button
              onClick={() => setEditing({ ...BLANK_VENDOR })}
              className="btn btn-primary text-xs"
            >
              + Add vendor
            </button>
          </div>

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
                    <span className="badge badge-queued capitalize">
                      {(v as unknown as Record<string,string>).scrape_scope ?? "pagina"}
                    </span>
                    <span>{v.price_multiplier}x</span>
                    {v.sync_schedule && (
                      <span className="font-mono text-[10px]">{v.sync_schedule}</span>
                    )}
                    <span className={clsx("badge", v.is_active ? "badge-done" : "badge-queued")}>
                      {v.is_active ? "active" : "paused"}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => setEditing(v as unknown as Record<string, unknown>)} className="btn text-[10px] py-0.5 px-2">Edit</button>
                    <button onClick={() => handleDeleteVendor(v.id)} className="btn btn-danger text-[10px] py-0.5 px-2">Delete</button>
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
            <div className="card space-y-4">
              <h2 className="text-xs font-medium text-gray-700">
                {editing.id ? "Edit vendor" : "New vendor"}
              </h2>

              {/* Basic info */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Name</label>
                  <input className="input text-xs" value={editing.name as string ?? ""} onChange={(e) => setEditing((p) => ({ ...p, name: e.target.value }))} placeholder="Comercial Gomes" />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Brand name</label>
                  <input className="input text-xs" value={editing.brand_name as string ?? ""} onChange={(e) => setEditing((p) => ({ ...p, brand_name: e.target.value }))} placeholder="Dimora Mediterranea" />
                </div>
                <div className="col-span-2">
                  <label className="block text-[10px] text-gray-400 mb-1">Base URL</label>
                  <input className="input text-xs" value={editing.base_url as string ?? ""} onChange={(e) => setEditing((p) => ({ ...p, base_url: e.target.value }))} placeholder="https://www.comercialgomes.com.br" />
                </div>
              </div>

              {/* Scrape scope */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-2">
                  Scrape scope
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {SCOPE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setEditing((p) => ({ ...p, scrape_scope: opt.value }))}
                      className={clsx(
                        "text-left p-2.5 rounded-lg border text-xs transition-colors",
                        scope === opt.value
                          ? "border-brand-600 bg-brand-50 text-brand-800"
                          : "border-gray-200 hover:bg-gray-50 text-gray-600"
                      )}
                    >
                      <p className="font-medium mb-0.5">{opt.label}</p>
                      <p className={clsx("text-[10px]", scope === opt.value ? "text-brand-600" : "text-gray-400")}>
                        {opt.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Dynamic fields based on scope */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">
                    Categoria {scope === "categoria" && <span className="text-brand-600">← scrape from here</span>}
                  </label>
                  <input
                    className={clsx("input text-xs", scope === "categoria" && "border-brand-600")}
                    value={editing.categoria as string ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, categoria: e.target.value }))}
                    placeholder="mesa-posta"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">
                    Subcategoria {scope === "subcategoria" && <span className="text-brand-600">← scrape from here</span>}
                  </label>
                  <input
                    className={clsx("input text-xs", scope === "subcategoria" && "border-brand-600", scope === "categoria" && "opacity-40")}
                    value={editing.subcategoria as string ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, subcategoria: e.target.value }))}
                    placeholder="servir"
                    disabled={scope === "categoria"}
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">
                    Página específica {scope === "pagina" && <span className="text-brand-600">← scrape from here</span>}
                  </label>
                  <input
                    className={clsx("input text-xs", scope === "pagina" && "border-brand-600", scope !== "pagina" && "opacity-40")}
                    value={editing.pagina_especifica as string ?? ""}
                    onChange={(e) => setEditing((p) => ({ ...p, pagina_especifica: e.target.value }))}
                    placeholder="pratos"
                    disabled={scope !== "pagina"}
                  />
                </div>
              </div>

              {/* Price + schedule */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Price multiplier</label>
                  <input className="input text-xs" type="number" step="0.1" min="1" value={editing.price_multiplier as number ?? 2} onChange={(e) => setEditing((p) => ({ ...p, price_multiplier: parseFloat(e.target.value) }))} />
                </div>
                <div>
                  <label className="block text-[10px] text-gray-400 mb-1">Sync schedule (cron)</label>
                  <input className="input text-xs font-mono" value={editing.sync_schedule as string ?? ""} onChange={(e) => setEditing((p) => ({ ...p, sync_schedule: e.target.value }))} placeholder="0 2 * * *" />
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button onClick={handleSaveVendor} disabled={saving} className="btn btn-primary text-xs">
                  {saving ? "Saving…" : "Save vendor"}
                </button>
                <button onClick={() => setEditing(null)} className="btn text-xs">Cancel</button>
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
          </p>
          <div className="card space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">Default brand prompt</label>
              <textarea className="input h-32 py-2 resize-none text-xs font-mono" placeholder="You are a product description expert for [brand]…" rows={6} />
              <p className="text-[10px] text-gray-400 mt-1">Used when no custom prompt is set on a vendor config.</p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1.5">Image style prompt</label>
              <textarea className="input h-24 py-2 resize-none text-xs font-mono" placeholder="Replace plain white backgrounds with: Pedra Clara Texturizada…" rows={4} />
            </div>
            <button className="btn btn-primary text-xs">Save defaults</button>
          </div>
        </div>
      )}


      {/* ── Team tab ─────────────────────────────────────── */}
      {tab === "team" && (
        <TeamTab />
      )}

      {/* ── Cancel account tab ──────────────────────────────────── */}
      {tab === "cancel" && (
        <div className="space-y-4">
          <div className="card border border-red-100">
            <h2 className="text-sm font-medium text-red-700 mb-2">Cancel account</h2>
            <p className="text-xs text-gray-500 mb-4">
              Cancelling your account will deactivate all connected stores and stop all syncs.
              Your data will be retained for 30 days before permanent deletion.
            </p>
            <div className="bg-red-50 rounded-lg px-3 py-2.5 text-xs text-red-600 mb-4 space-y-1">
              <p>• All connected Shopify stores will be disconnected</p>
              <p>• All scheduled syncs will be cancelled</p>
              <p>• Your Stripe subscription will be cancelled immediately</p>
              <p>• Data retained for 30 days then permanently deleted</p>
            </div>
            <button
              onClick={async () => {
                if (!confirm("Are you sure you want to cancel your account? This cannot be undone.")) return;
                try {
                  await fetch("/api/tenant/cancel", { method: "POST", headers: { "Authorization": `Bearer ${(window as any).__token}` } });
                  toast.success("Account cancelled. You will be signed out shortly.");
                  setTimeout(() => window.location.href = "/login", 2000);
                } catch {
                  toast.error("Failed to cancel account. Please contact support.");
                }
              }}
              className="btn btn-danger text-xs"
            >
              Cancel my account
            </button>
          </div>
        </div>
      )}

      {/* ── Schedule tab ─────────────────────────────────────── */}
      {tab === "schedule" && (
        <div className="space-y-4">
          <p className="text-xs text-gray-400">
            Sync schedules are configured per vendor using cron expressions. The scheduler checks every 5 minutes.
          </p>
          <div className="card space-y-3">
            <h2 className="text-xs font-medium text-gray-700">Common schedules</h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: "Every day at 2am",   cron: "0 2 * * *" },
                { label: "Every 6 hours",       cron: "0 */6 * * *" },
                { label: "Every Monday at 9am", cron: "0 9 * * 1" },
                { label: "Every hour",          cron: "0 * * * *" },
              ].map(({ label, cron }) => (
                <div key={cron} className="flex items-center justify-between p-2.5 border border-gray-100 rounded-lg text-xs">
                  <span className="text-gray-600">{label}</span>
                  <span className="font-mono text-gray-400 text-[10px] bg-gray-50 px-2 py-0.5 rounded">{cron}</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-gray-400">To set a schedule, edit the vendor config in the Vendor sources tab.</p>
          </div>
        </div>
      )}
    </div>
  );
}
