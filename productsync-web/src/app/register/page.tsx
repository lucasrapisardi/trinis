// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/register/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import toast from "react-hot-toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", workspace_name: "" });
  const [loading, setLoading] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState("");

  function set(field: string, value: string) {
    setForm((p) => ({ ...p, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_URL}/auth/register`, {
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        workspace_name: form.workspace_name,
      });
      setRegisteredEmail(form.email);
      setRegistered(true);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  if (registered) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          <div className="text-center mb-8">
            <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
          </div>
          <div className="card text-center space-y-3">
            <div className="text-3xl">📬</div>
            <h2 className="text-sm font-medium text-gray-900">Check your email</h2>
            <p className="text-xs text-gray-500">
              We sent a confirmation link to{" "}
              <span className="font-medium text-gray-700">{registeredEmail}</span>.
              Click it to activate your account.
            </p>
            <p className="text-xs text-gray-400">
              Didn&apos;t receive it?{" "}
              <button
                onClick={async () => {
                  await axios.post(`${API_URL}/auth/resend-confirmation`, { email: registeredEmail });
                  toast.success("Confirmation email resent!");
                }}
                className="text-brand-600 hover:underline"
              >
                Resend email
              </button>
            </p>
            <a href="/login" className="btn text-xs w-full justify-center block mt-2">
              Go to login →
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
          <p className="text-sm text-gray-500 mt-1">Create your account</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Full name</label>
              <input
                className="input text-sm"
                placeholder="Lucas Rapisardi"
                value={form.full_name}
                onChange={(e) => set("full_name", e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Workspace name</label>
              <input
                className="input text-sm"
                placeholder="Dimora Mediterranea"
                value={form.workspace_name}
                onChange={(e) => set("workspace_name", e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <input
                type="email"
                className="input text-sm"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Password</label>
              <input
                type="password"
                className="input text-sm"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
                required
                minLength={8}
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full justify-center text-sm mt-2"
            >
              {loading ? "Creating account…" : "Create account →"}
            </button>
          </form>

          <p className="text-xs text-gray-400 text-center mt-4">
            Already have an account?{" "}
            <a href="/login" className="text-brand-600 hover:underline">Sign in</a>
          </p>
        </div>
      </div>
    </div>
  );
}
