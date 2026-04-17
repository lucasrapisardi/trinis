// PATH: src/app/(dashboard)/jobs/[id]/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { ArrowLeft, RotateCcw, Square } from "lucide-react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { jobsApi, buildWsUrl } from "@/lib/api";
import type { Job, JobLog } from "@/types";

const LOG_COLOR = {
  info:  "text-gray-500",
  warn:  "text-amber-600",
  error: "text-red-600",
};

const STATUS_BADGE: Record<string, string> = {
  running:         "badge badge-running",
  done:            "badge badge-done",
  done_with_errors:"badge badge-cancelled",
  failed:          "badge badge-failed",
  queued:          "badge badge-queued",
  cancelled:       "badge badge-cancelled",
};

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: session } = useSession();
  const router = useRouter();

  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<JobLog[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  const logRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Load job
  useEffect(() => {
    jobsApi.get(id).then((r) => setJob(r.data)).catch(() => null);
  }, [id]);

  // Load logs from DB for finished jobs
  useEffect(() => {
    if (!job) return;
    if (["done", "done_with_errors", "failed", "cancelled"].includes(job.status)) {
      // Fetch stored logs via REST for completed jobs
      import("@/lib/api").then(({ default: api }) => {
        api.get(`/jobs/${id}/logs`).then((r) => {
          setLogs(r.data || []);
        }).catch(() => null);
      });
    }
  }, [job?.status, id]);

  // WebSocket log stream
  useEffect(() => {
    if (!job || !session?.user?.access_token) return;
    if (!["running", "queued"].includes(job.status)) return;

    const ws = new WebSocket(
      buildWsUrl(id, session.user.access_token, 0)
    );
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "done") {
        jobsApi.get(id).then((r) => setJob(r.data));
        return;
      }
      if (data.type === "failed") {
        jobsApi.get(id).then((r) => setJob(r.data));
        return;
      }
      setLogs((prev) => [...prev, data as JobLog]);
      // Refresh job stats periodically
      if (data.line % 10 === 0) {
        jobsApi.get(id).then((r) => setJob(r.data));
      }
    };

    // Reconnect on disconnect with backoff
    let retryCount = 0;
    ws.onerror = () => {
      setTimeout(() => {
        retryCount++;
        // Component will re-render and reconnect
      }, Math.min(8000, 1000 * 2 ** retryCount));
    };

    return () => ws.close();
  }, [job?.status, session?.user?.access_token, id]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  async function handleRetry() {
    try {
      const r = await jobsApi.retry(id);
      toast.success("Job queued for retry");
      router.push(`/jobs/${r.data.id}`);
    } catch {
      toast.error("Failed to retry job");
    }
  }

  async function handleStop() {
    try {
      await jobsApi.stop(id);
      toast.success("Job stopped");
      jobsApi.get(id).then((r) => setJob(r.data));
    } catch {
      toast.error("Failed to stop job");
    }
  }

  if (!job) {
    return (
      <div className="p-5 text-sm text-gray-400">Loading…</div>
    );
  }

  return (
    <div className="p-5 max-w-4xl mx-auto flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <a href="/jobs" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={14} />
        </a>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-medium text-gray-900 font-mono">
              {job.id.slice(0, 8)}…
            </h1>
            <span className={STATUS_BADGE[job.status]}>{job.status}</span>
            {job.attempt > 1 && (
              <span className="badge badge-queued">attempt {job.attempt}</span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-0.5">
            Created {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
            {job.finished_at &&
              ` · finished ${formatDistanceToNow(new Date(job.finished_at), { addSuffix: true })}`}
          </p>
        </div>
        <div className="flex gap-2">
          {job.status === "failed" && (
            <button onClick={handleRetry} className="btn text-xs">
              <RotateCcw size={12} /> Retry
            </button>
          )}
          {(job.status === "running" || job.status === "queued") && (
            <button onClick={handleStop} className="btn btn-danger text-xs">
              <Square size={12} /> {job.status === "queued" ? "Cancel" : "Stop"}
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Scraped",  value: job.products_scraped },
          { label: "Enriched", value: job.products_enriched },
          { label: "Pushed",   value: job.products_pushed },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-100 rounded-lg px-3 py-2.5">
            <p className="text-[10px] text-gray-400">{label}</p>
            <p className="text-lg font-medium text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      {/* Progress */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400">Progress</span>
        <div className="flex-1 h-1.5 rounded-full bg-gray-200">
          <div
            className={clsx(
              "h-full rounded-full transition-all",
              job.status === "done" ? "bg-green-500" :
              job.status === "failed" ? "bg-red-400" :
              "bg-teal-500"
            )}
            style={{ width: `${job.progress_pct}%` }}
          />
        </div>
        <span className="text-xs text-gray-500 min-w-[32px] text-right">
          {job.progress_pct}%
        </span>
      </div>

      {/* Error */}
      {job.error_message && (
        <div className="bg-red-50 border border-red-100 rounded-lg px-3 py-2.5 text-xs text-red-700">
          {job.error_message}
        </div>
      )}

      {/* Error summary for done_with_errors */}
      {job.status === "done_with_errors" && job.error_summary && (() => {
        try {
          const summary = JSON.parse(job.error_summary);
          return (
            <div className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5 text-xs">
              <p className="font-medium text-amber-700 mb-1">Completed with errors</p>
              <div className="flex gap-4 text-amber-600">
                <span>✓ Pushed: {summary.pushed}</span>
                <span>✗ Failed: {summary.failed}</span>
                <span>Total: {summary.total}</span>
              </div>
              {summary.message && <p className="text-amber-500 mt-1">{summary.message}</p>}
            </div>
          );
        } catch { return null; }
      })()}

      {/* Log terminal */}
      <div className="card p-0 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
          <span className="text-xs font-medium text-gray-600">Logs</span>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div
                className={clsx(
                  "w-1.5 h-1.5 rounded-full",
                  wsConnected ? "bg-teal-500 animate-pulse" : "bg-gray-300"
                )}
              />
              <span className="text-[10px] text-gray-400">
                {wsConnected ? "live" : "disconnected"}
              </span>
            </div>
            <button
              onClick={() => {
                setAutoScroll(true);
                logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
              }}
              className="text-[10px] text-gray-400 hover:text-gray-600"
            >
              ↓ tail
            </button>
          </div>
        </div>

        <div
          ref={logRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            setAutoScroll(el.scrollTop + el.clientHeight >= el.scrollHeight - 10);
          }}
          className="h-72 overflow-y-auto px-3 py-2 bg-gray-50 font-mono"
        >
          {logs.length === 0 ? (
            <p className="text-xs text-gray-400 py-2">
              {job.status === "queued" ? "Waiting for worker…" : "No logs yet"}
            </p>
          ) : (
            logs.map((log) => (
              <div key={log.line} className="flex gap-3 text-[11px] leading-relaxed">
                <span className="text-gray-300 flex-shrink-0 select-none">
                  {new Date(log.ts).toLocaleTimeString()}
                </span>
                <span className={clsx("flex-shrink-0 w-8", LOG_COLOR[log.level])}>
                  {log.level}
                </span>
                <span className={LOG_COLOR[log.level]}>{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
