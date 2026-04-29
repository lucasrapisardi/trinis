// PATH: src/app/(dashboard)/layout.tsx
"use client";
import ProductTour from "@/components/ProductTour";
import TourRestartButton from "@/components/TourRestartButton";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import {
  LayoutDashboard, Clock, Package, Store,
  CreditCard, Settings, LogOut, Zap, Shield, Upload,
} from "lucide-react";
import { tenantApi } from "@/lib/api";
import type { Tenant } from "@/types";

const NAV_ITEMS = [
  { href: "/dashboard", key: "dashboard", icon: LayoutDashboard },
  { href: "/jobs",     key: "jobs",      icon: Clock },
  { href: "/products", key: "products",  icon: Package },
  { href: "/stores",   key: "stores",    icon: Store },
  { href: "/billing",  key: "billing",   icon: CreditCard },
  { href: "/settings", key: "settings",  icon: Settings },
  { href: "/backup",   key: "backup",   icon: Shield },
  { href: "/import",   key: "import",   icon: Upload },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const t = useTranslations();
  const pathname = usePathname();
  const [tenant, setTenant] = useState<Tenant | null>(null);

  useEffect(() => {
    tenantApi.get().then((r) => setTenant(r.data)).catch(() => null);
  }, []);

  const usagePct = tenant
    ? Math.round((tenant.products_synced_this_month / tenant.plan_limit) * 100)
    : 0;

  const usageColor =
    usagePct >= 95 ? "bg-red-500" :
    usagePct >= 80 ? "bg-amber-500" :
    "bg-teal-500";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-48 flex-shrink-0 flex flex-col bg-gray-50 border-r border-gray-200">
        {/* Logo */}
        <div className="px-4 py-3 border-b border-gray-200">
          <img src="/assets/trinis-logo.png" alt="Trinis AI" style={{height:"32px", width:"auto", maxWidth:"140px", display:"block"}} />
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {NAV_ITEMS.map(({ href, key, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                id={`nav-${key}`}
              className={clsx("nav-item", active && "nav-item-active")}
              >
                <Icon size={13} className="opacity-60 flex-shrink-0" />
                {t(`nav.${key}`)}
              </Link>
            );
          })}
        </nav>

        {/* Footer: usage + sign out */}
        <div className="px-3 py-3 border-t border-gray-200 space-y-2">
          {tenant && (
            <div>
              <div className="flex justify-between text-[10px] text-gray-400 mb-1">
                <span className="font-medium text-gray-600 capitalize">
                  {tenant.plan}
                </span>
                <span>
                  {tenant.products_synced_this_month.toLocaleString()} /{" "}
                  {tenant.plan_limit.toLocaleString()}
                </span>
              </div>
              <div className="h-1 rounded-full bg-gray-200">
                <div
                  className={clsx("h-full rounded-full transition-all", usageColor)}
                  style={{ width: `${Math.min(usagePct, 100)}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-700 truncate">
                {session?.user?.full_name ?? session?.user?.email}
              </p>
              <p className="text-[10px] text-gray-400 truncate">
                {session?.user?.email}
              </p>
            </div>
            <div className="px-3 pb-2">
              <LanguageSwitcher />
            </div>
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
              title={t("nav.signOut")}
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        {tenant?.payment_past_due && (
          <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-xs text-red-700 flex items-center justify-between">
            <span>Payment past due — please update your billing details.</span>
            <Link href="/billing" className="underline font-medium">
              Fix now
            </Link>
          </div>
        )}
        <ProductTour />
        <TourRestartButton />
        {children}
      </main>
    </div>
  );
}
