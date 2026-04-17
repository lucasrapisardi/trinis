// PATH: src/app/api/auth/[...nextauth]/route.ts
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

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
          });
          const { access_token, refresh_token } = tokenRes.data;
          const meRes = await axios.get(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${access_token}` },
          });
          return { ...meRes.data, access_token, refresh_token };
        } catch {
          return null;
        }
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.email = user.email;
        token.full_name = user.full_name;
        token.tenant_id = user.tenant_id;
        token.is_owner = user.is_owner;
        token.access_token = user.access_token;
        token.refresh_token = user.refresh_token;
      }
      return token;
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
      };
      return session;
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 24 * 30,
  },

  secret: process.env.NEXTAUTH_SECRET,
});

export { handler as GET, handler as POST };
