import type { Metadata } from "next";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "ProductSync",
  description: "Product intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
