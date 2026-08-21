"use client";

import {
  ArrowRightIcon,
  BriefcaseIcon,
  CheckIcon,
  DocumentIcon,
  InfoIcon,
} from "@/components/icons";
import { useLanguage } from "@/i18n";
import axios from "axios";
import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [stats, setStats] = useState({ jobs: 0, cvs: 0 });
  const [loading, setLoading] = useState(true);
  const { t } = useLanguage();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const [jobsRes, cvsRes] = await Promise.all([
        axios.get(`${API_URL}/api/jobs`),
        axios.get(`${API_URL}/api/cvs`)
      ]);
      setStats({
        jobs: jobsRes.data.jobs.length,
        cvs: cvsRes.data.cvs.length
      });
    } catch (error) {
      console.error("Error loading stats:", error);
    } finally {
      setLoading(false);
    }
  };

  const getNextStep = () => {
    if (stats.jobs === 0) return {
      step: 1,
      text: t.dashboard.enterJobDesc,
      href: "/jobs",
      desc: t.dashboard.enterJobDescHint
    };
    if (stats.cvs === 0) return {
      step: 2,
      text: t.dashboard.uploadCv,
      href: "/cvs",
      desc: t.dashboard.uploadCvHint
    };
    return {
      step: 3,
      text: t.dashboard.viewScreening,
      href: "/screening",
      desc: t.dashboard.viewScreeningHint
    };
  };

  const nextStep = getNextStep();

  // Get current step number (1, 2, or 3)
  const currentStepNum = stats.jobs === 0 ? 1 : stats.cvs === 0 ? 2 : 3;

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header with inline status */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-6 sm:mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#0F172A] mb-2">
            {t.dashboard.welcome}
          </h1>
          <p className="text-sm sm:text-base text-[#64748B]">
            {t.dashboard.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[#F0FDF4] rounded-full">
            <div className="w-2 h-2 bg-[#059669] rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-[#059669]">{t.dashboard.aiEngine}</span>
          </div>
        </div>
      </div>

      {/* Horizontal Stepper - Clean Timeline Design */}
      <div className="card mb-6 sm:mb-8">
        <div className="flex items-center justify-between mb-4 sm:mb-6">
          <h2 className="text-base sm:text-lg font-semibold text-[#0F172A]">{t.dashboard.workflow}</h2>
          <div className="flex items-center gap-2 text-sm text-[#64748B]">
            <span className="font-medium text-[#0369A1]">{currentStepNum}</span>
            <span>/</span>
            <span>3</span>
          </div>
        </div>

        {/* Steps Container */}
        <div className="relative">
          {/* Progress Line */}
          <div className="absolute top-6 left-0 right-0 h-0.5 bg-[#E2E8F0]"></div>
          <div
            className="absolute top-6 left-0 h-0.5 bg-[#059669] transition-all duration-500"
            style={{ width: `${((currentStepNum - 1) / 2) * 100}%` }}
          ></div>

          {/* Steps */}
          <div className="relative flex justify-between">
            {/* Step 1 */}
            <Link href="/jobs" className="flex flex-col items-center text-center w-1/3 group cursor-pointer">
              <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center font-bold text-base sm:text-lg mb-2 sm:mb-3 transition-all
                ${stats.jobs > 0
                  ? 'bg-[#059669] text-white'
                  : currentStepNum === 1
                    ? 'bg-[#0369A1] text-white ring-4 ring-[#0369A1]/20'
                    : 'bg-[#E2E8F0] text-[#94A3B8]'
                }`}>
                {stats.jobs > 0 ? <CheckIcon className="w-5 h-5" /> : '1'}
              </div>
              <span className={`font-semibold mb-1 text-sm sm:text-base group-hover:text-[#0369A1] transition-colors ${currentStepNum === 1 ? 'text-[#0369A1]' : 'text-[#0F172A]'}`}>
                {t.nav.jobs}
              </span>
              <span className="text-xs text-[#64748B] max-w-[140px] hidden sm:block">{t.dashboard.step1Short}</span>
            </Link>

            {/* Step 2 */}
            <Link
              href={stats.jobs > 0 ? "/cvs" : "#"}
              className={`flex flex-col items-center text-center w-1/3 group ${stats.jobs > 0 ? 'cursor-pointer' : 'cursor-not-allowed'}`}
            >
              <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center font-bold text-base sm:text-lg mb-2 sm:mb-3 transition-all
                ${stats.cvs > 0
                  ? 'bg-[#059669] text-white'
                  : currentStepNum === 2
                    ? 'bg-[#0369A1] text-white ring-4 ring-[#0369A1]/20'
                    : 'bg-[#E2E8F0] text-[#94A3B8]'
                }`}>
                {stats.cvs > 0 ? <CheckIcon className="w-5 h-5" /> : '2'}
              </div>
              <span className={`font-semibold mb-1 text-sm sm:text-base transition-colors ${currentStepNum === 2 ? 'text-[#0369A1]' : stats.jobs > 0 ? 'group-hover:text-[#0369A1] text-[#0F172A]' : 'text-[#94A3B8]'}`}>
                {t.nav.cvs}
              </span>
              <span className="text-xs text-[#64748B] max-w-[140px] hidden sm:block">{t.dashboard.step2Short}</span>
            </Link>

            {/* Step 3 */}
            <Link
              href={stats.cvs > 0 ? "/screening" : "#"}
              className={`flex flex-col items-center text-center w-1/3 group ${stats.cvs > 0 ? 'cursor-pointer' : 'cursor-not-allowed'}`}
            >
              <div className={`w-10 h-10 sm:w-12 sm:h-12 rounded-full flex items-center justify-center font-bold text-base sm:text-lg mb-2 sm:mb-3 transition-all
                ${currentStepNum === 3
                  ? 'bg-[#0369A1] text-white ring-4 ring-[#0369A1]/20'
                  : 'bg-[#E2E8F0] text-[#94A3B8]'
                }`}>
                3
              </div>
              <span className={`font-semibold mb-1 text-sm sm:text-base transition-colors ${currentStepNum === 3 ? 'text-[#0369A1]' : stats.cvs > 0 ? 'group-hover:text-[#0369A1] text-[#0F172A]' : 'text-[#94A3B8]'}`}>
                {t.nav.screening}
              </span>
              <span className="text-xs text-[#64748B] max-w-[140px] hidden sm:block">{t.dashboard.step3Short}</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Bento Grid Layout */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8 animate-pulse">
          {/* Skeleton: Next Action large card */}
          <div className="col-span-2 row-span-2 bg-[#E2E8F0] rounded-2xl h-48" />
          {/* Skeleton: Stats cards */}
          <div className="bg-[#E2E8F0] rounded-2xl h-24" />
          <div className="bg-[#E2E8F0] rounded-2xl h-24" />
          {/* Skeleton: Quick action cards */}
          <div className="col-span-2 sm:col-span-1 bg-[#E2E8F0] rounded-2xl h-24" />
          <div className="col-span-2 sm:col-span-1 bg-[#E2E8F0] rounded-2xl h-24" />
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-8 [--stagger-delay:60ms]">
          {/* Next Action - Large Card */}
          <div
            className="col-span-2 row-span-2 bg-linear-to-br from-[#0369A1] to-[#0284C7] text-white p-5 sm:p-6 rounded-2xl flex flex-col animate-fade-in-up [animation-delay:calc(0*var(--stagger-delay))]"
            data-testid="next-action-card"
          >
            <p className="text-[#7DD3FC] text-sm font-medium mb-2">{t.dashboard.nextStep.toUpperCase()}</p>
            <h2 className="text-xl sm:text-2xl font-bold mb-2" data-testid="next-action-text">{nextStep.text}</h2>
            <p className="text-[#BAE6FD] text-sm sm:text-base mb-auto">{nextStep.desc}</p>
            <Link
              href={nextStep.href}
              className="mt-4 bg-white text-[#0369A1] px-5 py-2.5 rounded-lg font-semibold hover:bg-[#F0F9FF] transition-all inline-flex items-center gap-2 self-start cursor-pointer"
            >
              {t.common.start}
              <ArrowRightIcon />
            </Link>
          </div>

          {/* Stats Cards - Compact */}
          <div className="card p-4! flex flex-col items-center justify-center text-center animate-fade-in-up [animation-delay:calc(1*var(--stagger-delay))]" data-testid="jobs-stat-card">
            <div className="w-10 h-10 bg-[#F0F9FF] rounded-xl flex items-center justify-center text-[#0369A1] mb-2">
              <BriefcaseIcon />
            </div>
            <div className="text-2xl font-bold text-[#0F172A]" data-testid="jobs-count">{stats.jobs}</div>
            <span className="text-xs text-[#64748B]">{t.dashboard.positions}</span>
          </div>

          <div className="card p-4! flex flex-col items-center justify-center text-center animate-fade-in-up [animation-delay:calc(2*var(--stagger-delay))]" data-testid="cvs-stat-card">
            <div className="w-10 h-10 bg-[#F0F9FF] rounded-xl flex items-center justify-center text-[#0369A1] mb-2">
              <DocumentIcon />
            </div>
            <div className="text-2xl font-bold text-[#0F172A]" data-testid="cvs-count">{stats.cvs}</div>
            <span className="text-xs text-[#64748B]">{t.dashboard.processedCvs}</span>
          </div>

          {/* Quick Action - Enter JD: full-width row on mobile, card on desktop */}
          <Link href="/jobs" className="col-span-2 sm:col-span-1 card p-3 sm:p-4! hover:border-[#0369A1] hover:bg-[#F0F9FF] transition-all [transition-timing-function:cubic-bezier(0.16,1,0.3,1)] cursor-pointer group flex sm:flex-col items-center sm:items-start gap-3 sm:gap-0 animate-fade-in-up [animation-delay:calc(3*var(--stagger-delay))]">
            <div className="w-9 h-9 sm:w-auto sm:h-auto bg-[#F0F9FF] sm:bg-transparent rounded-lg flex items-center justify-center text-[#0369A1] shrink-0">
              <DocumentIcon />
            </div>
            <p className="text-sm font-medium text-[#0F172A] sm:mt-2 group-hover:text-[#0369A1]">{t.dashboard.newJob}</p>
          </Link>

        </div>
      )}

      {stats.jobs === 0 && (
        <div className="bg-[#FFFBEB] border border-[#FCD34D] text-[#92400E] p-4 rounded-xl flex items-center gap-3">
          <InfoIcon className="w-5 h-5 shrink-0" />
          <p className="text-sm font-medium">
            {t.dashboard.startHint}
          </p>
        </div>
      )}

    </div>
  );
}
