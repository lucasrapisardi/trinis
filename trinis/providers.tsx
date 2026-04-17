"use client";

import { SessionProvider } from "next-auth/react";
import { Toaster } from "react-hot-toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      {children}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            fontSize: "13px",
            borderRadius: "8px",
            border: "0.5px solid #e5e4de",
          },
        }}
      />
    </SessionProvider>
  );
}
