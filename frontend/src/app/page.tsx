"use client";

import { BriefcaseIcon } from "@/components/icons";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";

export default function LandingPage() {
    const { t, language, setLanguage } = useLanguage();
    const { user, isAuthenticated, isInitialized } = useAuth();

    return (
        <div className="min-h-[100dvh] bg-[#FAFBFF] text-[#0F172A] overflow-x-hidden">
            {/* ── Navbar ── */}
            <header className="fixed top-0 inset-x-0 z-50 backdrop-blur-md bg-white/70 border-b border-[#E2E8F0]/60">
                <div className="max-w-6xl mx-auto flex items-center justify-between px-6 h-16">
                    <Link href="/" className="flex items-center gap-2.5">
                        <span className="w-9 h-9 rounded-lg bg-[#0369A1] text-white flex items-center justify-center">
                            <BriefcaseIcon className="w-5 h-5" />
                        </span>
                        <span className="text-lg font-bold tracking-tight text-[#0F172A]">
                            CV Screener
                        </span>
                    </Link>
                    <div className="flex items-center gap-3">
                        {/* Language toggle */}
                        <div className="flex items-center bg-[#F1F5F9] rounded-lg p-0.5">
                            <button
                                onClick={() => setLanguage("vi")}
                                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                                    language === "vi"
                                        ? "bg-[#0369A1] text-white shadow-sm"
                                        : "text-[#64748B] hover:text-[#0F172A]"
                                }`}
                            >
                                VI
                            </button>
                            <button
                                onClick={() => setLanguage("en")}
                                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all cursor-pointer ${
                                    language === "en"
                                        ? "bg-[#0369A1] text-white shadow-sm"
                                        : "text-[#64748B] hover:text-[#0F172A]"
                                }`}
                            >
                                EN
                            </button>
                        </div>
                        {isInitialized && isAuthenticated && user ? (
                            <>
                                <span className="text-sm font-medium text-[#0F172A] hidden sm:inline-block">
                                    {user.name}
                                </span>
                                <Link
                                    href="/dashboard"
                                    className="px-5 py-2 text-sm font-semibold rounded-lg bg-[#0369A1] text-white hover:bg-[#0284C7] transition-colors shadow-sm"
                                >
                                    {t.landing.heroCta}
                                </Link>
                            </>
                        ) : (
                            <>
                                <Link
                                    href="/login"
                                    className="text-sm font-medium text-[#64748B] hover:text-[#0369A1] transition-colors hidden sm:inline-block"
                                >
                                    {t.landing.heroLogin}
                                </Link>
                                <Link
                                    href="/dashboard"
                                    className="px-5 py-2 text-sm font-semibold rounded-lg bg-[#0369A1] text-white hover:bg-[#0284C7] transition-colors shadow-sm"
                                >
                                    {t.landing.heroCta}
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </header>

            {/* ── Hero ── */}
            <section className="relative pt-32 pb-20 sm:pt-40 sm:pb-28 px-6">
                {/* Decorative blobs */}
                <div
                    aria-hidden="true"
                    className="pointer-events-none absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-[radial-gradient(ellipse_at_center,rgba(3,105,161,0.08)_0%,transparent_70%)]"
                />
                <div
                    aria-hidden="true"
                    className="pointer-events-none absolute top-20 right-0 w-[400px] h-[400px] bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.06)_0%,transparent_70%)]"
                />

                <div className="relative max-w-3xl mx-auto text-center">
                    <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1] text-[#0F172A]">
                        {t.landing.heroTitle}
                    </h1>
                    <p className="mt-6 text-lg sm:text-xl text-[#475569] max-w-2xl mx-auto leading-relaxed">
                        {t.landing.heroSubtitle}
                    </p>
                    <div className="mt-10 flex items-center justify-center gap-4 flex-wrap">
                        <Link
                            href="/dashboard"
                            className="px-7 py-3.5 rounded-xl bg-[#0369A1] text-white font-semibold text-base hover:bg-[#0284C7] shadow-lg shadow-[#0369A1]/20 transition-all hover:shadow-xl hover:shadow-[#0369A1]/25 hover:-translate-y-0.5"
                        >
                            {t.landing.heroCta}
                        </Link>
                    </div>
                </div>
            </section>

            {/* ── Features ── */}
            <section className="py-20 sm:py-28 px-6 bg-white">
                <div className="max-w-5xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#0F172A]">
                            {t.landing.featuresTitle}
                        </h2>
                    </div>

                    <div className="grid md:grid-cols-3 gap-4 sm:gap-6 md:gap-8">
                        {/* Feature 1 */}
                        <div className="group relative p-5 sm:p-8 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#0369A1]/30 hover:shadow-lg hover:shadow-[#0369A1]/5 transition-all">
                            <div className="w-12 h-12 rounded-xl bg-[#0369A1]/10 flex items-center justify-center mb-5">
                                <svg className="w-6 h-6 text-[#0369A1]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5,14.25v-2.625a3.375,3.375,0,00,-3.375,-3.375h-1.5A1.125,1.125,0,0113.5,7.125v-1.5a3.375,3.375,0,00,-3.375,-3.375H8.25m0,12.75h7.5m-7.5,3H12M10.5,2.25H5.625c-.621,0,-1.125,.504,-1.125,1.125v17.25c0,.621,.504,1.125,1.125,1.125h12.75c.621,0,1.125,-.504,1.125,-1.125V11.25a9,9,0,00,-9,-9z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-[#0F172A] mb-2">{t.landing.feature1Title}</h3>
                            <p className="text-[#64748B] leading-relaxed text-sm">{t.landing.feature1Desc}</p>
                        </div>

                        {/* Feature 2 */}
                        <div className="group relative p-5 sm:p-8 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#6366F1]/30 hover:shadow-lg hover:shadow-[#6366F1]/5 transition-all">
                            <div className="w-12 h-12 rounded-xl bg-[#6366F1]/10 flex items-center justify-center mb-5">
                                <svg className="w-6 h-6 text-[#6366F1]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M3,13.125C3,12.504,3.504,12,4.125,12h2.25c.621,0,1.125,.504,1.125,1.125v6.75C7.5,20.496,6.996,21,6.375,21h-2.25A1.125,1.125,0,013,19.875v-6.75zM9.75,8.625c0,-.621,.504,-1.125,1.125,-1.125h2.25c.621,0,1.125,.504,1.125,1.125v11.25c0,.621,-.504,1.125,-1.125,1.125h-2.25a1.125,1.125,0,01,-1.125,-1.125V8.625zM16.5,4.125c0,-.621,.504,-1.125,1.125,-1.125h2.25C20.496,3,21,3.504,21,4.125v15.75c0,.621,-.504,1.125,-1.125,1.125h-2.25a1.125,1.125,0,01,-1.125,-1.125V4.125z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-[#0F172A] mb-2">{t.landing.feature2Title}</h3>
                            <p className="text-[#64748B] leading-relaxed text-sm">{t.landing.feature2Desc}</p>
                        </div>

                        {/* Feature 3 */}
                        <div className="group relative p-5 sm:p-8 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#059669]/30 hover:shadow-lg hover:shadow-[#059669]/5 transition-all">
                            <div className="w-12 h-12 rounded-xl bg-[#059669]/10 flex items-center justify-center mb-5">
                                <svg className="w-6 h-6 text-[#059669]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.625,12a.375,.375,0,11,-.75,0,.375,.375,0,01.75,0zm0,0H8.25m4.125,0a.375,.375,0,11,-.75,0,.375,.375,0,01.75,0zm0,0H12m4.125,0a.375,.375,0,11,-.75,0,.375,.375,0,01.75,0zm0,0h-.375M21,12c0,4.556,-4.03,8.25,-9,8.25a9.764,9.764,0,01,-2.555,-.337A5.972,5.972,0,015.41,20.97a5.969,5.969,0,01,-.474,-.065,4.48,4.48,0,00.978,-2.025c.09,-.457,-.133,-.901,-.467,-1.226C3.93,16.178,3,14.189,3,12c0,-4.556,4.03,-8.25,9,-8.25s9,3.694,9,8.25z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-[#0F172A] mb-2">{t.landing.feature3Title}</h3>
                            <p className="text-[#64748B] leading-relaxed text-sm">{t.landing.feature3Desc}</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* ── Research / Trust ── */}
            <section className="py-20 sm:py-28 px-6">
                <div className="max-w-3xl mx-auto text-center">
                            <span className="inline-block px-3 py-1 text-xs font-semibold rounded-full bg-[#0F172A] text-white mb-5 tracking-wide uppercase">
                                {t.landing.researchBadge}
                            </span>
                            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#0F172A] mb-5">
                                {t.landing.researchTitle}
                            </h2>
                            <p className="text-[#475569] text-lg leading-relaxed">
                                {t.landing.researchDesc}
                            </p>
                            <div className="mt-8 flex items-center justify-center gap-3 sm:gap-6">
                                <div className="flex items-center gap-2 text-sm text-[#64748B]">
                                    <svg className="w-5 h-5 text-[#059669]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M9,12.75L11.25,15,15,9.75m-3,-7.036A11.959,11.959,0,013.598,6,11.99,11.99,0,003,9.749c0,5.592,3.824,10.29,9,11.623,5.176,-1.332,9,-6.03,9,-11.622,0,-1.31,-.21,-2.571,-.598,-3.751h-.152c-3.196,0,-6.1,-1.248,-8.25,-3.285z" />
                                    </svg>
                                    <span>{t.landing.syntheticData}</span>
                                </div>
                                <div className="flex items-center gap-2 text-sm text-[#64748B]">
                                    <svg className="w-5 h-5 text-[#059669]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5,10.5V6.75a4.5,4.5,0,10,-9,0v3.75m-.75,11.25h10.5a2.25,2.25,0,002.25,-2.25v-6.75a2.25,2.25,0,00,-2.25,-2.25H6.75a2.25,2.25,0,00,-2.25,2.25v6.75a2.25,2.25,0,002.25,2.25z" />
                                    </svg>
                                    <span>{t.landing.humanDecision}</span>
                                </div>
                            </div>
                </div>
            </section>

            {/* ── CTA ── */}
            <section className="py-20 sm:py-28 px-6 bg-[#0F172A]">
                <div className="max-w-3xl mx-auto text-center">
                    <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white mb-4">
                        {t.landing.ctaTitle}
                    </h2>
                    <p className="text-[#94A3B8] text-lg mb-10">
                        {t.landing.ctaDesc}
                    </p>
                    <Link
                        href="/dashboard"
                        className="inline-flex items-center gap-2 px-6 py-3.5 sm:px-8 sm:py-4 rounded-xl bg-white text-[#0F172A] font-bold text-lg hover:bg-[#F1F5F9] transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                    >
                        {t.landing.ctaButton}
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5,4.5L21,12m0,0l-7.5,7.5M21,12H3" />
                        </svg>
                    </Link>
                </div>
            </section>

            {/* ── Footer ── */}
            <footer className="py-8 px-6 bg-[#0F172A] border-t border-[#1E293B]">
                <p className="text-center text-sm text-[#64748B]">
                    {t.landing.footer}
                </p>
            </footer>
        </div>
    );
}
