// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/accept-invite/page.tsx
"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import axios from "axios";
import toast from "react-hot-toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

function AcceptInviteForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  const [invite, setInvite] = useState<{ email: string; workspace_name: string; full_name: string } | null>(null);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) { setTokenValid(false); return; }
    axios.get(`${API_URL}/team/verify-invite/${token}`)
      .then((r) => {
        setTokenValid(true);
        setInvite(r.data);
        setFullName(r.data.full_name || "");
      })
      .catch(() => setTokenValid(false));
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) { toast.error("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      await axios.post(`${API_URL}/team/accept-invite`, {
        token,
        password,
        full_name: fullName,
      });
      setDone(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Failed to accept invite");
    } finally {
      setLoading(false);
    }
  }

  if (tokenValid === null) return <p className="text-xs text-gray-400 text-center">Verifying invite…</p>;

  if (tokenValid === false) {
    return (
      <div className="text-center space-y-3">
        <div className="text-3xl">⚠️</div>
        <h2 className="text-sm font-medium text-gray-900">Invite expired or invalid</h2>
        <p className="text-xs text-gray-500">This invite link is no longer valid. Ask the workspace owner to send a new one.</p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="text-center space-y-3">
        <div className="text-3xl">✅</div>
        <h2 className="text-sm font-medium text-gray-900">Account created!</h2>
        <p className="text-xs text-gray-500">Redirecting you to login…</p>
      </div>
    );
  }

  return (
    <>
      <h2 className="text-sm font-medium text-gray-900 mb-1">Accept invitation</h2>
      <p className="text-xs text-gray-500 mb-4">
        You&apos;ve been invited to join <strong>{invite?.workspace_name}</strong>.
        Create your password to get started.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Email</label>
          <input className="input text-sm bg-gray-50" value={invite?.email ?? ""} disabled />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Full name</label>
          <input
            className="input text-sm"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Your name"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Password</label>
          <input
            type="password"
            className="input text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoFocus
          />
        </div>
        <button type="submit" disabled={loading} className="btn btn-primary w-full justify-center text-sm">
          {loading ? "Creating account…" : "Accept invite →"}
        </button>
      </form>
    </>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
        </div>
        <div className="card">
          <Suspense fallback={<p className="text-xs text-gray-400 text-center">Loading…</p>}>
            <AcceptInviteForm />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
