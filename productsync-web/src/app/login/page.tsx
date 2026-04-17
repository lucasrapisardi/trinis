// PATH: src/app/login/page.tsx
"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [unconfirmed, setUnconfirmed] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    setLoading(false);

    if (result?.error) {
      toast.error("Invalid email or password");
    } else {
      router.push("/");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-medium text-gray-900">ProductSync</h1>
          <p className="text-sm text-gray-500 mt-1">Sign in to your account</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Email</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1.5">Password</label>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary w-full mt-2"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        {unconfirmed && (
          <div className="mt-3 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2.5 text-xs text-amber-700">
            <p className="font-medium mb-1">Email not confirmed</p>
            <p className="text-amber-600">Please check your inbox and click the confirmation link.</p>
            <button
              onClick={async () => {
                const { default: axios } = await import("axios");
                await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/auth/resend-confirmation`, { email });
                toast.success("Confirmation email resent!");
              }}
              className="text-amber-700 underline mt-1 block"
            >
              Resend confirmation email →
            </button>
          </div>
        )}
        <p className="text-center text-sm text-gray-500 mt-4">
          Forgot password? <a href="/forgot-password" className="text-xs text-gray-400 hover:text-gray-600 block mb-2">Reset it here</a>
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-brand-600 hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
