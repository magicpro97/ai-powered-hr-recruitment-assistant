"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function AccountLockedContent() {
    const searchParams = useSearchParams();
    const lockedUntil = searchParams.get("until");

    const [remainingTime, setRemainingTime] = useState<number>(() => {
        if (!lockedUntil) return 0;
        const until = new Date(lockedUntil).getTime();
        return Math.max(0, Math.floor((until - Date.now()) / 1000));
    });
    const [isExpired, setIsExpired] = useState(() => {
        if (!lockedUntil) return true;
        return new Date(lockedUntil).getTime() <= Date.now();
    });

    useEffect(() => {
        if (!lockedUntil) return;

        const interval = setInterval(() => {
            const until = new Date(lockedUntil).getTime();
            const remaining = Math.max(0, Math.floor((until - Date.now()) / 1000));

            if (remaining <= 0) {
                setIsExpired(true);
                setRemainingTime(0);
            } else {
                setRemainingTime(remaining);
                setIsExpired(false);
            }
        }, 1000);
        return () => clearInterval(interval);
    }, [lockedUntil]);

    const formatTime = (seconds: number): string => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, "0")}`;
    };

    return (
        <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-red-900/50 to-slate-900 px-4">
            <div className="w-full max-w-md">
                {/* Warning Icon */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-20 h-20 bg-linear-to-br from-red-500 to-orange-600 rounded-full mb-4 shadow-lg shadow-red-500/30">
                        <svg
                            className="w-10 h-10 text-white"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                            />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white">Account Temporarily Locked</h1>
                    <p className="text-gray-400 mt-2">Too many failed login attempts</p>
                </div>

                {/* Lockout Card */}
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-5 sm:p-8 shadow-xl border border-red-500/20">
                    {isExpired ? (
                        <>
                            <div className="text-center mb-6">
                                <div className="inline-flex items-center justify-center w-16 h-16 bg-green-500/20 rounded-full mb-4">
                                    <svg
                                        className="w-8 h-8 text-green-400"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                    >
                                        <path
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            strokeWidth={2}
                                            d="M5 13l4 4L19 7"
                                        />
                                    </svg>
                                </div>
                                <h2 className="text-xl font-semibold text-white mb-2">
                                    Lockout Expired
                                </h2>
                                <p className="text-gray-300">
                                    Your account is now unlocked. You can try logging in again.
                                </p>
                            </div>
                            <Link
                                href="/login"
                                className="block w-full py-3 px-4 bg-linear-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl text-center shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200"
                            >
                                Return to Login
                            </Link>
                        </>
                    ) : (
                        <>
                            <div className="text-center mb-6">
                                <p className="text-gray-300 mb-4">
                                    For security reasons, your account has been temporarily locked after multiple failed login attempts.
                                </p>

                                {/* Countdown Timer */}
                                <div className="inline-flex items-center justify-center w-32 h-32 bg-red-500/20 rounded-full mb-4 border-4 border-red-500/40">
                                    <span className="text-3xl sm:text-4xl font-mono font-bold text-red-400">
                                        {formatTime(remainingTime)}
                                    </span>
                                </div>

                                <p className="text-gray-400 text-sm">
                                    Please wait until the timer expires to try again
                                </p>
                            </div>

                            {/* Security Tips */}
                            <div className="bg-white/5 rounded-xl p-4 mb-6">
                                <h3 className="text-sm font-semibold text-gray-200 mb-2 flex items-center gap-2">
                                    <svg className="w-4 h-4 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    Security Tips
                                </h3>
                                <ul className="text-sm text-gray-400 space-y-1">
                                    <li>• Use a strong, unique password</li>
                                    <li>• Check for typos in your email</li>
                                    <li>• Use &quot;Forgot Password&quot; if needed</li>
                                </ul>
                            </div>

                            <div className="flex gap-3">
                                <Link
                                    href="/forgot-password"
                                    className="flex-1 py-3 px-4 bg-white/10 hover:bg-white/20 text-white font-medium rounded-xl text-center transition-all duration-200"
                                >
                                    Reset Password
                                </Link>
                                <Link
                                    href="/"
                                    className="flex-1 py-3 px-4 bg-white/10 hover:bg-white/20 text-white font-medium rounded-xl text-center transition-all duration-200"
                                >
                                    Go Home
                                </Link>
                            </div>
                        </>
                    )}
                </div>

                {/* Contact Support */}
                <p className="text-center text-gray-500 text-sm mt-6">
                    Need help? Open an issue on{" "}
                    <a href="https://github.com/magicpro97/ai-powered-hr-recruitment-assistant/issues" className="text-blue-400 hover:text-blue-300">
                        GitHub
                    </a>
                </p>
            </div>
        </div>
    );
}

function LoadingFallback() {
    return (
        <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-red-900/50 to-slate-900">
            <div className="animate-pulse text-white">Loading...</div>
        </div>
    );
}

export default function AccountLockedPage() {
    return (
        <Suspense fallback={<LoadingFallback />}>
            <AccountLockedContent />
        </Suspense>
    );
}
