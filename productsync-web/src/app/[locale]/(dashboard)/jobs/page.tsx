// PATH: src/app/(dashboard)/jobs/page.tsx
"use client";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { RefreshCw } from "lucide-react";
import Link from "next/link";
import clsx from "clsx";
import { jobsApi } from "@/lib/api";
import type { Job } from "@/types";

const STATUS_BADGE: Record<string, string> = {
  done_with_errors: "badge badge-cancelled",
  running:   "badge badge-running",
  done:      "badge badge-done",
  failed:    "badge badge-failed",
  queued:    "badge badge-queued",
  cancelled: "badge badge-cancelled",
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const r = await jobsApi.list(50);
      setJobs(r.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // Poll every 5s for running jobs
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-5 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-base font-medium text-gray-900">Jobs</h1>
        <div className="flex gap-2">
          <button onClick={load} className="btn text-xs">
            <RefreshCw size={12} className={clsx(loading && "animate-spin")} />
            Refresh
          </button>
          <a href="/jobs/new" className="btn btn-primary text-xs">
            + New sync
          </a>
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        {jobs.length === 0 && !loading ? (
          <div className="p-8 text-center text-sm text-gray-400">
            No jobs yet — trigger your first sync above.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400 text-left">
                <th className="px-4 py-2.5 font-medium">Job ID</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Progress</th>
                <th className="px-4 py-2.5 font-medium">Scraped</th>
                <th className="px-4 py-2.5 font-medium">Pushed</th>
                <th className="px-4 py-2.5 font-medium">Created</th>
                <th className="px-4 py-2.5 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr
                  key={job.id}
                  className="border-b border-gray-100 last:border-0 hover:bg-gray-50"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="font-mono text-brand-600 hover:underline"
                    >
                      {job.id.slice(0, 8)}…
                    </Link>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={STATUS_BADGE[job.status]}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-gray-100">
                        <div
                          className={clsx(
                            "h-full rounded-full",
                            job.status === "done" ? "bg-green-500" :
                            job.status === "failed" ? "bg-red-400" :
                            "bg-teal-500"
                          )}
                          style={{ width: `${job.progress_pct}%` }}
                        />
                      </div>
                      <span className="text-gray-400">{job.progress_pct}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-gray-600">{job.products_scraped}</td>
                  <td className="px-4 py-2.5 text-gray-600">{job.products_pushed}</td>
                  <td className="px-4 py-2.5 text-gray-400">
                    {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
                  </td>
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
