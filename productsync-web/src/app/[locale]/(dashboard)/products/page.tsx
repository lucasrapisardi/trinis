// PATH: src/app/(dashboard)/products/page.tsx
"use client";
import { useTranslations } from "next-intl";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { RefreshCw, ExternalLink } from "lucide-react";
import clsx from "clsx";
import api from "@/lib/api";

interface Product {
  id: string;
  title: string;
  status: string;
  vendor: string;
  product_type: string;
  created_at: string;
  updated_at: string;
  variants: { price: string; compare_at_price: string; barcode: string }[];
  image?: { src: string };
  shopify_id: string;
  shop_domain: string;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const t = useTranslations("nav");
  const [statusFilter, setStatusFilter] = useState("all");

  async function load() {
    setLoading(true);
    try {
      const r = await api.get("/products");
      setProducts(r.data);
    } catch {
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = products.filter((p) => {
    const matchSearch =
      !search ||
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.variants?.[0]?.barcode?.includes(search);
    const matchStatus =
      statusFilter === "all" || p.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-5 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-base font-medium text-gray-900">Products</h1>
        <button onClick={load} className="btn text-xs">
          <RefreshCw size={12} className={clsx(loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 mb-4">
        <input
          className="input text-xs max-w-xs"
          placeholder="Buscar por nome ou EAN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input text-xs w-36"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </select>
        <span className="text-xs text-gray-400 self-center ml-auto">
          {filtered.length} product{filtered.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">
            {products.length === 0
              ? "Nenhum produto sincronizado ainda — execute sua primeira sincronização."
              : "Nenhum produto encontrado."}
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400 text-left">
                <th className="px-4 py-2.5 font-medium">Product</th>
                <th className="px-4 py-2.5 font-medium">EAN</th>
                <th className="px-4 py-2.5 font-medium">Price</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Store</th>
                <th className="px-4 py-2.5 font-medium">Updated</th>
                <th className="px-4 py-2.5 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((product) => (
                <tr
                  key={product.id}
                  className="border-b border-gray-100 last:border-0 hover:bg-gray-50"
                >
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      {product.image?.src ? (
                        <img
                          src={product.image.src}
                          alt={product.title}
                          className="w-8 h-8 rounded object-cover border border-gray-100 flex-shrink-0"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded bg-gray-100 flex-shrink-0" />
                      )}
                      <span className="font-medium text-gray-800 truncate max-w-[200px]">
                        {product.title}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-gray-400">
                    {product.variants?.[0]?.barcode ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-gray-700">
                    {product.variants?.[0]?.price
                      ? `R$ ${parseFloat(product.variants[0].price).toFixed(2)}`
                      : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={clsx(
                      "badge",
                      product.status === "active" ? "badge-done" :
                      product.status === "draft"  ? "badge-queued" :
                      "badge-cancelled"
                    )}>
                      {product.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-400 truncate max-w-[120px]">
                    {product.shop_domain ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-gray-400">
                    {formatDistanceToNow(new Date(product.updated_at), {
                      addSuffix: true,
                    })}
                  </td>
                  <td className="px-4 py-2.5">
                    {product.shopify_id && product.shop_domain && (
                      <a
                        href={`https://${product.shop_domain}/admin/products/${product.shopify_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <ExternalLink size={12} />
                      </a>
                    )}
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
