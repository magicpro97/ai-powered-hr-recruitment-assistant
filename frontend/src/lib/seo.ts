import type { Metadata } from "next";

/**
 * SEO utilities and constants for HR Assistant
 *
 * Set NEXT_PUBLIC_APP_URL in production (e.g., https://your-domain.com)
 */

const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
const SITE_NAME = "HR Assistant";
const DEFAULT_LOCALE = "vi_VN";

/**
 * Default metadata configuration
 */
export const defaultMetadata: Metadata = {
    metadataBase: new URL(BASE_URL),
    title: {
        default: "HR Assistant - AI-Powered CV Screening & Recruitment",
        template: "%s | HR Assistant",
    },
    description:
        "Công cụ tuyển dụng AI để sàng lọc CV, đánh giá ứng viên và tạo câu hỏi phỏng vấn.",
    keywords: [
        "HR software",
        "CV screening",
        "AI recruitment",
        "candidate matching",
        "hiring tool",
        "phần mềm tuyển dụng",
        "sàng lọc CV",
        "AI HR",
        "tuyển dụng thông minh",
        "đánh giá ứng viên",
    ],
    authors: [{ name: "HR Assistant Team" }],
    creator: "HR Assistant",
    publisher: "HR Assistant",
    formatDetection: {
        email: false,
        address: false,
        telephone: false,
    },
    robots: {
        index: true,
        follow: true,
        googleBot: {
            index: true,
            follow: true,
            "max-video-preview": -1,
            "max-image-preview": "large",
            "max-snippet": -1,
        },
    },
    openGraph: {
        type: "website",
        locale: DEFAULT_LOCALE,
        alternateLocale: ["en_US"],
        url: BASE_URL,
        siteName: SITE_NAME,
        title: "HR Assistant - AI-Powered CV Screening & Recruitment",
        description:
            "Công cụ tuyển dụng AI để sàng lọc CV và đánh giá ứng viên.",
    },
    twitter: {
        card: "summary",
        title: "HR Assistant - AI CV Screening",
        description: "Công cụ tuyển dụng AI để sàng lọc CV tự động.",
    },
    alternates: {
        canonical: BASE_URL,
        languages: {
            "vi-VN": BASE_URL,
            "en-US": BASE_URL,
        },
    },
    category: "technology",
    classification: "Business Software",
};

/**
 * JSON-LD Structured Data for WebApplication
 */
export function generateWebApplicationSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        name: SITE_NAME,
        description:
            "AI-powered HR recruitment assistant for CV screening and candidate matching",
        url: BASE_URL,
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web Browser",
        offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "USD",
            description: "Free tier available",
        },
        featureList: [
            "AI-powered CV screening",
            "Candidate matching",
            "Interview question generation",
            "Multi-language support (Vietnamese, English)",
        ],
        softwareVersion: "1.0.0",
        author: {
            "@type": "Organization",
            name: "HR Assistant Team",
        },
    };
}

/**
 * JSON-LD Structured Data for Organization
 */
export function generateOrganizationSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        name: SITE_NAME,
        url: BASE_URL,
        description: "AI-powered HR recruitment platform",
        sameAs: [
            // Add social media links when available
        ],
        contactPoint: {
            "@type": "ContactPoint",
            contactType: "customer service",
            availableLanguage: ["Vietnamese", "English"],
        },
    };
}

/**
 * JSON-LD Structured Data for BreadcrumbList
 */
export function generateBreadcrumbSchema(
    items: Array<{ name: string; url: string }>
) {
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: items.map((item, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: item.name,
            item: `${BASE_URL}${item.url}`,
        })),
    };
}

/**
 * JSON-LD Structured Data for SoftwareApplication (for app stores)
 */
export function generateSoftwareApplicationSchema() {
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: SITE_NAME,
        description:
            "Streamline your recruitment with AI-powered CV screening and candidate matching",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Any",
        offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "USD",
        },
    };
}

/**
 * Page-specific metadata generators
 */
export const pageMetadata = {
    home: {
        title: "HR Assistant - AI-Powered CV Screening & Recruitment",
        description:
            "Công cụ tuyển dụng AI để sàng lọc CV, đánh giá ứng viên và tạo câu hỏi phỏng vấn.",
    },
    jobs: {
        title: "Quản lý Job Description",
        description:
            "Tạo và quản lý Job Description. AI tự động phân tích yêu cầu công việc để sàng lọc ứng viên phù hợp nhất.",
    },
    cvs: {
        title: "Quản lý CV Ứng viên",
        description:
            "Upload và quản lý CV ứng viên. AI tự động trích xuất thông tin, đánh giá kỹ năng và kinh nghiệm.",
    },
    screening: {
        title: "Sàng lọc & Đánh giá Ứng viên",
        description:
            "Sàng lọc ứng viên tự động với AI. So khớp CV với Job Description, xếp hạng ứng viên phù hợp nhất.",
    },
    login: {
        title: "Đăng nhập",
        description: "Đăng nhập vào HR Assistant để quản lý tuyển dụng.",
        robots: { index: false, follow: false },
    },
    register: {
        title: "Đăng ký tài khoản",
        description: "Đăng ký tài khoản HR Assistant miễn phí.",
        robots: { index: false, follow: false },
    },
};

/**
 * Generate page metadata with defaults
 */
export function generatePageMetadata(
    page: keyof typeof pageMetadata,
    overrides?: Partial<Metadata>
): Metadata {
    const pageMeta = pageMetadata[page];
    return {
        title: pageMeta.title,
        description: pageMeta.description,
        openGraph: {
            title: pageMeta.title,
            description: pageMeta.description,
        },
        twitter: {
            title: pageMeta.title,
            description: pageMeta.description,
        },
        ...("robots" in pageMeta ? { robots: pageMeta.robots } : {}),
        ...overrides,
    };
}
