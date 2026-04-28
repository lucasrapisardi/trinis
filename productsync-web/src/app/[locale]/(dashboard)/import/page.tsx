"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import toast from "react-hot-toast";
import { Upload, Download, CheckCircle, AlertCircle } from "lucide-react";
import api, { storesApi } from "@/lib/api";
import type { ShopifyStore } from "@/types";

interface Product {
  nome: string;
  descricao: string;
  preco: string;
  ean?: string;
  imagem_url?: string;
  categoria?: string;
  tags?: string;
}

interface ParseResult {
  total: number;
  valid: number;
  errors: { row: number; error: string }[];
  preview: Product[];
  products: Product[];
}

export default function ImportPage() {
  const [stores, setStores] = useState<ShopifyStore[]>([]);
  const [storeId, setStoreId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [enrich, setEnrich] = useState(true);
  const [aiModel, setAiModel] = useState("gpt-4o-mini");
  const [availableModels, setAvailableModels] = useState<string[]>(["gpt-4o-mini"]);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    storesApi.list().then((r) => {
      setStores(r.data);
      if (r.data.length > 0) setStoreId(r.data[0].id);
    }).catch(() => null);
    api.get("/billing/model-addon/status").then((r) => {
      setAvailableModels(r.data.available_models ?? ["gpt-4o-mini"]);
    }).catch(() => null);
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setParseResult(null);
    setParsing(true);
    try {
      const form = new FormData();
      form.append("file", f);
      const r = await api.post("/import/parse", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setParseResult(r.data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to parse file");
    } finally {
      setParsing(false);
    }
  }

  async function handleImport() {
    if (!parseResult || !storeId) return;
    setImporting(true);
    try {
      const r = await api.post("/import/run", {
        products: parseResult.products,
        store_id: storeId,
        enrich,
        ai_model: aiModel,
      });
      setJobId(r.data.job_id);
      toast.success(`Import started! ${r.data.total} products queued.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Import failed");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="p-5 max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-medium text-gray-900">Import Products</h1>
        <div className="flex gap-2">
          <a href="http://localhost:8000/api/import/template/csv" className="btn text-xs flex items-center gap-1.5">
            <Download size={12} /> CSV Template
          </a>
          <a href="http://localhost:8000/api/import/template/xml" className="btn text-xs flex items-center gap-1.5">
            <Download size={12} /> XML Template
          </a>
        </div>
      </div>

      {/* Instructions */}
      <div className="card bg-blue-50 border border-blue-100">
        <p className="text-xs text-blue-700 font-medium mb-1">How it works</p>
        <ol className="text-[10px] text-blue-600 space-y-0.5 list-decimal list-inside">
          <li>Download the CSV or XML template</li>
          <li>Fill in your products (nome, descrição and preço are required)</li>
          <li>Upload the file and preview the results</li>
          <li>Choose whether to enrich with AI or push directly to Shopify</li>
          <li>Click Import — products will be processed in the background</li>
        </ol>
      </div>

      {/* Upload */}
      <div className="card space-y-3">
        <p className="text-xs font-medium text-gray-700">Upload File</p>
        <label className="flex flex-col items-center justify-center border-2 border-dashed border-gray-200 rounded-lg p-8 cursor-pointer hover:border-brand-400 hover:bg-brand-50 transition-colors">
          <Upload size={20} className="text-gray-400 mb-2" />
          <p className="text-xs text-gray-500">{file ? file.name : "Click to upload CSV or XML"}</p>
          <p className="text-[10px] text-gray-400 mt-1">Supported formats: .csv, .xml</p>
          <input type="file" accept=".csv,.xml" onChange={handleFileChange} className="hidden" />
        </label>
        {parsing && <p className="text-xs text-gray-400 text-center">Parsing file…</p>}
      </div>

      {/* Parse result */}
      {parseResult && (
        <div className="card space-y-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-xs text-green-700">
              <CheckCircle size={14} />
              <span>{parseResult.valid} valid products</span>
            </div>
            {parseResult.errors.length > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-red-600">
                <AlertCircle size={14} />
                <span>{parseResult.errors.length} errors</span>
              </div>
            )}
            <span className="text-[10px] text-gray-400 ml-auto">{parseResult.total} total rows</span>
          </div>

          {parseResult.errors.length > 0 && (
            <div className="bg-red-50 rounded p-2 space-y-1">
              {parseResult.errors.slice(0, 5).map((e, i) => (
                <p key={i} className="text-[10px] text-red-600">Row {e.row}: {e.error}</p>
              ))}
            </div>
          )}

          {/* Preview */}
          <div className="overflow-x-auto">
            <p className="text-[10px] text-gray-400 mb-1">Preview (first 5 rows)</p>
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 text-left">
                  <th className="py-1.5 pr-3 font-medium">Nome</th>
                  <th className="py-1.5 pr-3 font-medium">Preço</th>
                  <th className="py-1.5 pr-3 font-medium">EAN</th>
                  <th className="py-1.5 font-medium">Imagem</th>
                </tr>
              </thead>
              <tbody>
                {parseResult.preview.map((p, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    <td className="py-1.5 pr-3 text-gray-800 max-w-[200px] truncate">{p.nome}</td>
                    <td className="py-1.5 pr-3 text-gray-600">R$ {p.preco}</td>
                    <td className="py-1.5 pr-3 text-gray-400 font-mono text-[10px]">{p.ean || "—"}</td>
                    <td className="py-1.5 text-[10px]">
                      {p.imagem_url ? (
                        <img src={p.imagem_url} className="w-8 h-8 object-cover rounded" onError={(e) => (e.currentTarget.style.display = "none")} />
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Import options */}
      {parseResult && parseResult.valid > 0 && !jobId && (
        <div className="card space-y-4">
          <p className="text-xs font-medium text-gray-700">Import Options</p>

          {/* Store */}
          <div>
            <label className="block text-[10px] text-gray-400 mb-1">Target Store</label>
            <select className="input text-xs w-full" value={storeId} onChange={(e) => setStoreId(e.target.value)}>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>{s.shop_domain}</option>
              ))}
            </select>
          </div>

          {/* Pipeline */}
          <div className="flex gap-3">
            <label className="flex items-start gap-2 cursor-pointer">
              <input type="radio" checked={enrich} onChange={() => setEnrich(true)} className="mt-0.5 accent-brand-600" />
              <div>
                <p className="text-xs font-medium text-gray-700">Enrich with AI</p>
                <p className="text-[10px] text-gray-400">Generate descriptions + enhance hero image before pushing to Shopify</p>
              </div>
            </label>
            <label className="flex items-start gap-2 cursor-pointer">
              <input type="radio" checked={!enrich} onChange={() => setEnrich(false)} className="mt-0.5 accent-brand-600" />
              <div>
                <p className="text-xs font-medium text-gray-700">Push directly</p>
                <p className="text-[10px] text-gray-400">Use data as-is, no AI processing</p>
              </div>
            </label>
          </div>

          {/* AI Model */}
          {enrich && (
            <div>
              <label className="block text-[10px] text-gray-400 mb-1">AI Model</label>
              <div className="flex flex-wrap gap-2">
                {availableModels.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setAiModel(m)}
                    className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                      aiModel === m ? "border-brand-500 bg-brand-50 text-brand-700 font-medium" : "border-gray-200 text-gray-600"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={handleImport}
            disabled={importing || !storeId}
            className="btn btn-primary w-full justify-center text-sm"
          >
            {importing ? "Starting import…" : `Import ${parseResult.valid} products`}
          </button>
        </div>
      )}

      {/* Success */}
      {jobId && (
        <div className="card bg-green-50 border border-green-100 text-center space-y-2">
          <CheckCircle size={24} className="text-green-600 mx-auto" />
          <p className="text-sm font-medium text-green-800">Import started successfully!</p>
          <p className="text-xs text-green-600">You can track progress in the Jobs page.</p>
          <a href="/jobs" className="btn btn-primary text-xs inline-block mt-2">View Jobs →</a>
        </div>
      )}
    </div>
  );
}
