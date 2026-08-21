"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useGuestLimits } from "@/hooks/useGuestLimits";
import { useLanguage } from "@/i18n";
import Link from "next/link";

interface GuestBannerProps {
    variant?: "default" | "warning" | "compact";
    showUsage?: boolean;
    feature?: string;
    remaining?: number;
    total?: number;
}

export default function GuestBanner({
    variant = "default",
    showUsage = false,
    feature,
    remaining,
    total
}: GuestBannerProps) {
    const { isAuthenticated, isInitialized } = useAuth();
    const { t } = useLanguage();
    const { usage, limits, isGuest } = useGuestLimits();

    // Don't show for authenticated users or before initialization
    if (!isInitialized || isAuthenticated) {
        return null;
    }

    if (variant === "compact") {
        return (
            <div className="bg-linear-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg px-4 py-2 mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <span className="text-amber-600">👤</span>
                    <span className="text-sm text-amber-800">{t.guest?.mode || "Guest Mode"}</span>
                    {feature && remaining !== undefined && total !== undefined && (
                        <span className="text-xs text-amber-600 ml-2">
                            ({feature}: {remaining}/{total})
                        </span>
                    )}
                </div>
                <Link
                    href="/login"
                    className="text-sm font-medium text-amber-700 hover:text-amber-900 underline"
                >
                    {t.guest?.loginToSave || "Login to save"}
                </Link>
            </div>
        );
    }

    if (variant === "warning") {
        // Map feature prop to translated feature name
        const featureMap: Record<string, string> = {
            Job: t.guest?.quotaJobs || "job",
            CV: t.guest?.quotaCvs || "CV",
            Screening: t.guest?.quotaScreenings || "screenings",
        };
        const featureLabel = feature ? (featureMap[feature] || feature) : "";
        const limitLabel = total !== undefined ? String(total) : "";
        const limitReachedText = (t.guest?.limitReached || "Free {feature} limit reached ({limit})")
            .replace("{feature}", featureLabel)
            .replace("{limit}", limitLabel);

        return (
            <div className="bg-linear-to-r from-red-50 to-orange-50 border border-red-200 rounded-xl p-4 mb-6">
                <div className="flex items-start gap-3">
                    <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center shrink-0">
                        <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,9v2m0,4h.01m-6.938,4h13.856c1.54,0,2.502,-1.667,1.732,-3L13.732,4c-.77,-1.333,-2.694,-1.333,-3.464,0L3.34,16c-.77,1.333,.192,3,1.732,3z" />
                        </svg>
                    </div>
                    <div className="flex-1">
                        <h3 className="font-semibold text-red-800 mb-1">
                            {limitReachedText}
                        </h3>
                        <p className="text-sm text-red-700 mb-3">
                            {t.guest?.limitReachedDesc || "You've reached the guest limit. Sign in to continue."}
                        </p>
                        <Link
                            href="/login"
                            className="inline-flex items-center gap-2 bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
                        >
                            {t.auth?.login || "Sign In"}
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,5l7,7,-7,7" />
                            </svg>
                        </Link>
                    </div>
                </div>
            </div>
        );
    }

    // Default variant - value proposition banner
    return (
        <div className="bg-linear-to-r from-blue-50 via-indigo-50 to-purple-50 border border-blue-200 rounded-xl p-5 mb-6">
            <div className="flex flex-col md:flex-row md:items-center gap-4">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-semibold rounded-full">
                            👤 {t.guest?.mode || "Guest Mode"}
                        </span>
                    </div>
                    <h3 className="font-semibold text-slate-800 mb-2">
                        {t.guest?.valueTitle || "Sign in to unlock full features"}
                    </h3>
                    <ul className="text-sm text-slate-600 space-y-1">
                        <li className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707,5.293a1,1,0,010,1.414l-8,8a1,1,0,01,-1.414,0l-4,-4a1,1,0,011.414,-1.414L8,12.586l7.293,-7.293a1,1,0,011.414,0z" clipRule="evenodd" />
                            </svg>
                            {t.guest?.benefit1 || "Save your screening history permanently"}
                        </li>
                        <li className="flex items-center gap-2">
                            <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707,5.293a1,1,0,010,1.414l-8,8a1,1,0,01,-1.414,0l-4,-4a1,1,0,011.414,-1.414L8,12.586l7.293,-7.293a1,1,0,011.414,0z" clipRule="evenodd" />
                            </svg>
                            {t.guest?.benefit2 || "Unlimited CV uploads & screenings"}
                        </li>
                    </ul>

                    {showUsage && isGuest && (
                        <div className="mt-3 pt-3 border-t border-blue-200">
                            <p className="text-xs text-slate-500 mb-2">{t.guest?.currentUsage || "Current usage"}:</p>
                            <div className="flex gap-4 text-xs">
                                <span className="text-slate-600">
                                    Jobs: <strong>{usage.jobs}/{limits.MAX_JOBS}</strong>
                                </span>
                                <span className="text-slate-600">
                                    CVs: <strong>{usage.cvs}/{limits.MAX_CVS}</strong>
                                </span>
                                <span className="text-slate-600">
                                    Screenings: <strong>{usage.screenings}/{limits.MAX_SCREENINGS}</strong>
                                </span>
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex flex-col gap-2">
                    <Link
                        href="/login"
                        className="inline-flex items-center justify-center gap-2 bg-linear-to-r from-blue-600 to-indigo-600 text-white px-6 py-2.5 rounded-lg font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
                    >
                        {t.auth?.login || "Sign In"}
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,5l7,7,-7,7" />
                        </svg>
                    </Link>
                    <Link
                        href="/register"
                        className="text-center text-sm text-slate-500 hover:text-slate-700"
                    >
                        {t.guest?.noAccount || "Don't have an account?"} <span className="underline">{t.auth?.register || "Register"}</span>
                    </Link>
                </div>
            </div>
        </div>
    );
}
