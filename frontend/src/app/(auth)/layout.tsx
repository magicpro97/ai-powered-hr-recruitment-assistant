import type { Metadata } from "next";

/**
 * Auth pages should not be indexed by search engines
 */
export const metadata: Metadata = {
    robots: {
        index: false,
        follow: false,
        nocache: true,
        googleBot: {
            index: false,
            follow: false,
            noimageindex: true,
        },
    },
};

export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <>
            {/* Full screen auth pages without sidebar */}
            {children}
        </>
    );
}
