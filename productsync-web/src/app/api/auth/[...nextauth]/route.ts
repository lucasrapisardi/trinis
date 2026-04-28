// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

// Access token expires in 60 min — refresh 5 min before expiry
const ACCESS_TOKEN_EXPIRE_MS = 55 * 60 * 1000;

async function refreshAccessToken(token: Record<string, unknown>) {
  try {
    const res = await axios.post(`${API_URL}/auth/refresh`, {
      refresh_token: token.refresh_token,
    });
    const { access_token, refresh_token } = res.data;
    return {
      ...token,
      access_token,
      refresh_token: refresh_token ?? token.refresh_token,
      access_token_expires_at: Date.now() + ACCESS_TOKEN_EXPIRE_MS,
      error: undefined,
    };
  } catch {
    return { ...token, error: "RefreshAccessTokenError" };
  }
}

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const tokenRes = await axios.post(`${API_URL}/auth/login`, {
            email: credentials.email,
            password: credentials.password,
          }, {
            headers: { "ngrok-skip-browser-warning": "true" },
          });
          const { access_token, refresh_token } = tokenRes.data;
          const meRes = await axios.get(`${API_URL}/auth/me`, {
            headers: {
              Authorization: `Bearer ${access_token}`,
              "ngrok-skip-browser-warning": "true",
            },
          });
          return { ...meRes.data, access_token, refresh_token };
        } catch (err: unknown) {
          const detail = (err as { response?: { data?: { detail?: { code?: string } | string } } })
            ?.response?.data?.detail;
          if (detail && typeof detail === "object" && detail.code === "email_not_confirmed") {
            throw new Error("email_not_confirmed");
          }
          return null;
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user }) {
      // First sign in — store tokens and expiry
      if (user) {
        return {
          ...token,
          id: user.id,
          email: user.email,
          full_name: user.full_name,
          tenant_id: user.tenant_id,
          is_owner: user.is_owner,
          access_token: user.access_token,
          refresh_token: user.refresh_token,
          access_token_expires_at: Date.now() + ACCESS_TOKEN_EXPIRE_MS,
          tour_completed: user.tour_completed ?? false,
          error: undefined,
        };
      }

      // Token still valid
      if (Date.now() < (token.access_token_expires_at as number)) {
        return token;
      }

      // Token expired — refresh it
      return refreshAccessToken(token as Record<string, unknown>);
    },

    async session({ session, token }) {
      session.user = {
        id: token.id as string,
        email: token.email as string,
        full_name: token.full_name as string | null,
        tenant_id: token.tenant_id as string,
        is_owner: token.is_owner as boolean,
        access_token: token.access_token as string,
        refresh_token: token.refresh_token as string,
        tour_completed: token.tour_completed as boolean,
      };
      // Expose refresh error to client so it can redirect to login
      session.error = token.error as string | undefined;
      return session;
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  },

  secret: process.env.NEXTAUTH_SECRET,
});

export { handler as GET, handler as POST };
