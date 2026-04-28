"use client";
import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

interface Props {
  styles: string;
  body: string;
}

export default function LandingClient({ styles, body }: Props) {
  const { data: session, status } = useSession();
  const router = useRouter();

  // Patch login links after mount to redirect authenticated users to dashboard
  useEffect(() => {
    if (status === "authenticated" && session) {
      // Replace all /login links with /en/dashboard
      const links = document.querySelectorAll<HTMLAnchorElement>('a[href="/login"]');
      links.forEach((a) => {
        a.href = "/en/dashboard";
        a.textContent = "Dashboard →";
      });
    }
  }, [status, session]);

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: styles }} />
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap"
        rel="stylesheet"
      />
      <div dangerouslySetInnerHTML={{ __html: body }} />
    </>
  );
}
