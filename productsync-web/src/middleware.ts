import createMiddleware from "next-intl/middleware";
import { defineRouting } from "next-intl/routing";
import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

const routing = defineRouting({
  locales: ["en", "pt", "es"],
  defaultLocale: "en",
  localeDetection: true,
});

const intlMiddleware = createMiddleware(routing);

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/confirm-email",
  "/accept-invite",
];

function isPublicPath(pathname: string) {
  const stripped = pathname.replace(/^\/(en|pt|es)/, "") || "/";
  return PUBLIC_PATHS.some((p) => stripped.startsWith(p));
}

export default async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Landing page — bypass intl and auth
  if (pathname === "/") return NextResponse.next();

  // Always run intl middleware
  const intlResponse = intlMiddleware(req);

  // Public paths — no auth needed
  if (isPublicPath(pathname)) return intlResponse;

  // Check auth token
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!token) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", req.url);
    return NextResponse.redirect(loginUrl);
  }

  return intlResponse;
}

export const config = {
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon.ico).*)",
  ],
};
