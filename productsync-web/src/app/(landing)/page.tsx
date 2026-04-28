import { readFileSync } from "fs";
import { join } from "path";
import LandingClient from "./LandingClient";

export default function LandingPage() {
  const html = readFileSync(join(process.cwd(), "public/landing.html"), "utf-8");

  const styleMatches = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/gi)];
  const styles = styleMatches.map(m => m[1]).join("\n");

  const bodyMatch = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  const body = bodyMatch ? bodyMatch[1] : "";

  return <LandingClient styles={styles} body={body} />;
}
