"use client";
import { useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { useLocale } from "next-intl";
import api from "@/lib/api";

const TOUR_STEPS = {
  en: [
    { element: "#nav-dashboard", popover: { title: "👋 Welcome to ProductSync!", description: "Your Dashboard gives a real-time overview of sync jobs, products, and store health.", side: "right" as const } },
    { element: "#nav-jobs", popover: { title: "⚡ Jobs", description: "Create and monitor sync jobs. Each job scrapes products, enriches with AI, and pushes to Shopify.", side: "right" as const } },
    { element: "#nav-stores", popover: { title: "🛍️ Stores", description: "Connect your Shopify stores via OAuth. Multiple stores available on higher plans.", side: "right" as const } },
    { element: "#nav-import", popover: { title: "📥 Import", description: "Import products via CSV or XML. Choose to enrich with AI or push directly to Shopify.", side: "right" as const } },
    { element: "#nav-billing", popover: { title: "💳 Billing", description: "Manage your plan, buy credits, add Bulk Image Enhance or upgrade your AI model tier.", side: "right" as const } },
    { element: "#nav-settings", popover: { title: "⚙️ Settings", description: "Configure vendor sources, AI prompts, sync schedule, and team members.", side: "right" as const } },
    { element: "#nav-backup", popover: { title: "🛡️ Backup", description: "Automatically back up your Shopify products and restore them anytime.", side: "right" as const } },
    { popover: { title: "🚀 You're all set!", description: "Start by connecting a store, adding a vendor, and creating your first sync job!" } },
  ],
  pt: [
    { element: "#nav-dashboard", popover: { title: "👋 Bem-vindo ao ProductSync!", description: "O Dashboard mostra em tempo real seus jobs, produtos e status das lojas.", side: "right" as const } },
    { element: "#nav-jobs", popover: { title: "⚡ Jobs", description: "Crie e monitore jobs de sincronização. Raspa produtos, enriquece com IA e publica no Shopify.", side: "right" as const } },
    { element: "#nav-stores", popover: { title: "🛍️ Lojas", description: "Conecte suas lojas Shopify via OAuth. Múltiplas lojas disponíveis nos planos superiores.", side: "right" as const } },
    { element: "#nav-import", popover: { title: "📥 Importar", description: "Importe produtos via CSV ou XML. Enriqueça com IA ou publique diretamente.", side: "right" as const } },
    { element: "#nav-billing", popover: { title: "💳 Faturamento", description: "Gerencie seu plano, compre créditos, adicione Bulk Enhance ou upgrade do modelo IA.", side: "right" as const } },
    { element: "#nav-settings", popover: { title: "⚙️ Configurações", description: "Configure fornecedores, prompts de IA, agenda de sincronização e equipe.", side: "right" as const } },
    { element: "#nav-backup", popover: { title: "🛡️ Backup", description: "Faça backup automático dos produtos Shopify e restaure quando precisar.", side: "right" as const } },
    { popover: { title: "🚀 Tudo pronto!", description: "Conecte uma loja, adicione um fornecedor e crie seu primeiro job!" } },
  ],
  es: [
    { element: "#nav-dashboard", popover: { title: "👋 ¡Bienvenido a ProductSync!", description: "El Dashboard muestra en tiempo real tus jobs, productos y estado de las tiendas.", side: "right" as const } },
    { element: "#nav-jobs", popover: { title: "⚡ Jobs", description: "Crea y monitorea jobs de sincronización. Extrae productos, enriquece con IA y publica en Shopify.", side: "right" as const } },
    { element: "#nav-stores", popover: { title: "🛍️ Tiendas", description: "Conecta tus tiendas Shopify vía OAuth. Múltiples tiendas disponibles en planes superiores.", side: "right" as const } },
    { element: "#nav-import", popover: { title: "📥 Importar", description: "Importa productos vía CSV o XML. Enriquece con IA o publica directamente.", side: "right" as const } },
    { element: "#nav-billing", popover: { title: "💳 Facturación", description: "Gestiona tu plan, compra créditos, agrega Bulk Enhance o mejora el modelo IA.", side: "right" as const } },
    { element: "#nav-settings", popover: { title: "⚙️ Configuración", description: "Configura proveedores, prompts de IA, agenda y equipo.", side: "right" as const } },
    { element: "#nav-backup", popover: { title: "🛡️ Backup", description: "Haz backup automático de tus productos Shopify y restáuralos cuando lo necesites.", side: "right" as const } },
    { popover: { title: "🚀 ¡Todo listo!", description: "Conecta una tienda, agrega un proveedor y crea tu primer job!" } },
  ],
};

export default function ProductTour() {
  const { data: session } = useSession();
  const locale = useLocale() as "en" | "pt" | "es";
  const driverRef = useRef<any>(null);

  async function startTour() {
    if (driverRef.current) {
      try { driverRef.current.destroy(); } catch {}
    }
    const { driver } = await import("driver.js");
    await import("driver.js/dist/driver.css");
    const steps = TOUR_STEPS[locale] || TOUR_STEPS.en;
    const next = locale === "pt" ? "Próximo →" : locale === "es" ? "Siguiente →" : "Next →";
    const prev = locale === "pt" ? "← Anterior" : locale === "es" ? "← Anterior" : "← Back";
    const done = locale === "pt" ? "Concluir ✓" : locale === "es" ? "Finalizar ✓" : "Done ✓";
    const driverObj = driver({
      showProgress: true,
      animate: true,
      overlayOpacity: 0.55,
      stagePadding: 6,
      stageRadius: 8,
      allowClose: true,
      nextBtnText: next,
      prevBtnText: prev,
      doneBtnText: done,
      onDestroyed: () => showDismissToast(),
      steps,
    });
    driverRef.current = driverObj;
    driverObj.drive();
  }

  // Listen for manual restart trigger
  useEffect(() => {
    window.addEventListener("start-tour", startTour);
    return () => window.removeEventListener("start-tour", startTour);
  }, [locale]);

  // Auto-start for new users
  useEffect(() => {
    if (!session?.user) return;
    const user = session.user as any;
    if (user.tour_completed) return;
    if (localStorage.getItem("tour_dismissed")) return;
    const timer = setTimeout(() => startTour(), 1200);
    return () => clearTimeout(timer);
  }, [session, locale]);

  function showDismissToast() {
    const existing = document.getElementById("tour-toast");
    if (existing) return;
    const toast = document.createElement("div");
    toast.id = "tour-toast";
    toast.style.cssText = `position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e293b;border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px 20px;display:flex;align-items:center;gap:16px;z-index:9999;font-size:13px;color:#94a3b8;box-shadow:0 8px 32px rgba(0,0,0,0.4);font-family:inherit;`;
    const labels: Record<string, string[]> = {
      en: ["Replay anytime via the", "Don't show again"],
      pt: ["Repita pelo botão", "Não mostrar novamente"],
      es: ["Repite con el botón", "No mostrar de nuevo"],
    };
    const [hint, dismiss] = labels[locale] || labels.en;
    toast.innerHTML = `<span>${hint} <strong style="color:#f1f5f9">?</strong></span><button id="tour-dismiss-btn" style="background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);color:#f1f5f9;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;font-family:inherit;">${dismiss}</button><button id="tour-close-btn" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:16px;">×</button>`;
    document.body.appendChild(toast);
    document.getElementById("tour-dismiss-btn")?.addEventListener("click", async () => {
      localStorage.setItem("tour_dismissed", "1");
      await api.patch("/auth/tour-complete").catch(() => null);
      toast.remove();
    });
    document.getElementById("tour-close-btn")?.addEventListener("click", () => toast.remove());
    setTimeout(() => toast.remove(), 8000);
  }

  return null;
}
