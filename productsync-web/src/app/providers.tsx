// PATH: /home/lumoura/trinis_ai/productsync-web/src/app/providers.tsx
"use client";

import { SessionProvider, useSession, signOut } from "next-auth/react";
import { Toaster } from "react-hot-toast";
import { useEffect } from "react";

function SessionErrorHandler() {
  const { data: session } = useSession();

  useEffect(() => {
    // If token refresh failed, sign out and redirect to login
    if (session?.error === "RefreshAccessTokenError") {
      signOut({ callbackUrl: "/login" });
    }
  }, [session?.error]);

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider
      // Re-fetch session every 5 minutes to detect expiry
      refetchInterval={5 * 60}
      refetchOnWindowFocus={true}
    >
      <SessionErrorHandler />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            fontSize: "13px",
            borderRadius: "8px",
            border: "1px solid #e5e7eb",
          },
        }}
      />
      {children}
    </SessionProvider>
  );
}
