import type { MetadataRoute } from "next";

/**
 * Dynamic sitemap generation for SEO
 * @see https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap
 */
export default function sitemap(): MetadataRoute.Sitemap {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
    const lastModified = new Date();

    // Static pages that should be indexed
    const staticPages: MetadataRoute.Sitemap = [
        {
            url: baseUrl,
            lastModified,
            changeFrequency: "weekly",
            priority: 1.0,
            alternates: {
                languages: {
                    vi: `${baseUrl}`,
                    en: `${baseUrl}`,
                },
            },
        },
        {
            url: `${baseUrl}/jobs`,
            lastModified,
            changeFrequency: "daily",
            priority: 0.9,
            alternates: {
                languages: {
                    vi: `${baseUrl}/jobs`,
                    en: `${baseUrl}/jobs`,
                },
            },
        },
        {
            url: `${baseUrl}/cvs`,
            lastModified,
            changeFrequency: "daily",
            priority: 0.8,
            alternates: {
                languages: {
                    vi: `${baseUrl}/cvs`,
                    en: `${baseUrl}/cvs`,
                },
            },
        },
    ];

    return staticPages;
}
