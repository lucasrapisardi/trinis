// PATH: /home/lumoura/trinis_ai/productsync-web/src/lib/currency.ts

const LOCALE_CURRENCY: Record<string, { currency: string; locale: string }> = {
  en: { currency: "USD", locale: "en-US" },
  pt: { currency: "BRL", locale: "pt-BR" },
  es: { currency: "EUR", locale: "es-ES" },
};

export function formatCurrency(amount: number, locale: string = "en"): string {
  const { currency, locale: intlLocale } = LOCALE_CURRENCY[locale] ?? LOCALE_CURRENCY.en;
  return new Intl.NumberFormat(intlLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function getCurrencySymbol(locale: string = "en"): string {
  const { currency, locale: intlLocale } = LOCALE_CURRENCY[locale] ?? LOCALE_CURRENCY.en;
  return new Intl.NumberFormat(intlLocale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(0).replace(/\d/g, "").trim();
}

export function getCurrency(locale: string = "en"): string {
  return LOCALE_CURRENCY[locale]?.currency ?? "USD";
}
