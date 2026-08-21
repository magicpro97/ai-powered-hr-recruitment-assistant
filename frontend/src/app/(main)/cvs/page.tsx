import { generatePageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import CVsPageClient from "./CVsPageClient";

export const metadata: Metadata = generatePageMetadata("cvs");

export default function CVsPage() {
  return <CVsPageClient />;
}
