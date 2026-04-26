"use client";

import { useEffect, useState, useCallback } from "react";
import api from "@/lib/api";
import clsx from "clsx";
import toast from "react-hot-toast";
import { formatDistanceToNow } from "date-fns";
import { Download, Trash2, RefreshCw, Shield, RotateCcw } from "lucide-react";

const PLANS = {
  basic:    { price: 9,  label: "Basic",    snapshots: 5,    retention: "7 days",  auto: false, description: "Manual backups only" },
  standard: { price: 19, label: "Standard", snapshots: 30,   retention: "30 days", auto: true,  description: "Manual + daily automatic" },
  premium:  { price: 39, label: "Premium",  snapshots: "∞",  retention: "90 days", auto: true,  description: "Manual + daily automatic" },
};

export default function BackupPage() {
  const [status, setStatus] = useState<any>(null);
  const [stores, setStores] = useState<any[]>([]);
  const [selectedStore, setSelectedStore] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirmModal, setConfirmModal] = useState<{ title: string; message: string; onConfirm: () => void } | null>(null);
  const [restoreModal, setRestoreModal] = useState<string | null>(null);
  const [isFree, setIsFree] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("backup_success")) {
      toast.success("Backup plan activated!");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const [backupRes, storesRes, tenantRes] = await Promise.all([
        api.get("/backup/status"),
        api.get("/stores"),
        api.get("/tenant"),
      ]);
      setIsFree(tenantRes.data.plan === "free");
      setStatus(backupRes.data);
      const activeStores = storesRes.data.filter((s: any) => s.is_active);
      setStores(activeStores);
      if (activeStores.length > 0 && !selectedStore) {
        setSelectedStore(activeStores[0].id);
      }
    } catch {
      toast.error("Failed to load backup status");
    } finally {
      setLoading(false);
    }
  }, [selectedStore]);

  useEffect(() => { load(); }, [load]);

  async function handleSubscribe(plan: string) {
    try {
      const r = await api.post(`/backup/subscribe/${plan}`);
      if (r.data.checkout_url) {
        window.location.href = r.data.checkout_url;
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (typeof detail === "object" && detail?.code === "plan_upgrade_required") {
        toast.error(detail.message);
      } else {
        toast.error("Failed to subscribe");
      }
    }
  }

  async function handleCancel() {
    setConfirmModal({
      title: "Cancel backup subscription",
      message: "Your existing snapshots will be kept, but no new backups will be created.",
      onConfirm: async () => {
        setConfirmModal(null);
        try {
          await api.post("/backup/cancel");
          toast.success("Backup subscription cancelled");
          load();
        } catch {
          toast.error("Failed to cancel subscription");
        }
      }
    });
    return;
  }

  async function handleChangePlan(plan: string) {
    setConfirmModal({
      title: `Switch to ${PLANS[plan as keyof typeof PLANS]?.label} plan`,
      message: `Your plan will be updated to ${PLANS[plan as keyof typeof PLANS]?.label} ($${PLANS[plan as keyof typeof PLANS]?.price}/mo).`,
      onConfirm: async () => {
        setConfirmModal(null);
        try {
          await api.put(`/backup/subscribe/${plan}`);
          toast.success(`Switched to ${plan} plan`);
          load();
        } catch {
          toast.error("Failed to change plan");
        }
      }
    });
    return;
  }

  async function handleRunBackup() {
    if (!selectedStore) { toast.error("Select a store first"); return; }
    setRunning(true);
    try {
      await api.post(`/backup/run/${selectedStore}`);
      toast.success("Backup started — this may take a few minutes");
      setTimeout(load, 3000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "object" ? detail.message : "Failed to start backup");
    } finally {
      setRunning(false);
    }
  }

  async function handleRestore(snapshotId: string, mode: string) {
    setConfirmModal(null);
    try {
      await api.post(`/backup/restore/${snapshotId}?mode=${mode}`);
      toast.success("Restore started — products will be updated shortly");
    } catch {
      toast.error("Failed to start restore");
    }
  }

  function promptRestore(snapshotId: string) {
    setConfirmModal({
      title: "Restore backup",
      message: "",
      onConfirm: () => {},
    });
    // Use custom modal with two options
    setRestoreModal(snapshotId);
  }

  async function handleDownload(snapshotId: string) {
    try {
      const { data: session } = await import("next-auth/react").then(m => ({ data: null }));
      const token = (await import("next-auth/react")).getSession().then((s: any) => s?.user?.access_token);
      const accessToken = await token;
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/backup/download/${snapshotId}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      );
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `backup-${snapshotId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to download backup");
    }
  }

  async function handleDelete(snapshotId: string) {
    if (!confirm("Delete this backup snapshot?")) return;
    try {
      await api.delete(`/backup/${snapshotId}`);
      toast.success("Backup deleted");
      load();
    } catch {
      toast.error("Failed to delete backup");
    }
  }

  if (loading) return <div className="p-8 text-xs text-gray-400">Loading…</div>;

  if (isFree) return (
    <div className="p-6 max-w-lg mx-auto mt-12">
      <div className="card text-center space-y-4 py-10">
        <div className="text-4xl">🔒</div>
        <h2 className="text-sm font-semibold text-gray-800">Backup is not available on the Free plan</h2>
        <p className="text-xs text-gray-400">Upgrade to Starter or above to protect your product catalog with automatic backups.</p>
        <a href="/billing" className="inline-block btn btn-primary text-xs px-6">
          Upgrade plan →
        </a>
      </div>
    </div>
  );

  const sub = status?.subscription;
  const snapshots = status?.snapshots ?? [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Shield size={20} className="text-brand-600" />
        <div>
          <h1 className="text-sm font-semibold text-gray-900">Backup Add-on</h1>
          <p className="text-[10px] text-gray-400">Full snapshots of your Shopify products, stored securely</p>
        </div>
      </div>

      {/* Plan selection */}
      {!sub?.active ? (
        <div className="space-y-3">
          <p className="text-xs font-medium text-gray-700">Choose a backup plan:</p>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(PLANS).map(([key, plan]) => (
              <div key={key} className="card space-y-3">
                <div>
                  <p className="text-xs font-semibold text-gray-800">{plan.label}</p>
                  <p className="text-xl font-bold text-brand-600 mt-1">${plan.price}<span className="text-xs font-normal text-gray-400">/mo</span></p>
                </div>
                <ul className="space-y-1">
                  <li className="text-[10px] text-gray-500">📦 {plan.snapshots} snapshots</li>
                  <li className="text-[10px] text-gray-500">🗓 {plan.retention} retention</li>
                  <li className="text-[10px] text-gray-500">⚡ {plan.description}</li>
                </ul>
                <button onClick={() => handleSubscribe(key)} className="btn btn-primary text-xs w-full justify-center">
                  Subscribe →
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-700">
                Active plan: <span className="text-brand-600 font-semibold capitalize">{sub.plan}</span>
              </p>
              {sub.next_auto_backup_at && (
                <p className="text-[10px] text-gray-400 mt-0.5">
                  Next auto backup: {formatDistanceToNow(new Date(sub.next_auto_backup_at), { addSuffix: true })}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {stores.length > 1 && (
                <select value={selectedStore} onChange={(e) => setSelectedStore(e.target.value)} className="input text-xs py-1">
                  {stores.map((s: any) => (
                    <option key={s.id} value={s.id}>{s.shop_domain}</option>
                  ))}
                </select>
              )}
              <button onClick={handleRunBackup} disabled={running} className="btn btn-primary text-xs flex items-center gap-1.5">
                <RefreshCw size={12} className={running ? "animate-spin" : ""} />
                {running ? "Running…" : "Run backup now"}
              </button>
            </div>
          </div>

          {/* Plan switcher */}
          <div className="border-t border-gray-100 pt-3">
            <p className="text-[10px] text-gray-400 mb-2">Switch plan:</p>
            <div className="flex gap-2">
              {Object.entries(PLANS).map(([key, plan]) => (
                <button
                  key={key}
                  onClick={() => handleChangePlan(key)}
                  disabled={sub.plan === key}
                  className={clsx(
                    "text-[10px] px-3 py-1.5 rounded-lg border transition-colors",
                    sub.plan === key
                      ? "bg-brand-50 border-brand-200 text-brand-700 font-medium cursor-default"
                      : "border-gray-200 text-gray-500 hover:bg-gray-50"
                  )}
                >
                  {plan.label} ${plan.price}/mo
                </button>
              ))}
              <button onClick={handleCancel} className="text-[10px] px-3 py-1.5 rounded-lg border border-red-200 text-red-500 hover:bg-red-50 ml-auto">
                Cancel subscription
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Snapshots list */}
      {snapshots.length > 0 && (
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-xs font-medium text-gray-700">Snapshots ({snapshots.length})</p>
          </div>
          {snapshots.map((snap: any, i: number) => (
            <div key={snap.id} className={clsx("flex items-center gap-3 px-4 py-3", i < snapshots.length - 1 && "border-b border-gray-100")}>
              <div className={clsx("w-2 h-2 rounded-full flex-shrink-0",
                snap.status === "done" ? "bg-teal-500" :
                snap.status === "running" ? "bg-amber-500 animate-pulse" :
                snap.status === "failed" ? "bg-red-500" : "bg-gray-300"
              )} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-800">
                  {snap.product_count > 0 ? `${snap.product_count} products` : "Snapshot"}
                  <span className="ml-2 text-[10px] text-gray-400 capitalize">{snap.trigger}</span>
                </p>
                <p className="text-[10px] text-gray-400">
                  {formatDistanceToNow(new Date(snap.created_at), { addSuffix: true })}
                  {snap.file_size_bytes > 0 && ` · ${(snap.file_size_bytes / 1024).toFixed(1)} KB`}
                  {snap.status === "failed" && snap.error_message && ` · ${snap.error_message.slice(0, 60)}`}
                </p>
              </div>
              <span className={clsx("text-[10px] px-1.5 py-0.5 rounded font-medium",
                snap.status === "done" ? "bg-teal-50 text-teal-700" :
                snap.status === "running" ? "bg-amber-50 text-amber-700" :
                snap.status === "failed" ? "bg-red-50 text-red-700" : "bg-gray-100 text-gray-500"
              )}>{snap.status}</span>
              {snap.status === "done" && (
                <div className="flex gap-1">
                  <button onClick={() => setRestoreModal(snap.id)} className="btn text-[10px] py-0.5 px-2 flex items-center gap-1">
                    <RotateCcw size={10} /> Restore
                  </button>
                  <button onClick={() => handleDownload(snap.id)} className="btn text-[10px] py-0.5 px-2 flex items-center gap-1">
                    <Download size={10} /> Download
                  </button>
                  <button onClick={() => handleDelete(snap.id)} className="btn btn-danger text-[10px] py-0.5 px-2">
                    <Trash2 size={10} />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {sub?.active && snapshots.length === 0 && (
        <div className="card text-center py-8">
          <p className="text-xs text-gray-400">No backups yet — run your first backup above.</p>
        </div>
      )}
      {/* Restore Modal */}
      {restoreModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-900">Restore backup</h3>
            <p className="text-xs text-gray-500">Choose how to restore this snapshot:</p>
            <div className="space-y-2">
              <button
                onClick={() => { handleRestore(restoreModal, "all"); setRestoreModal(null); }}
                className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
              >
                <p className="text-xs font-medium text-gray-800">Restore all products</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Updates all existing products and recreates deleted ones</p>
              </button>
              <button
                onClick={() => { handleRestore(restoreModal, "new_only"); setRestoreModal(null); }}
                className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
              >
                <p className="text-xs font-medium text-gray-800">Restore missing products only</p>
                <p className="text-[10px] text-gray-400 mt-0.5">Only recreates products that no longer exist in your store</p>
              </button>
            </div>
            <button onClick={() => setRestoreModal(null)} className="w-full btn text-xs">Cancel</button>
          </div>
        </div>
      )}

      {/* Confirm Modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
            <h3 className="text-sm font-semibold text-gray-900">{confirmModal.title}</h3>
            <p className="text-xs text-gray-500">{confirmModal.message}</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setConfirmModal(null)} className="btn text-xs">Cancel</button>
              <button onClick={confirmModal.onConfirm} className="btn btn-primary text-xs">Confirm</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
