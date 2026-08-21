import { generatePageMetadata } from "@/lib/seo";
import type { Metadata } from "next";
import JobsPageClient from "./JobsPageClient";

export const metadata: Metadata = generatePageMetadata("jobs");

export default function JobsPage() {
  return <JobsPageClient />;
}
