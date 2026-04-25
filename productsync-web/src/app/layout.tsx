import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ProductSync",
  description: "Product intelligence platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html>
      <body>{children}</body>
    </html>
  );
}
