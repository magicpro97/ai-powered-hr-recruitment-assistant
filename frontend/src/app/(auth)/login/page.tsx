"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
    const router = useRouter();
    const { login, isLoading, error, clearError } = useAuth();
    const { t } = useLanguage();

    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [formError, setFormError] = useState("");

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setFormError("");
        clearError();

        if (!email || !password) {
            setFormError(t.auth.invalidCredentials);
            return;
        }

        try {
            await login(email, password);
            // Full page reload to reset all component states with authenticated context
            window.location.href = "/dashboard";
        } catch (err) {
            // Check if account is locked (error message contains "locked until")
            const errorMessage = err instanceof Error ? err.message : "";
            if (errorMessage.toLowerCase().includes("locked")) {
                // Extract timestamp from error message if present
                const match = errorMessage.match(/until\s+(.+)/i);
                const lockedUntil = match ? encodeURIComponent(match[1]) : "";
                router.push(`/account-locked${lockedUntil ? `?until=${lockedUntil}` : ""}`);
                return;
            }
            // Error is already set in AuthContext
            console.error("Login failed:", err);
        }
    };

    const displayError = formError || error;

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
                                d="M16,7a4,4,0,11,-8,0,4,4,0,018,0zM12,14a7,7,0,00,-7,7h14a7,7,0,00,-7,-7z"
                            />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white">HR Assistant</h1>
                    <p className="text-gray-400 mt-2">AI-Powered Recruitment</p>
                </div>

                {/* Login Form Card */}
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-5 sm:p-8 shadow-xl border border-white/10">
                    <h2 className="text-xl font-semibold text-white mb-6">{t.auth.login}</h2>

                    {displayError && (
                        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-200 text-sm">
                            {displayError}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Email */}
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                                {t.auth.email}
                            </label>
                            <input
                                id="email"
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="name@example"
                                autoComplete="email"
                                disabled={isLoading}
                            />
                        </div>

                        {/* Password */}
                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                                {t.auth.password}
                            </label>
                            <input
                                id="password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                                placeholder="••••••••"
                                autoComplete="current-password"
                                disabled={isLoading}
                            />
                        </div>

                        {/* Forgot Password Link */}
                        <div className="flex justify-end">
                            <Link
                                href="/forgot-password"
                                className="text-sm text-blue-400 hover:text-blue-300 transition"
                            >
                                {t.auth.forgotPassword}
                            </Link>
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
                                        <circle
                                            className="opacity-25"
                                            cx="12"
                                            cy="12"
                                            r="10"
                                            stroke="currentColor"
                                            strokeWidth="4"
                                        />
                                        <path
                                            className="opacity-75"
                                            fill="currentColor"
                                            d="M4,12a8,8,0,018,-8V0C5.373,0,0,5.373,0,12h4zm2,5.291A7.962,7.962,0,014,12H0c0,3.042,1.135,5.824,3,7.938l3,-2.647z"
                                        />
                                    </svg>
                                    {t.auth.loggingIn}
                                </span>
                            ) : (
                                t.auth.login
                            )}
                        </button>
                    </form>

                    {/* Divider */}
                    <div className="relative my-6">
                        <div className="absolute inset-0 flex items-center">
                            <div className="w-full border-t border-white/10"></div>
                        </div>
                        <div className="relative flex justify-center text-sm">
                            <span className="px-2 bg-transparent text-gray-500">{t.auth.noAccount}</span>
                        </div>
                    </div>

                    {/* Register Link */}
                    <Link
                        href="/register"
                        className="block w-full py-3 px-4 text-center bg-white/5 border border-white/10 text-white font-medium rounded-xl hover:bg-white/10 transition"
                    >
                        {t.auth.signUp}
                    </Link>
                </div>

                {/* Footer */}
                <p className="text-center text-gray-500 text-sm mt-8">
                    © 2025 HR Assistant. AI-Powered Recruitment.
                </p>
            </div>
        </div>
    );
}
