// PATH: /home/lumoura/trinis_ai/productsync-web/src/components/LanguageSwitcher.tsx
"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import clsx from "clsx";

const LOCALES = [
  { code: "en", label: "EN", flag: "🇺🇸", currency: "USD", name: "English" },
  { code: "pt", label: "PT", flag: "🇧🇷", currency: "BRL", name: "Português" },
  { code: "es", label: "ES", flag: "🇪🇸", currency: "EUR", name: "Español" },
];

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const current = LOCALES.find((l) => l.code === locale) ?? LOCALES[0];

  function switchLocale(newLocale: string) {
    const segments = pathname.split("/");
    const hasLocale = LOCALES.some((l) => l.code === segments[1]);
    const newPath = hasLocale
      ? `/${newLocale}/${segments.slice(2).join("/")}`
      : `/${newLocale}${pathname}`;
    router.push(newPath);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <span>{current.flag}</span>
        <span className="font-medium">{current.label}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2.5 4L5 6.5L7.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[140px] py-1">
            {LOCALES.map((l) => (
              <button
                key={l.code}
                onClick={() => switchLocale(l.code)}
                className={clsx(
                  "w-full flex items-center gap-2.5 px-3 py-2 text-xs hover:bg-gray-50 transition-colors",
                  l.code === locale ? "text-brand-600 font-medium" : "text-gray-600"
                )}
              >
                <span>{l.flag}</span>
                <span>{l.name}</span>
                <span className="text-gray-400 ml-auto">{l.currency}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
