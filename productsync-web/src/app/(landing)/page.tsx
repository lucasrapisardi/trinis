import { readFileSync } from "fs";
import { join } from "path";

export default function LandingPage() {
  const html = readFileSync(join(process.cwd(), "public/landing.html"), "utf-8");
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}
