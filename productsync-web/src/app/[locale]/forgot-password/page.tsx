// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/forgot-password/page.tsx
"use client";

import { useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_URL}/auth/forgot-password`, { email });
      setSent(true);
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-xl font-semibold text-gray-900">ProductSync</h1>
        </div>
        <div className="card">
          {sent ? (
            <div className="text-center space-y-3">
              <div className="text-3xl">📬</div>
              <h2 className="text-sm font-medium text-gray-900">Check your email</h2>
              <p className="text-xs text-gray-500">
                If an account exists for <span className="font-medium">{email}</span>,
                we&apos;ve sent a password reset link. Check your inbox and spam folder.
              </p>
              <a href="/login" className="btn btn-primary text-xs w-full justify-center mt-2 block">
                Back to login
              </a>
            </div>
          ) : (
            <>
              <h2 className="text-sm font-medium text-gray-900 mb-1">Forgot your password?</h2>
              <p className="text-xs text-gray-500 mb-4">
                Enter your email and we&apos;ll send you a reset link.
              </p>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Email</label>
                  <input
                    type="email"
                    className="input text-sm"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <button type="submit" disabled={loading} className="btn btn-primary w-full justify-center text-sm">
                  {loading ? "Sending…" : "Send reset link →"}
                </button>
              </form>
              <p className="text-xs text-gray-400 text-center mt-4">
                <a href="/login" className="hover:text-gray-600">← Back to login</a>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
