// PATH: src/app/(dashboard)/billing/page.tsx
"use client";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import clsx from "clsx";
import toast from "react-hot-toast";
import api, { billingApi, tenantApi } from "@/lib/api";
import type { Tenant, PlanName } from "@/types";

const PLANS = [
  {
    name: "free" as PlanName,
    label: "Free",
    price: "$0",
    features: ["10 produtos / mês", "1 loja", "Sincronização manual"],
    limit: 10,
  },
  {
    name: "starter" as PlanName,
    label: "Starter",
    price: "$19",
    features: ["300 produtos / mês", "2 lojas", "Sincronização agendada"],
    limit: 300,
  },
  {
    name: "pro" as PlanName,
    label: "Pro",
    price: "$49",
    features: ["1.000 produtos / mês", "5 lojas", "Sincronização agendada", "Enriquecimento por IA"],
    limit: 1000,
  },
  {
    name: "business" as PlanName,
    label: "Business",
    price: "$149",
    features: ["10.000 produtos / mês", "Lojas ilimitadas", "Fila prioritária", "Regras de IA personalizadas"],
    limit: 10000,
  },
];

// Mock invoices — in production fetch from your backend
const MOCK_INVOICES = [
  { date: "Apr 1, 2026", plan: "Pro plan", amount: "$49.00", status: "pago" },
  { date: "Mar 1, 2026", plan: "Pro plan", amount: "$49.00", status: "pago" },
  { date: "Feb 1, 2026", plan: "Pro plan", amount: "$49.00", status: "falhou" },
  { date: "Jan 1, 2026", plan: "Free plan", amount: "$0.00",  status: "pago" },
];

export default function BillingPage() {
  const { data: session } = useSession();
  const t = useTranslations("billing");
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loadingPortal, setLoadingPortal] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState<PlanName | null>(null);
  const [backup, setBackup] = useState<any>(null);

  useEffect(() => {
    tenantApi.get().then((r) => setTenant(r.data)).catch(() => null);
    api.get("/backup/status").then((r) => setBackup(r.data)).catch(() => null);
  }, []);

  async function handleManageBilling() {
    setLoadingPortal(true);
    try {
      const r = await billingApi.portal();
      window.location.href = r.data.portal_url;
    } catch {
      toast.error("Failed to open billing portal");
      setLoadingPortal(false);
    }
  }

  async function handleUpgrade(plan: PlanName) {
    if (plan === "free") return;
    setLoadingPlan(plan);
    try {
      const r = await billingApi.checkout(plan);
      window.location.href = r.data.checkout_url;
    } catch {
      toast.error("Failed to start checkout");
      setLoadingPlan(null);
    }
  }

  const usagePct = tenant
    ? Math.round((tenant.products_synced_this_month / tenant.plan_limit) * 100)
    : 0;

  const usageColor =
    usagePct >= 95 ? "bg-red-500" :
    usagePct >= 80 ? "bg-amber-500" :
    "bg-teal-500";

  return (
    <div className="p-5 max-w-3xl mx-auto space-y-5">
      <h1 className="text-base font-medium text-gray-900">Billing</h1>

      {/* Current plan + usage */}
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3 card space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-gray-400 mb-1">Current plan</p>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-medium text-gray-900 capitalize">
                  {tenant?.plan ?? "—"}
                </span>
                <span className="text-sm text-gray-400">
                  {tenant?.plan === "pro" ? "$49 / month" :
                   tenant?.plan === "business" ? "$149 / month" : "Free"}
                </span>
              </div>
            </div>
            <span className={clsx(
              "badge text-[10px]",
              tenant?.payment_past_due ? "badge-failed" : "badge-done"
            )}>
              {tenant?.payment_past_due ? "Pagamento em atraso" : t("active")}
            </span>
          </div>

          {/* Usage meter */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-gray-500">Products synced this month</span>
              <span className="font-medium text-gray-700">
                {tenant?.products_synced_this_month.toLocaleString()} /{" "}
                {tenant?.plan_limit.toLocaleString()}
              </span>
            </div>
            <div className="h-2 rounded-full bg-gray-100">
              <div
                className={clsx("h-full rounded-full transition-all", usageColor)}
                style={{ width: `${Math.min(usagePct, 100)}%` }}
              />
            </div>
            {usagePct >= 80 && (
              <p className="text-[10px] text-amber-600 mt-1">
                You&apos;re at {usagePct}% of your plan limit — consider upgrading.
              </p>
            )}
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={handleManageBilling}
              disabled={loadingPortal}
              className="btn btn-primary text-xs"
            >
              {loadingPortal ? "Abrindo…" : t("manageBilling")}
            </button>
          </div>
        </div>

        {/* Billing details */}
        <div className="col-span-2 card">
          <p className="text-xs font-medium text-gray-700 mb-3">Billing details</p>
          <div className="space-y-2.5 text-xs">
            {[
              { label: "Próxima fatura", value: "May 1, 2026" },
              { label: "Valor devido",   value: tenant?.plan === "pro" ? "$49.00" : tenant?.plan === "business" ? "$149.00" : "$0.00" },
              { label: "Pagamento",      value: "Visa ···· 4242" },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between">
                <span className="text-gray-400">{label}</span>
                <span className="font-medium text-gray-700">{value}</span>
              </div>
            ))}
          </div>
          <button
            onClick={handleManageBilling}
            className="btn text-xs w-full justify-center mt-4"
          >
            Update payment →
          </button>
        </div>
      </div>

      {/* Plan comparison */}
      <div className="grid grid-cols-3 gap-3">
        {PLANS.map((plan) => {
          const isCurrent = tenant?.plan === plan.name;
          const isDowngrade =
            (tenant?.plan === "business" && plan.name !== "business") ||
            (tenant?.plan === "pro" && plan.name === "free");

          return (
            <div
              key={plan.name}
              className={clsx(
                "card transition-all",
                isCurrent && "border-2 border-brand-600"
              )}
            >
              <div className="flex items-center justify-between mb-1">
                <p className={clsx(
                  "text-xs font-medium",
                  isCurrent ? "text-brand-600" : "text-gray-400"
                )}>
                  {plan.label}
                </p>
                {isCurrent && (
                  <span className="badge text-[10px] bg-brand-50 text-brand-800">
                    Current
                  </span>
                )}
              </div>

              <p className="text-lg font-medium text-gray-900 mb-3">
                {plan.price}
                {plan.name !== "free" && (
                  <span className="text-xs font-normal text-gray-400"> / mo</span>
                )}
              </p>

              <ul className="space-y-1.5 mb-4">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-center gap-1.5 text-xs text-gray-500">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <path d="M2 5l2 2 4-4" stroke="#1D9E75" strokeWidth="1.4"
                        strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>

              {!isCurrent && !isDowngrade && plan.name !== "free" && (
                <button
                  onClick={() => handleUpgrade(plan.name)}
                  disabled={loadingPlan === plan.name}
                  className="btn btn-primary text-xs w-full justify-center"
                >
                  {loadingPlan === plan.name ? "Carregando…" : "Fazer upgrade →"}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Backup Add-on */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-800">Backup Add-on</p>
            <p className="text-[10px] text-gray-400 mt-0.5">Full product snapshots stored securely</p>
          </div>
          {backup?.subscription?.active ? (
            <span className="text-[10px] bg-teal-50 text-teal-700 px-2 py-0.5 rounded font-medium capitalize">
              {backup.subscription.plan} · Active · {backup.subscription.plan === "basic" ? "$9" : backup.subscription.plan === "standard" ? "$19" : "$39"}/mo
            </span>
          ) : (
            <span className="text-[10px] bg-gray-100 text-gray-400 px-2 py-0.5 rounded">Not subscribed</span>
          )}
        </div>
        {backup?.subscription?.active ? (
          <div className="flex items-center justify-between border-t border-gray-100 pt-3">
            <div className="flex gap-4">
              <div>
                <p className="text-[10px] text-gray-400">Snapshots</p>
                <p className="text-xs font-medium text-gray-700">{backup.snapshots?.filter((s: any) => s.status === "done").length ?? 0} stored</p>
              </div>
              <div>
                <p className="text-[10px] text-gray-400">Plan</p>
                <p className="text-xs font-medium text-gray-700 capitalize">{backup.subscription.plan}</p>
              </div>
            </div>
            <a href="/backup" className="btn text-xs">Manage backup →</a>
          </div>
        ) : (
          <a href="/backup" className="inline-block btn btn-primary text-xs">
            Subscribe to Backup →
          </a>
        )}
      </div>



      {/* Invoice history */}
      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-700">Invoice history</p>
        </div>
        <table className="w-full text-xs">
          <tbody>
            {MOCK_INVOICES.map((inv, i) => (
              <tr
                key={i}
                className="border-b border-gray-100 last:border-0 hover:bg-gray-50"
              >
                <td className="px-4 py-2.5 font-medium text-gray-700">{inv.date}</td>
                <td className="px-4 py-2.5 text-gray-400">{inv.plan}</td>
                <td className="px-4 py-2.5 font-medium text-gray-700">{inv.amount}</td>
                <td className="px-4 py-2.5">
                  <span className={clsx(
                    "badge",
                    inv.status === "pago" ? "badge-done" : "badge-failed"
                  )}>
                    {inv.status}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <button className="btn text-[10px] py-0.5 px-2">PDF</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
