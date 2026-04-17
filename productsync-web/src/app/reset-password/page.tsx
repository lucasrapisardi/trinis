// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/reset-password/page.tsx
"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import axios from "axios";
import toast from "react-hot-toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) { setTokenValid(false); return; }
    axios.get(`${API_URL}/auth/verify-reset-token/${token}`)
      .then(() => setTokenValid(true))
      .catch(() => setTokenValid(false));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { toast.error("Passwords don't match"); return; }
    if (password.length < 8) { toast.error("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      await axios.post(`${API_URL}/auth/reset-password`, { token, new_password: password });
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  }

  if (tokenValid === null) {
    return <p className="text-xs text-gray-400 text-center">Verifying link…</p>;
  }

  if (tokenValid === false) {
    return (
      <div className="text-center space-y-3">
        <div className="text-3xl">⚠️</div>
        <h2 className="text-sm font-medium text-gray-900">Link expired or invalid</h2>
        <p className="text-xs text-gray-500">This reset link is no longer valid. Request a new one.</p>
        <a href="/forgot-password" className="btn btn-primary text-xs w-full justify-center block">
          Request new link →
        </a>
      </div>
    );
  }

  if (done) {
    return (
      <div className="text-center space-y-3">
        <div className="text-3xl">✅</div>
        <h2 className="text-sm font-medium text-gray-900">Password updated!</h2>
        <p className="text-xs text-gray-500">Redirecting you to login…</p>
      </div>
    );
  }

  return (
    <>
      <h2 className="text-sm font-medium text-gray-900 mb-1">Set new password</h2>
      <p className="text-xs text-gray-500 mb-4">Choose a strong password of at least 8 characters.</p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">New password</label>
          <input
            type="password"
            className="input text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoFocus
            minLength={8}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Confirm password</label>
          <input
            type="password"
            className="input text-sm"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <button type="submit" disabled={loading} className="btn btn-primary w-full justify-center text-sm">
          {loading ? "Updating…" : "Update password →"}
        </button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
        </div>
        <div className="card">
          <Suspense fallback={<p className="text-xs text-gray-400 text-center">Loading…</p>}>
            <ResetPasswordForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
