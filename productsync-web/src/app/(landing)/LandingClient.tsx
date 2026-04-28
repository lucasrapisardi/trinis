"use client";
import { useEffect } from "react";
import { useSession } from "next-auth/react";

interface Props {
  styles: string;
  body: string;
}

export default function LandingClient({ styles, body }: Props) {
  const { data: session, status } = useSession();

  useEffect(() => {
    if (status === "loading") return;

    const links = document.querySelectorAll<HTMLAnchorElement>('a[href="/login"]');
    links.forEach((a) => {
      if (status === "authenticated" && session) {
        a.textContent = "Dashboard →";
        a.onclick = (e) => {
          e.preventDefault();
          e.stopPropagation();
          window.location.assign("/en/dashboard");
        };
      }
    });
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
