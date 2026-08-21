import { describe, expect, test } from "bun:test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { extname, join, relative, resolve } from "node:path";

const FRONTEND_ROOT = resolve(import.meta.dir, "../..");
const SOURCE_ROOT = join(FRONTEND_ROOT, "src");
const PUBLIC_ROOT = join(FRONTEND_ROOT, "public");
const approvedPageFiles = [
  "(auth)/account-locked/page.tsx",
  "(auth)/forgot-password/page.tsx",
  "(auth)/login/page.tsx",
  "(auth)/register/page.tsx",
  "(auth)/reset-password/page.tsx",
  "(main)/cvs/page.tsx",
  "(main)/dashboard/page.tsx",
  "(main)/jobs/page.tsx",
  "(main)/screening/page.tsx",
  "(main)/settings/page.tsx",
  "page.tsx",
];

const excludedPaths = [
  "src/app/(main)/admin",
  "src/app/(main)/agent",
  "src/app/(main)/calibration",
  "src/app/(main)/evaluation",
  "src/app/(main)/expert",
  "src/app/(main)/question-review",
  "src/app/(main)/research",
  "src/app/evaluation-guide",
  "src/app/user-guide",
  "src/components/ExperimentDashboard.tsx",
  "src/components/FeedbackWidget.tsx",
  "src/components/GuideHint.tsx",
  "src/components/ITviecImport.tsx",
  "src/components/JobImport.tsx",
  "src/components/MessageFeedback.tsx",
  "src/components/PageGuide.tsx",
  "src/components/RecruiterEvaluation.tsx",
  "src/components/SUSQuestionnaire.tsx",
  "src/components/Tour",
  "src/components/WelcomeModal.tsx",
  "src/lib/report-formatters.test.ts",
  "src/lib/report-formatters.ts",
];

function runtimeSources() {
  return readdirSync(SOURCE_ROOT, { recursive: true })
    .map(String)
    .filter((path) => [".ts", ".tsx"].includes(extname(path)))
    .filter((path) => path !== "lib/public-scope.test.ts")
    .map((path) => [path, readFileSync(join(SOURCE_ROOT, path), "utf8")] as const)
    .concat([["next.config.ts", readFileSync(join(FRONTEND_ROOT, "next.config.ts"), "utf8")]]);
}

describe("public frontend scope", () => {
  test("exposes exactly the approved App Router pages", () => {
    const pageFiles = readdirSync(join(SOURCE_ROOT, "app"), { recursive: true })
      .map(String)
      .filter((path) => path.endsWith("page.tsx"))
      .sort();

    expect(pageFiles).toEqual(approvedPageFiles);
  });

  test("excludes private and research UI", () => {
    expect(excludedPaths.filter((path) => existsSync(join(FRONTEND_ROOT, path)))).toEqual([]);
  });

  test("has no excluded routes, endpoints, imports, media, or deployment literals", () => {
    const forbidden = /\/(?:admin|agent|calibration|evaluation|expert|question-review|research|evaluation-guide|user-guide)(?:\/|["'`?#])|\/api\/feedback|\/(?:images\/guide|videos)\/|\b(?:ITviecImport|JobImport)\b|screener\.work|trycloudflare\.com/i;
    const findings = runtimeSources()
      .filter(([, source]) => forbidden.test(source))
      .map(([path]) => path);

    expect(findings).toEqual([]);
  });

  test("references only checked-in local media", () => {
    const assetPattern = /\/(?:[\w.-]+\/)*[\w.-]+\.(?:gif|ico|jpe?g|mov|mp4|png|svg|webm|webp)(?![\w.])/g;
    const missing = runtimeSources().flatMap(([path, source]) =>
      [...source.matchAll(assetPattern)]
        .map(([asset]) => asset)
        .filter((asset) => !existsSync(join(PUBLIC_ROOT, asset)))
        .map((asset) => `${relative(FRONTEND_ROOT, path)}: ${asset}`),
    );

    expect([...new Set(missing)]).toEqual([]);
  });

  test("has no research, report, removed-feature, or unsupported claim residue", () => {
    const forbidden = /\b(?:canAccessResearch|requireResearcher|researcher|formatSummaryTableCsv|formatSummaryTableLatex|ReportCell|SummaryTable|benefit3|exportLocked|evaluateCta|evaluateCtaButton|demoVideoTitle|demoVideoDesc|continueToEvaluation|userGuide)\b|75%|23\s*(?:hours|giờ)|(?:in|trong)\s+(?:a few\s+)?minutes|vài phút|HTTPS\s*\+\s*ClamAV|\bAnonymized\b|aggregated\/anonymized|tổng hợp ẩn danh|evaluation feedback|phần đánh giá|Export PDF|Xuất PDF|professional PDF reports|báo cáo PDF chuyên nghiệp|Evaluation feature|tính năng Đánh giá|detailed reports|báo cáo chi tiết|agent-skills|vercel-labs/i;
    const findings = runtimeSources()
      .filter(([, source]) => forbidden.test(source))
      .map(([path]) => path);

    expect(findings).toEqual([]);
  });

  test("keeps only narrow bilingual public-boundary wording", () => {
    const translations = readFileSync(join(SOURCE_ROOT, "i18n/translations.ts"), "utf8");

    expect(translations).toContain("luận văn Thạc sĩ");
    expect(translations).toContain("Master's thesis");
    expect(translations).toContain("Dữ liệu tổng hợp");
    expect(translations).toContain("Synthetic data");
    expect(translations).toContain("quyết định tuyển dụng");
    expect(translations).toContain("hiring decisions");
  });
});
