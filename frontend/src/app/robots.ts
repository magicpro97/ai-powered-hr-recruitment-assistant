import type { MetadataRoute } from "next";

/**
 * Dynamic robots.txt generation for SEO
 * @see https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots
 */
export default function robots(): MetadataRoute.Robots {
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

    return {
        rules: [
            {
                userAgent: "*",
                allow: "/",
                disallow: [
                    "/api/", // API routes
                    "/login", // Auth pages
                    "/register",
                    "/forgot-password",
                    "/reset-password",
                    "/dashboard", // Private dashboard areas
                    "/screening/", // Private screening results
                ],
            },
            {
                userAgent: "Googlebot",
                allow: "/",
                disallow: ["/api/", "/login", "/register"],
            },
        ],
        sitemap: `${baseUrl}/sitemap.xml`,
        host: baseUrl,
    };
}
