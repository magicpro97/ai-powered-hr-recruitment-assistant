"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

function ResetPasswordForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { resetPassword, isLoading, error, clearError } = useAuth();
    const { t } = useLanguage();

    const token = searchParams.get("token") || "";

    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [formError, setFormError] = useState("");
    const [success, setSuccess] = useState(false);

    const validatePassword = (pwd: string): boolean => {
        return /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(pwd);
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setFormError("");
        clearError();

        if (!token) {
            setFormError("Invalid or missing reset token");
            return;
        }
        if (!validatePassword(password)) {
            setFormError(t.auth.passwordRequirements);
            return;
        }
        if (password !== confirmPassword) {
            setFormError(t.auth.passwordMismatch);
            return;
        }

        try {
            await resetPassword(token, password);
            setSuccess(true);
            setTimeout(() => router.push("/login"), 3000);
        } catch (err) {
            console.error("Reset password failed:", err);
        }
    };

    const displayError = formError || error;

    if (!token) {
        return (
            <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-blue-900 to-slate-900 px-4">
                <div className="w-full max-w-md text-center">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-red-500/20 rounded-full mb-4">
                        <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,9v2m0,4h.01m-6.938,4h13.856c1.54,0,2.502,-1.667,1.732,-3L13.732,4c-.77,-1.333,-2.694,-1.333,-3.464,0L3.34,16c-.77,1.333,.192,3,1.732,3z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">Invalid Reset Link</h2>
                    <p className="text-gray-400 mb-6">This password reset link is invalid or has expired.</p>
                    <Link
                        href="/forgot-password"
                        className="inline-flex items-center px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600 transition"
                    >
                        Request New Link
                    </Link>
                </div>
            </div>
        );
    }

    if (success) {
        return (
            <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-blue-900 to-slate-900 px-4">
                <div className="w-full max-w-md text-center">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-green-500 rounded-full mb-4">
                        <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5,13l4,4L19,7" />
                        </svg>
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-2">{t.auth.passwordReset}</h2>
                    <p className="text-gray-400">Redirecting to login...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-blue-900 to-slate-900 px-4">
            <div className="w-full max-w-md">
                {/* Logo/Brand */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-linear-to-br from-blue-500 to-indigo-600 rounded-2xl mb-4 shadow-lg shadow-blue-500/30">
                        <svg
                            className="w-8 h-8 text-white"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M15,7a2,2,0,012,2m4,0a6,6,0,01,-7.743,5.743L11,17H9v2H7v2H4a1,1,0,01,-1,-1v-2.586a1,1,0,01.293,-.707l5.964,-5.964A6,6,0,1121,9z"
                            />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white">HR Assistant</h1>
                    <p className="text-gray-400 mt-2">{t.auth.resetPassword}</p>
                </div>

                {/* Form Card */}
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-5 sm:p-8 shadow-xl border border-white/10">
                    <h2 className="text-xl font-semibold text-white mb-2">Set New Password</h2>
                    <p className="text-gray-400 text-sm mb-6">
                        Enter your new password below.
                    </p>

                    {displayError && (
                        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-200 text-sm">
                            {displayError}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Password */}
                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                                {t.auth.newPassword}
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="••••••••"
                                autoComplete="new-password"
                                disabled={isLoading}
                            />
                            <p className="mt-1 text-xs text-gray-500">{t.auth.passwordRequirements}</p>
                        </div>

                        {/* Confirm Password */}
                        <div>
                            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-300 mb-2">
                                {t.auth.confirmPassword}
                            </label>
                            <input
                                id="confirmPassword"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="••••••••"
                                autoComplete="new-password"
                                disabled={isLoading}
                            />
                        </div>

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full py-3 px-4 bg-linear-to-r from-blue-500 to-indigo-600 text-white font-medium rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                        >
                            {isLoading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4,12a8,8,0,018,-8V0C5.373,0,0,5.373,0,12h4zm2,5.291A7.962,7.962,0,014,12H0c0,3.042,1.135,5.824,3,7.938l3,-2.647z" />
                                    </svg>
                                    {t.auth.resetting}
                                </span>
                            ) : (
                                t.auth.resetPassword
                            )}
                        </button>
                    </form>

                    {/* Back to Login */}
                    <div className="mt-6 text-center">
                        <Link
                            href="/login"
                            className="inline-flex items-center text-gray-400 hover:text-white transition"
                        >
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10,19l-7,-7m0,0l7,-7m-7,7h18" />
                            </svg>
                            Back to login
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function ResetPasswordPage() {
    return (
        <Suspense fallback={
            <div className="min-h-[100dvh] flex items-center justify-center bg-linear-to-br from-slate-900 via-blue-900 to-slate-900">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
            </div>
        }>
            <ResetPasswordForm />
        </Suspense>
    );
}
