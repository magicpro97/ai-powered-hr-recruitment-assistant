import type { MetadataRoute } from "next";

/**
 * PWA Web App Manifest for mobile SEO and installability
 * @see https://nextjs.org/docs/app/api-reference/file-conventions/metadata/manifest
 */
export default function manifest(): MetadataRoute.Manifest {
    return {
        name: "HR Assistant - AI-Powered CV Screening",
        short_name: "HR Assistant",
        description:
            "Công cụ tuyển dụng AI - Sàng lọc CV tự động, đánh giá ứng viên thông minh",
        start_url: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#0369A1",
        orientation: "portrait-primary",
        categories: ["business", "productivity"],
        icons: [
            {
                src: "/icon-192.png",
                sizes: "192x192",
                type: "image/png",
                purpose: "maskable",
            },
            {
                src: "/icon-512.png",
                sizes: "512x512",
                type: "image/png",
                purpose: "any",
            },
        ],
        related_applications: [],
        prefer_related_applications: false,
    };
}
