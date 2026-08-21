"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";
import { FormEvent, useState } from "react";

export default function ForgotPasswordPage() {
    const { forgotPassword, isLoading, error, clearError } = useAuth();
    const { t } = useLanguage();

    const [email, setEmail] = useState("");
    const [formError, setFormError] = useState("");
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setFormError("");
        clearError();
        setSuccess(false);

        if (!email) {
            setFormError("Please enter your email");
            return;
        }

        try {
            await forgotPassword(email);
            setSuccess(true);
        } catch (err) {
            console.error("Forgot password failed:", err);
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
                                d="M15,7a2,2,0,012,2m4,0a6,6,0,01,-7.743,5.743L11,17H9v2H7v2H4a1,1,0,01,-1,-1v-2.586a1,1,0,01.293,-.707l5.964,-5.964A6,6,0,1121,9z"
                            />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white">HR Assistant</h1>
                    <p className="text-gray-400 mt-2">{t.auth.forgotPassword}</p>
                </div>

                {/* Form Card */}
                <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-5 sm:p-8 shadow-xl border border-white/10">
                    {success ? (
                        <div className="text-center">
                            <div className="inline-flex items-center justify-center w-12 h-12 bg-green-500/20 rounded-full mb-4">
                                <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5,13l4,4L19,7" />
                                </svg>
                            </div>
                            <h2 className="text-lg font-semibold text-white mb-2">Email Sent</h2>
                            <p className="text-gray-400 text-sm mb-6">{t.auth.resetEmailSent}</p>
                            <Link
                                href="/login"
                                className="inline-flex items-center text-blue-400 hover:text-blue-300 transition"
                            >
                                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10,19l-7,-7m0,0l7,-7m-7,7h18" />
                                </svg>
                                Back to login
                            </Link>
                        </div>
                    ) : (
                        <>
                            <h2 className="text-xl font-semibold text-white mb-2">{t.auth.resetPassword}</h2>
                            <p className="text-gray-400 text-sm mb-6">
                                Enter your email and we&apos;ll send you a link to reset your password.
                            </p>

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
                                            {t.auth.sendingReset}
                                        </span>
                                    ) : (
                                        "Send Reset Link"
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
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
