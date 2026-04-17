// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/confirm-email/page.tsx
"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

function ConfirmEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) { setStatus("error"); setMessage("Invalid confirmation link."); return; }
    axios.get(`${API_URL}/auth/confirm-email/${token}`)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setMessage(err?.response?.data?.detail || "This link is invalid or has expired.");
      });
  }, [token]);

  return (
    <div className="text-center space-y-3">
      {status === "loading" && (
        <>
          <div className="text-3xl animate-pulse">📬</div>
          <p className="text-sm text-gray-500">Confirming your email…</p>
        </>
      )}
      {status === "success" && (
        <>
          <div className="text-3xl">✅</div>
          <h2 className="text-sm font-medium text-gray-900">Email confirmed!</h2>
          <p className="text-xs text-gray-500">Your account is now active. You can log in.</p>
          <a href="/login" className="btn btn-primary text-xs w-full justify-center block mt-2">
            Go to login →
          </a>
        </>
      )}
      {status === "error" && (
        <>
          <div className="text-3xl">⚠️</div>
          <h2 className="text-sm font-medium text-gray-900">Confirmation failed</h2>
          <p className="text-xs text-gray-500">{message}</p>
          <a href="/register" className="btn text-xs w-full justify-center block mt-2">
            Back to register
          </a>
        </>
      )}
    </div>
  );
}

export default function ConfirmEmailPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
        </div>
        <div className="card">
          <Suspense fallback={<p className="text-xs text-gray-400 text-center">Loading…</p>}>
            <ConfirmEmailContent />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
