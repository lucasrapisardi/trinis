"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { formatDistanceToNow } from "date-fns";
import { Plus, RefreshCw } from "lucide-react";
import clsx from "clsx";
import { jobsApi, storesApi } from "@/lib/api";
import type { DashboardSummary, Job, ShopifyStore } from "@/types";

function MetricCard({
  label, value, sub,
}: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-100 rounded-lg px-3.5 py-3">
      <p className="text-[11px] text-gray-400 mb-1">{label}</p>
      <p className="text-xl font-medium text-gray-900">{value}</p>
      {sub && <p className="text-[11px] text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

const STATUS_BADGE: Record<string, string> = {
  running:   "badge badge-running",
  done:      "badge badge-done",
  failed:    "badge badge-failed",
  queued:    "badge badge-queued",
  cancelled: "badge badge-cancelled",
};

export default function DashboardPage() {
  const { data: session } = useSession();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stores, setStores] = useState<ShopifyStore[]>([]);

  useEffect(() => {
    jobsApi.summary().then((r) => setSummary(r.data)).catch(() => null);
    jobsApi.list(10).then((r) => setJobs(r.data)).catch(() => null);
    storesApi.list().then((r) => setStores(r.data)).catch(() => null);
  }, []);

  const firstName = session?.user?.full_name?.split(" ")[0]
    ?? session?.user?.email?.split("@")[0]
    ?? "there";

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" :
    hour < 18 ? "Good afternoon" :
    "Good evening";

  return (
    <div className="p-5 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-base font-medium text-gray-900">
            {greeting}, {firstName}
          </h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {summary?.running_jobs
              ? `${summary.running_jobs} job${summary.running_jobs > 1 ? "s" : ""} running`
              : "No jobs running"}{" "}
            {summary?.last_sync_at &&
              `· last sync ${formatDistanceToNow(new Date(summary.last_sync_at), { addSuffix: true })}`}
          </p>
        </div>
        <a href="/jobs/new" className="btn btn-primary text-xs">
          <Plus size={13} /> New sync
        </a>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-2 mb-5">
        <MetricCard
          label="Products synced"
          value={(summary?.products_synced_this_month ?? 0).toLocaleString()}
          sub="this month"
        />
        <MetricCard
          label="Jobs this month"
          value={(summary?.jobs_this_month ?? 0).toString()}
          sub={`${summary?.jobs_failed_this_month ?? 0} failed`}
        />
        <MetricCard
          label="Plan usage"
          value={
            summary
              ? `${Math.round((summary.products_synced_this_month / summary.plan_limit) * 100)}%`
              : "—"
          }
          sub={
            summary
              ? `${summary.products_synced_this_month.toLocaleString()} / ${summary.plan_limit.toLocaleString()}`
              : undefined
          }
        />
        <MetricCard
          label="Plan"
          value={summary?.plan ? summary.plan.charAt(0).toUpperCase() + summary.plan.slice(1) : "—"}
          sub="current plan"
        />
      </div>

      {/* Bottom grid */}
      <div className="grid grid-cols-5 gap-4">
        {/* Job feed */}
        <div className="col-span-3 card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-medium text-gray-700">Recent jobs</h2>
            <button
              onClick={() => jobsApi.list(10).then((r) => setJobs(r.data))}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
            >
              <RefreshCw size={12} />
            </button>
          </div>

          {jobs.length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">No jobs yet</p>
          ) : (
            <div className="space-y-0">
              {jobs.map((job) => (
                <a
                  key={job.id}
                  href={`/jobs/${job.id}`}
                  className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0 hover:bg-gray-50 -mx-1 px-1 rounded text-xs group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-800 truncate">
                      Job #{job.id.slice(0, 8)}
                    </p>
                    <p className="text-gray-400 text-[10px]">
                      {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  {job.status === "running" && (
                    <div className="w-16 h-1 rounded-full bg-gray-200">
                      <div
                        className="h-full rounded-full bg-teal-500 transition-all"
                        style={{ width: `${job.progress_pct}%` }}
                      />
                    </div>
                  )}
                  <span className={STATUS_BADGE[job.status] ?? "badge badge-queued"}>
                    {job.status}
                  </span>
                </a>
              ))}
            </div>
          )}

          <a href="/jobs" className="btn text-xs mt-3 w-full justify-center">
            View all jobs
          </a>
        </div>

        {/* Right column */}
        <div className="col-span-2 space-y-4">
          {/* Connected stores */}
          <div className="card">
            <h2 className="text-xs font-medium text-gray-700 mb-3">
              Connected stores
            </h2>
            {stores.length === 0 ? (
              <p className="text-xs text-gray-400">No stores connected yet</p>
            ) : (
              <div className="space-y-2">
                {stores.map((store) => (
                  <div
                    key={store.id}
                    className="flex items-center gap-2 p-2 border border-gray-100 rounded-lg"
                  >
                    <div
                      className={clsx(
                        "w-1.5 h-1.5 rounded-full flex-shrink-0",
                        store.is_active ? "bg-teal-500" : "bg-amber-500"
                      )}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{store.shop_domain}</p>
                      <p className="text-[10px] text-gray-400">
                        {store.last_synced_at
                          ? `Synced ${formatDistanceToNow(new Date(store.last_synced_at), { addSuffix: true })}`
                          : "Never synced"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <a href="/stores" className="btn text-xs mt-3 w-full justify-center">
              + Add store
            </a>
          </div>

          {/* Quick actions */}
          <div className="card">
            <h2 className="text-xs font-medium text-gray-700 mb-3">
              Quick actions
            </h2>
            <div className="space-y-1.5">
              {[
                { href: "/settings/vendors", label: "Configure vendors" },
                { href: "/settings/enrichment", label: "Edit AI rules" },
                { href: "/settings/schedule", label: "Set sync schedule" },
              ].map(({ href, label }) => (
                <a key={href} href={href} className="btn text-xs w-full justify-start">
                  {label} →
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
