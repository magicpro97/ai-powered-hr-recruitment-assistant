import { generatePageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import ScreeningPageClient from "./ScreeningPageClient";

export const metadata: Metadata = generatePageMetadata("screening");

export default function ScreeningPage() {
  return <ScreeningPageClient />;
}
