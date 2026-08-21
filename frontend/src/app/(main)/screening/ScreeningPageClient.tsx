"use client";

import CVDetailModal from "@/components/CVDetailModal";
import GuestBanner from "@/components/GuestBanner";
import ScreeningProgress from "@/components/ScreeningProgress";
import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  SearchIcon,
  StarIcon,
} from "@/components/icons";
import { useAuth } from "@/contexts/AuthContext";
import { getCsrfHeaders } from "@/lib/csrf";
import { localizeInterviewFocusArea, localizeInterviewQuestionType } from "@/lib/interview-question-labels";
import { useJob } from "@/contexts/JobContext";
import { useGuestLimits } from "@/hooks/useGuestLimits";
import { useLanguage } from "@/i18n";
import axios from "axios";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Job {
  job_id: string;
  title: string;
  required_skills?: string[];
}

interface CandidateMatch {
  cv_id: string;
  name: string;
  score: number;
  matching_skills: string[];
  missing_skills: string[];
  analysis: string;
  experience_years?: number;
  email?: string;
  phone?: string;
  owner_user_id?: string;
}

interface ScreeningResult {
  job_id: string;
  job_title: string;
  candidates: CandidateMatch[];
}

type InterviewQuestion = {
  question: string;
  type?: string;
  focus_area?: string;
  source: "ai" | "custom";
  liked: boolean;
};

export default function ScreeningPageClient() {
  const [cvCount, setCvCount] = useState<number>(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [screeningStartTime, setScreeningStartTime] = useState(0);
  const [results, setResults] = useState<ScreeningResult | null>(null);
  const [error, setError] = useState("");
  const [expandedCandidate, setExpandedCandidate] = useState<string | null>(null);
  const { t } = useLanguage();
  const { currentJob, setCurrentJob, jobs, jobsLoading } = useJob();
  const { user } = useAuth();
  const { isGuest, canPerformScreening, getScreeningsRemaining, refreshUsage, limits } = useGuestLimits();
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Interview question builder state
  const [questionsMap, setQuestionsMap] = useState<Record<string, InterviewQuestion[]>>({});
  const [loadingQuestions, setLoadingQuestions] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState<Record<string, string>>({});
  const [savingSet, setSavingSet] = useState<string | null>(null);
  const [savedSets, setSavedSets] = useState<Set<string>>(new Set());
  // Saved question sets viewer
  const [showSavedSets, setShowSavedSets] = useState(false);
  const [savedSetsList, setSavedSetsList] = useState<Array<{id: string; cv_id: string; candidate_name: string; question_count: number; created_at: string; questions?: Array<{question: string; type?: string; source: string; liked: boolean}>}>>([]);
  const [loadingSavedSets, setLoadingSavedSets] = useState(false);
  const [expandedSetId, setExpandedSetId] = useState<string | null>(null);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [cvDetailModal, setCvDetailModal] = useState<{ cvId: string; name: string } | null>(null);

  const [hasHydrated, setHasHydrated] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => setHasHydrated(true), []);

  // Auth can hydrate JobContext after this page's first client render.
  useEffect(() => {
    if (!currentJob) return;
    setSearchQuery(currentJob.title);
  }, [currentJob]);

  const loadCvCount = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/cvs`, {
        withCredentials: true,
      });
      setCvCount(response.data.cvs?.length || 0);
    } catch (err: unknown) {
      console.error("Failed to load CVs:", err);
    }
  }, []);

  useEffect(() => {
    loadCvCount();
  }, [loadCvCount]);

  // Close dropdown when clicking outside - using useCallback for stable reference
  const handleClickOutside = useCallback((event: MouseEvent) => {
    if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
      setShowDropdown(false);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [handleClickOutside]);

  // Filter jobs based on search query - useMemo for derived state
  const filteredJobs = useMemo(() =>
    jobs.filter(job => job.title.toLowerCase().includes(searchQuery.toLowerCase())),
    [jobs, searchQuery]
  );

  // Recent jobs for quick-select (last 5 added, excluding currently selected)
  const recentJobs = useMemo(() =>
    jobs.slice(-5).reverse().filter(j => j.job_id !== currentJob?.job_id),
    [jobs, currentJob?.job_id]
  );

  const selectJob = useCallback((job: Job) => {
    setSearchQuery(job.title);
    setShowDropdown(false);
    // Set global job context for cross-page navigation
    setCurrentJob({
      job_id: job.job_id,
      title: job.title,
      required_skills: job.required_skills
    });
  }, [setCurrentJob]);

  const handleScreening = useCallback(async () => {
    if (!currentJob) {
      setError(t.screening.pleaseSelect);
      return;
    }

    // Check guest screening quota
    if (isGuest && !canPerformScreening()) {
      setError(t.guest.limitReached.replace('{feature}', 'Screening').replace('{limit}', String(limits.MAX_SCREENINGS)) +
        ` ${t.guest.signInForMore}`);
      return;
    }

    setLoading(true);
    setScreeningStartTime(Date.now());
    setError("");
    setResults(null);

    try {
      const response = await axios.post(`${API_URL}/api/screening`, {
        job_id: currentJob.job_id,
        top_k: 10,
      }, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setResults(response.data);
      // Refresh guest usage from backend after success
      if (isGuest) {
        refreshUsage();
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { status?: number; data?: { detail?: string; message?: string } } };
      if (axiosError.response?.status === 429) {
        // Guest quota exceeded - backend enforced
        setError(axiosError.response.data?.message || t.guest.limitReached.replace('{feature}', 'Screening').replace('{limit}', String(limits.MAX_SCREENINGS)));
        if (isGuest) refreshUsage(); // Sync with backend
      } else {
        setError(axiosError.response?.data?.detail || t.common.error);
      }
    } finally {
      setLoading(false);
    }
  }, [currentJob, t.screening.pleaseSelect, t.common.error, isGuest, canPerformScreening, refreshUsage, limits.MAX_SCREENINGS, t.guest.limitReached, t.guest.signInForMore]);

  const getScoreColor = useCallback((score: number) => {
    if (score >= 80) return "text-[#059669] bg-[#ECFDF5]";
    if (score >= 60) return "text-[#0369A1] bg-[#F0F9FF]";
    if (score >= 40) return "text-[#D97706] bg-[#FFFBEB]";
    return "text-[#DC2626] bg-[#FEF2F2]";
  }, []);

  const getScoreLabel = useCallback((score: number) => {
    if (score >= 80) return t.screening.excellent;
    if (score >= 60) return t.screening.good;
    if (score >= 40) return t.screening.moderate;
    return t.screening.needsImprovement;
  }, [t.screening.excellent, t.screening.good, t.screening.moderate, t.screening.needsImprovement]);

  const renderStars = useCallback((score: number) => {
    const stars = Math.round(score / 20);
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <StarIcon key={i} filled={i <= stars} />
        ))}
      </div>
    );
  }, []);

  const generateInterviewQuestions = async (cvId: string) => {
    if (!results) return;
    setLoadingQuestions(cvId);
    try {
      const res = await axios.post(`${API_URL}/api/interview-questions/generate/${results.job_id}/${cvId}`, {}, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      if (res.data.questions) {
        setQuestionsMap(prev => ({
          ...prev,
          [cvId]: res.data.questions.map((q: Omit<InterviewQuestion, "source" | "liked">) => ({
            ...q,
            source: "ai" as const,
            liked: true,
          }))
        }));
      }
    } catch (err) {
      console.error("Failed to generate questions:", err);
    } finally {
      setLoadingQuestions(null);
    }
  };

  const toggleQuestionLike = (cvId: string, index: number) => {
    setQuestionsMap(prev => {
      const questions = [...(prev[cvId] || [])];
      questions[index] = { ...questions[index], liked: !questions[index].liked };
      return { ...prev, [cvId]: questions };
    });
  };

  const addCustomQuestion = (cvId: string) => {
    const text = customInput[cvId]?.trim();
    if (!text) return;
    setQuestionsMap(prev => ({
      ...prev,
      [cvId]: [...(prev[cvId] || []), { question: text, source: "custom" as const, liked: true }]
    }));
    setCustomInput(prev => ({ ...prev, [cvId]: "" }));
  };

  const saveQuestionSet = async (cvId: string, candidateName: string) => {
    if (!results) return;
    const questions = questionsMap[cvId];
    if (!questions?.length) return;
    setSavingSet(cvId);
    try {
      await axios.post(`${API_URL}/api/interview-questions/save`, {
        job_id: results.job_id,
        cv_id: cvId,
        candidate_name: candidateName,
        questions: questions,
      }, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setSavedSets(prev => new Set(prev).add(cvId));
      if (showSavedSets && results) loadSavedSets(results.job_id);
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSavingSet(null);
    }
  };

  const loadSavedSets = async (jobId: string) => {
    setLoadingSavedSets(true);
    try {
      const res = await axios.get(`${API_URL}/api/interview-questions/job/${jobId}`);
      setSavedSetsList(res.data.sets || []);
    } catch (err) {
      console.error("Failed to load saved sets:", err);
    } finally {
      setLoadingSavedSets(false);
    }
  };

  const toggleSavedSets = () => {
    if (!showSavedSets && results) {
      loadSavedSets(results.job_id);
    }
    setShowSavedSets(!showSavedSets);
  };

  const expandSet = async (setId: string) => {
    if (expandedSetId === setId) {
      setExpandedSetId(null);
      return;
    }
    try {
      const res = await axios.get(`${API_URL}/api/interview-questions/set/${setId}`);
      setSavedSetsList(prev => prev.map(s => s.id === setId ? { ...s, questions: res.data.questions } : s));
      setExpandedSetId(setId);
    } catch (err) {
      console.error("Failed to load set:", err);
    }
  };

  const deleteSet = async (setId: string) => {
    if (!confirm(t.screening.confirmDelete)) return;
    try {
      await axios.delete(`${API_URL}/api/interview-questions/set/${setId}`, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setSavedSetsList(prev => prev.filter(s => s.id !== setId));
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  const copyAllQuestions = (setItem: typeof savedSetsList[0]) => {
    if (!setItem.questions) return;
    const text = setItem.questions
      .filter(q => q.liked)
      .map((q, i) => `${i + 1}. ${q.question}`)
      .join("\n");
    navigator.clipboard.writeText(text);
    setCopiedId(setItem.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Guest Banner - show value proposition */}
      {isGuest && (
        <GuestBanner
          variant={!canPerformScreening() ? 'warning' : 'compact'}
          feature="Screening"
          remaining={getScreeningsRemaining()}
          total={limits.MAX_SCREENINGS}
          showUsage
        />
      )}

      {/* Progress Indicator */}
      <div className="mb-6 flex items-center gap-1.5 sm:gap-3">
        <span className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center font-bold text-xs sm:text-sm ${jobs.length > 0 ? 'bg-[#059669] text-white' : 'bg-[#E2E8F0] text-[#94A3B8]'}`}>
          {jobs.length > 0 ? <CheckIcon /> : '1'}
        </span>
        <span className="hidden sm:inline text-[#64748B]">{t.nav.jobs}</span>
        <div className={`flex-1 h-1 rounded ${jobs.length > 0 ? 'bg-[#059669]' : 'bg-[#E2E8F0]'}`}></div>
        <span className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center font-bold text-xs sm:text-sm ${cvCount > 0 ? 'bg-[#059669] text-white' : 'bg-[#E2E8F0] text-[#94A3B8]'}`}>
          {cvCount > 0 ? <CheckIcon /> : '2'}
        </span>
        <span className="hidden sm:inline text-[#64748B]">{t.nav.cvs}</span>
        <div className={`flex-1 h-1 rounded ${cvCount > 0 ? 'bg-[#059669]' : 'bg-[#E2E8F0]'}`}></div>
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#0369A1] text-white rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">3</span>
        <span className="hidden sm:inline text-[#0F172A] font-medium">{t.nav.screening}</span>
      </div>

      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-[#0F172A] mb-2">{t.screening.title}</h1>
        <p className="text-sm sm:text-base text-[#64748B]">{t.screening.subtitle}</p>
      </div>

      {/* Warning: No CVs uploaded yet */}
      {jobs.length > 0 && cvCount === 0 && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,9v2m0,4h.01m-6.938,4h13.856c1.54,0,2.502,-1.667,1.732,-3L13.732,4c-.77,-1.333,-2.694,-1.333,-3.464,0L3.34,16c-.77,1.333,.192,3,1.732,3z" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-800 mb-1">{t.screening.noCVsTitle}</h3>
              <p className="text-amber-700 text-sm mb-3">{t.screening.noCVs}</p>
              <Link
                href="/cvs"
                className="inline-flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
              >
                {t.screening.uploadCVsFirst}
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Job Selection - Autocomplete */}
      <div className="card mb-6">
        <label className="block text-sm font-semibold text-[#0F172A] mb-2">
          {t.screening.selectJob}
        </label>

        {/* Quick-select suggestions from recently added jobs */}
        {!jobsLoading && recentJobs.length > 0 && !currentJob && (
          <div className="mb-3">
            <p className="text-xs text-[#64748B] mb-2 flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,8v4l3,3m6,-3a9,9,0,11,-18,0,9,9,0,0118,0z" />
              </svg>
              {t.screening.recentJobsHint}
            </p>
            <div className="flex flex-wrap gap-2">
              {recentJobs.map((job) => (
                <button
                  key={job.job_id}
                  type="button"
                  onClick={() => selectJob(job)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#F0F9FF] hover:bg-[#E0F2FE] border border-[#BAE6FD] text-[#0369A1] rounded-full text-sm font-medium transition-colors cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21,13.255A23.931,23.931,0,0112,15c-3.183,0,-6.22,-.62,-9,-1.745M16,6V4a2,2,0,00,-2,-2h-4a2,2,0,00,-2,2v2m4,6h.01M5,20h14a2,2,0,002,-2V8a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
                  </svg>
                  <span className="truncate max-w-[140px] sm:max-w-[200px]">{job.title}</span>
                </button>
              ))}
            </div>
          </div>
        )}
        {jobsLoading ? (
          <div className="animate-pulse h-12 bg-gray-200 rounded-lg"></div>
        ) : jobs.length === 0 ? (
          <div className="bg-[#FFFBEB] border border-[#FCD34D] text-[#D97706] p-4 rounded-lg">
            {t.screening.noJobs}
          </div>
        ) : (
          <div className="relative" ref={dropdownRef}>
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setShowDropdown(true);
                  // Clear selection if user edits or empties the field
                  if (!e.target.value.trim() || (currentJob && e.target.value !== currentJob.title)) {
                    setCurrentJob(null);
                  }
                }}
                onFocus={() => setShowDropdown(true)}
                placeholder={t.screening.selectJobPlaceholder}
                className="input pr-10"
                data-testid="jobsearchinput"
              />
              <button
                type="button"
                onClick={() => setShowDropdown(!showDropdown)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#64748B] hover:text-[#0F172A]"
              >
                {showDropdown ? <ChevronUpIcon /> : <ChevronDownIcon />}
              </button>
            </div>

            {/* Dropdown */}
            {showDropdown && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-[#E2E8F0] rounded-lg shadow-lg max-h-60 overflow-auto">
                {filteredJobs.length === 0 ? (
                  <div className="p-3 text-[#64748B] text-sm">
                    {t.screening.noJobsFound || "Không tìm thấy vị trí phù hợp"}
                  </div>
                ) : (
                  filteredJobs.map((job) => (
                    <div
                      key={job.job_id}
                      onClick={() => selectJob(job)}
                      className={`p-3 cursor-pointer hover:bg-[#F0F9FF] transition-colors border-b border-[#E2E8F0] last:border-b-0 ${currentJob?.job_id === job.job_id ? "bg-[#F0F9FF]" : ""
                        }`}
                    >
                      <div className="flex items-center gap-2">
                        {currentJob?.job_id === job.job_id && (
                          <CheckIcon />
                        )}
                        <div className="flex-1">
                          <p className="font-medium text-[#0F172A]">{job.title}</p>
                          {(job.required_skills?.length ?? 0) > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {job.required_skills?.slice(0, 3).map((skill, idx) => (
                                <span key={idx} className="text-xs px-2 py-0.5 bg-[#E0F2FE] text-[#0369A1] rounded">
                                  {skill}
                                </span>
                              ))}
                              {(job.required_skills?.length ?? 0) > 3 && (
                                <span className="text-xs text-[#64748B]">+{(job.required_skills?.length ?? 0) - 3}</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Screen Button */}
      {hasHydrated ? (
        <button
          onClick={handleScreening}
          disabled={loading || !currentJob || searchQuery !== currentJob.title}
          className="btn-primary w-full py-3 sm:py-4 text-base sm:text-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="startscreeningbutton"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
              {t.screening.analyzing}
            </>
          ) : (
            <>
              <SearchIcon />
              {t.screening.startScreening}
            </>
          )}
        </button>
      ) : (
        <div className="h-[52px] w-full" aria-hidden="true" />
      )}

      {/* Tips & progress while screening */}
      {loading && <ScreeningProgress startTime={screeningStartTime} />}

      {/* Results */}
      {results && results.candidates && (
        <div className="mt-8" data-testid="screeningresults">
          {/* Summary Banner */}
          <div className="bg-[#059669] text-white p-4 sm:p-6 rounded-xl mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-xl sm:text-2xl font-bold mb-1">{t.screening.resultsFor} {results.job_title}</h2>
                <p className="text-[#A7F3D0]">
                  {t.screening.found} {results.candidates.length} {t.screening.candidates}
                </p>
              </div>
              <div className="flex items-center gap-3 sm:gap-4 flex-wrap">
                <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                  {[
                    { min: 80, color: 'bg-emerald-400/30 text-white', label: t.screening.excellent },
                    { min: 60, max: 79, color: 'bg-sky-400/30 text-white', label: t.screening.good },
                    { min: 40, max: 59, color: 'bg-amber-400/30 text-white', label: t.screening.moderate },
                    { min: 0, max: 39, color: 'bg-red-400/30 text-white', label: t.screening.needsImprovement },
                  ]
                    .map(tier => ({
                      ...tier,
                      count: results.candidates.filter(c =>
                        tier.max !== undefined
                          ? c.score >= tier.min && c.score <= tier.max
                          : c.score >= tier.min
                      ).length,
                    }))
                    .filter(tier => tier.count > 0)
                    .map(tier => (
                      <span
                        key={tier.min}
                        className={`inline-flex items-center gap-1 sm:gap-1.5 px-2 sm:px-3 py-1 sm:py-1.5 rounded-full text-[11px] sm:text-xs font-semibold ${tier.color}`}
                      >
                        <span className="text-sm sm:text-base font-bold">{tier.count}</span>
                        <span className="hidden sm:inline">{tier.label}</span>
                      </span>
                    ))}
                </div>
              </div>
            </div>
          </div>

          {/* Candidates List */}
          <div className="space-y-4">
            {results.candidates.map((candidate, idx) => (
              <div
                key={candidate.cv_id}
                className="card hover:shadow-lg transition-all cursor-pointer"
                onClick={() => setExpandedCandidate(
                  expandedCandidate === candidate.cv_id ? null : candidate.cv_id
                )}
              >
                {/* Main Info */}
                <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
                  {/* Rank + Avatar row on mobile */}
                  <div className="flex items-center gap-3 sm:gap-4">
                    {/* Rank */}
                    <div className={`w-8 h-8 sm:w-10 sm:h-10 rounded-full flex items-center justify-center font-bold text-base sm:text-lg shrink-0 ${idx === 0 ? "bg-[#F59E0B] text-white" :
                      idx === 1 ? "bg-[#94A3B8] text-white" :
                        idx === 2 ? "bg-[#CD7F32] text-white" :
                          "bg-[#F1F5F9] text-[#64748B]"
                      }`}>
                      {idx + 1}
                    </div>

                    {/* Avatar & Name */}
                    <div className="w-10 h-10 sm:w-12 sm:h-12 bg-linear-to-br from-[#0369A1] to-[#0284C7] text-white rounded-xl flex items-center justify-center font-bold text-base sm:text-lg shrink-0">
                      {candidate.name?.charAt(0) || "?"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3
                          className="font-bold text-[#0F172A] text-base sm:text-lg hover:text-[#0369A1] cursor-pointer transition-colors"
                          onClick={(e) => { e.stopPropagation(); setCvDetailModal({ cvId: candidate.cv_id, name: candidate.name }); }}
                          title={t.cvDetail?.clickToView || "Bấm để xem chi tiết"}
                        >{candidate.name}</h3>
                        {candidate.owner_user_id && user?.id && candidate.owner_user_id === user.id ? (
                          <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">{t.cvs.mine || "Của tôi"}</span>
                        ) : candidate.owner_user_id && candidate.owner_user_id !== "system" ? (
                          <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">{t.cvs.shared || "Được chia sẻ"}</span>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-3 text-sm text-[#64748B]">
                        <span>{candidate.experience_years || 0} {t.cvs.yearsExp}</span>
                        {candidate.email && (
                          <>
                            <span className="hidden sm:inline">•</span>
                            <span className="hidden sm:inline truncate">{candidate.email}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Score */}
                  <div className="flex sm:flex-col items-center sm:items-end gap-1.5 sm:gap-0 ml-11 sm:ml-0 shrink-0">
                    <div className={`inline-flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-4 py-1 sm:py-2 rounded-full font-bold ${getScoreColor(candidate.score)}`}>
                      <span className="text-lg sm:text-2xl">{candidate.score}</span>
                      <span className="text-[10px] sm:text-sm">/100</span>
                    </div>
                    <div className="flex items-center gap-1.5 sm:gap-2">
                      <span className="hidden sm:flex items-center gap-0.5">{renderStars(candidate.score)}</span>
                      <span className="text-xs text-[#64748B]">{getScoreLabel(candidate.score)}</span>
                    </div>
                  </div>

                  {/* Expand Icon */}
                  <div className="text-[#94A3B8]">
                    {expandedCandidate === candidate.cv_id ? <ChevronUpIcon /> : <ChevronDownIcon />}
                  </div>
                </div>

                {/* Expanded Details */}
                {expandedCandidate === candidate.cv_id && (
                  <div className="mt-6 pt-6 border-t border-[#E2E8F0]">
                    {/* Skills */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                      <div>
                        <h4 className="font-semibold text-[#059669] mb-3 flex items-center gap-2">
                          <CheckIcon />
                          {t.screening.matchingSkills} ({candidate.matching_skills?.length || 0})
                        </h4>
                        <div className="space-y-2">
                          {candidate.matching_skills?.map((skill, i) => {
                            const skillKey = `${candidate.cv_id}-match-${i}`;
                            const isExpanded = expandedSkill === skillKey;
                            return (
                              <div
                                key={i}
                                onClick={(e) => { e.stopPropagation(); setExpandedSkill(isExpanded ? null : skillKey); }}
                                className={`cursor-pointer rounded-lg border transition-all duration-200 ${isExpanded ? "border-[#059669]/30 bg-[#F0FDF4] p-3" : "border-transparent"}`}
                              >
                                <div className="flex items-start gap-2">
                                  <svg className={`w-4 h-4 shrink-0 mt-0.5 text-[#059669] transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25,4.5l7.5,7.5,-7.5,7.5" />
                                  </svg>
                                  <span className={`text-sm leading-relaxed ${isExpanded ? "text-[#065F46] font-medium" : "text-[#059669]"}`}>
                                    {skill}
                                  </span>
                                </div>
                                {isExpanded && (
                                  <div className="mt-2 ml-6 text-xs text-[#475569] bg-white rounded-md p-2.5 border border-[#E2E8F0]">
                                    <div className="flex items-center gap-1.5 text-[#059669] font-medium mb-1">
                                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813,15.904L9,18.75l-.813,-2.846a4.5,4.5,0,00,-3.09,-3.09L2.25,12l2.846,-.813a4.5,4.5,0,003.09,-3.09L9,5.25l.813,2.846a4.5,4.5,0,003.09,3.09L15.75,12l-2.846,.813a4.5,4.5,0,00,-3.09,3.09z" /></svg>
                                      AI Reasoning
                                    </div>
                                    {skill}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-[#DC2626] mb-3">{t.screening.missingSkills} ({candidate.missing_skills?.length || 0})</h4>
                        <div className="space-y-2">
                          {candidate.missing_skills?.map((skill, i) => {
                            const skillKey = `${candidate.cv_id}-miss-${i}`;
                            const isExpanded = expandedSkill === skillKey;
                            return (
                              <div
                                key={i}
                                onClick={(e) => { e.stopPropagation(); setExpandedSkill(isExpanded ? null : skillKey); }}
                                className={`cursor-pointer rounded-lg border transition-all duration-200 ${isExpanded ? "border-[#DC2626]/20 bg-[#FEF2F2] p-3" : "border-transparent"}`}
                              >
                                <div className="flex items-start gap-2">
                                  <svg className={`w-4 h-4 shrink-0 mt-0.5 text-[#DC2626] transition-transform duration-200 ${isExpanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25,4.5l7.5,7.5,-7.5,7.5" />
                                  </svg>
                                  <span className={`text-sm leading-relaxed ${isExpanded ? "text-[#991B1B] font-medium" : "text-[#DC2626]"}`}>
                                    {skill}
                                  </span>
                                </div>
                                {isExpanded && (
                                  <div className="mt-2 ml-6 text-xs text-[#475569] bg-white rounded-md p-2.5 border border-[#E2E8F0]">
                                    <div className="flex items-center gap-1.5 text-[#DC2626] font-medium mb-1">
                                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12,9v3.75m-9.303,3.376c-.866,1.5,.217,3.374,1.948,3.374h14.71c1.73,0,2.813,-1.874,1.948,-3.374L13.949,3.378c-.866,-1.5,-3.032,-1.5,-3.898,0L2.697,16.126z" /></svg>
                                      AI Reasoning
                                    </div>
                                    {skill}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>

                    {/* AI Analysis */}
                    {candidate.analysis && (
                      <div className="bg-[#F8FAFC] p-4 rounded-lg">
                        <h4 className="font-semibold text-[#0F172A] mb-2">{t.screening.aiAnalysis}</h4>
                        <p className="text-[#475569] leading-relaxed">{candidate.analysis}</p>
                      </div>
                    )}

                    {/* Interview Questions Builder */}
                    <div className="mt-6 pt-6 border-t border-[#E2E8F0]">
                      {/* Generate button — shown when no questions yet */}
                      {!questionsMap[candidate.cv_id] && (
                        <button
                          onClick={(e) => { e.stopPropagation(); generateInterviewQuestions(candidate.cv_id); }}
                          disabled={loadingQuestions === candidate.cv_id}
                          className="flex items-center gap-2 px-4 py-2.5 bg-[#0369A1] text-white rounded-lg hover:bg-[#075985] transition-colors disabled:opacity-50"
                        >
                          {loadingQuestions === candidate.cv_id ? (
                            <>
                              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4,12a8,8,0,018,-8V0C5.373,0,0,5.373,0,12h4z"/></svg>
                              {t.screening.generatingQuestions}
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813,15.904L9,18.75l-.813,-2.846a4.5,4.5,0,00,-3.09,-3.09L2.25,12l2.846,-.813a4.5,4.5,0,003.09,-3.09L9,5.25l.813,2.846a4.5,4.5,0,003.09,3.09L15.75,12l-2.846,.813a4.5,4.5,0,00,-3.09,3.09z" /></svg>
                              {t.screening.generateQuestions}
                            </>
                          )}
                        </button>
                      )}

                      {/* Question list — shown when questions exist */}
                      {questionsMap[candidate.cv_id] && (
                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="font-semibold text-[#0F172A] flex items-center gap-2">
                              <svg className="w-5 h-5 text-[#0369A1]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813,15.904L9,18.75l-.813,-2.846a4.5,4.5,0,00,-3.09,-3.09L2.25,12l2.846,-.813a4.5,4.5,0,003.09,-3.09L9,5.25l.813,2.846a4.5,4.5,0,003.09,3.09L15.75,12l-2.846,.813a4.5,4.5,0,00,-3.09,3.09z" /></svg>
                              {t.screening.interviewQuestions}
                            </h4>
                            <span className="text-sm text-[#64748B]">
                              {questionsMap[candidate.cv_id].filter(q => q.liked).length} {t.screening.questionSelected}
                            </span>
                          </div>

                          <div className="space-y-2 mb-4">
                            {questionsMap[candidate.cv_id].map((q, qi) => (
                              <div
                                key={qi}
                                data-testid="interviewquestioncard"
                                className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${q.liked ? "border-[#BAE6FD] bg-[#F0F9FF]" : "border-[#E2E8F0] bg-white opacity-60"}`}
                                onClick={(e) => e.stopPropagation()}
                              >
                                {/* Like toggle button */}
                                <button
                                  onClick={(e) => { e.stopPropagation(); toggleQuestionLike(candidate.cv_id, qi); }}
                                  className="shrink-0 mt-0.5 cursor-pointer"
                                >
                                  {q.liked ? (
                                    <svg className="w-5 h-5 text-[#0369A1]" fill="currentColor" viewBox="0 0 24 24"><path d="M7.493,18.75c-.425,0,-.82,-.236,-.975,-.632A7.48,7.48,0,016,15.375c0,-1.75,.599,-3.358,1.602,-4.634,.151,-.192,.373,-.309,.6,-.397,.473,-.183,.89,-.514,1.212,-.924a9.042,9.042,0,012.861,-2.4c.723,-.384,1.35,-.956,1.653,-1.715a4.498,4.498,0,00.322,-1.672V3a.75,.75,0,01.75,-.75,2.25,2.25,0,012.25,2.25c0,1.152,-.26,2.243,-.723,3.218,-.266,.558,.107,1.282,.725,1.282h3.126c1.026,0,1.945,.694,2.054,1.715,.045,.422,.068,.85,.068,1.285a11.95,11.95,0,01,-2.649,7.521c-.388,.482,-.987,.729,-1.605,.729H14.23c-.483,0,-.964,-.078,-1.423,-.23l-3.114,-1.04a4.501,4.501,0,00,-1.423,-.23h-.777zM2.331,10.977a11.969,11.969,0,00,-.831,4.398,12,12,0,00.52,3.507c.26,.85,1.084,1.368,1.973,1.368H4.9c.445,0,.72,-.498,.523,-.898a8.963,8.963,0,01,-.924,-3.977c0,-1.708,.476,-3.305,1.302,-4.666,.245,-.403,-.028,-.959,-.5,-.959H4.25c-.832,0,-1.612,.453,-1.918,1.227z"/></svg>
                                  ) : (
                                    <svg className="w-5 h-5 text-[#94A3B8]" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6.633,10.5c.806,0,1.533,-.446,2.031,-1.08a9.041,9.041,0,012.861,-2.4c.723,-.384,1.35,-.956,1.653,-1.715a4.498,4.498,0,00.322,-1.672V3a.75,.75,0,01.75,-.75,2.25,2.25,0,012.25,2.25c0,1.152,-.26,2.243,-.723,3.218,-.266,.558,.107,1.282,.725,1.282h3.126c1.026,0,1.945,.694,2.054,1.715,.045,.422,.068,.85,.068,1.285a11.95,11.95,0,01,-2.649,7.521c-.388,.482,-.987,.729,-1.605,.729H14.23c-.483,0,-.964,-.078,-1.423,-.23l-3.114,-1.04a4.501,4.501,0,00,-1.423,-.23H5.904M14.25,9h0M5.904,18.75c.083,.228,.127,.474,.127,.727v.384c0,.414,-.336,.75,-.75,.75h-.908a.75,.75,0,01,-.727,-.568,11.971,11.971,0,01,-.521,-3.457c0,-1.527,.285,-2.988,.804,-4.33"/></svg>
                                  )}
                                </button>
                                {/* Question text */}
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm text-[#334155] leading-relaxed">{q.question}</p>
                                  <div className="flex items-center gap-2 mt-1">
                                    {q.type && (
                                      <span className="text-xs px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#64748B]">{localizeInterviewQuestionType(q.type, t.screening)}</span>
                                    )}
                                    {q.focus_area && (
                                      <span className="text-xs px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#64748B]">{localizeInterviewFocusArea(q.focus_area)}</span>
                                    )}
                                    {q.source === "custom" && (
                                      <span className="text-xs px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E]">{t.screening.customQuestion}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Add custom question input */}
                          <div className="flex gap-2 mb-4" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={customInput[candidate.cv_id] || ""}
                              onChange={(e) => setCustomInput(prev => ({ ...prev, [candidate.cv_id]: e.target.value }))}
                              onKeyDown={(e) => { if (e.key === "Enter") addCustomQuestion(candidate.cv_id); }}
                              placeholder={t.screening.addCustomQuestion}
                              className="flex-1 px-3 py-2 text-sm border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#0369A1]/20 focus:border-[#0369A1]"
                            />
                            <button
                              onClick={(e) => { e.stopPropagation(); addCustomQuestion(candidate.cv_id); }}
                              disabled={!customInput[candidate.cv_id]?.trim()}
                              className="px-4 py-2 text-sm bg-[#F1F5F9] text-[#334155] rounded-lg hover:bg-[#E2E8F0] transition-colors disabled:opacity-40"
                            >
                              {t.screening.addQuestion}
                            </button>
                          </div>

                          {/* Save button */}
                          <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                            {savedSets.has(candidate.cv_id) ? (
                              <div className="flex items-center gap-2 text-sm text-[#059669]">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5,12.75l6,6,9,-13.5" /></svg>
                                {t.screening.savedSuccess}
                              </div>
                            ) : (
                              <button
                                onClick={(e) => { e.stopPropagation(); saveQuestionSet(candidate.cv_id, candidate.name); }}
                                disabled={savingSet === candidate.cv_id || !questionsMap[candidate.cv_id]?.some(q => q.liked)}
                                className="flex items-center gap-2 px-4 py-2 text-sm bg-[#059669] text-white rounded-lg hover:bg-[#047857] transition-colors disabled:opacity-50"
                              >
                                {savingSet === candidate.cv_id ? (
                                  <>
                                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4,12a8,8,0,018,-8V0C5.373,0,0,5.373,0,12h4z"/></svg>
                                    {t.screening.saving}
                                  </>
                                ) : (
                                  <>
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M17.593,3.322c1.1,.128,1.907,1.077,1.907,2.185V21L12,17.25,4.5,21V5.507c0,-1.108,.806,-2.057,1.907,-2.185a48.507,48.507,0,0111.186,0z" /></svg>
                                    {t.screening.saveQuestionSet} ({questionsMap[candidate.cv_id].filter(q => q.liked).length})
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* No Results */}
          {results.candidates.length === 0 && (
            <div className="text-center py-12 text-[#64748B]">
              <p className="text-lg">{t.screening.noCandidates}</p>
            </div>
          )}

          {/* Saved Question Sets */}
          {results.candidates.length > 0 && (
            <div className="mt-6">
              <button
                onClick={toggleSavedSets}
                className="flex items-center gap-2 text-sm text-[#0369A1] hover:text-[#075985] transition-colors font-medium"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593,3.322c1.1,.128,1.907,1.077,1.907,2.185V21L12,17.25,4.5,21V5.507c0,-1.108,.806,-2.057,1.907,-2.185a48.507,48.507,0,0111.186,0z" />
                </svg>
                {t.screening.viewSavedSets}
                <svg className={`w-4 h-4 transition-transform ${showSavedSets ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5,8.25l-7.5,7.5,-7.5,-7.5" />
                </svg>
              </button>

              {showSavedSets && (
                <div className="mt-3 border border-[#E2E8F0] rounded-xl bg-white overflow-hidden">
                  <div className="px-5 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
                    <h4 className="font-semibold text-[#0F172A] text-sm">{t.screening.savedSets}</h4>
                  </div>

                  {loadingSavedSets ? (
                    <div className="p-6 text-center text-[#64748B] text-sm">
                      <svg className="w-5 h-5 animate-spin mx-auto mb-2" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/><path className="opacity-75" fill="currentColor" d="M4,12a8,8,0,018,-8V0C5.373,0,0,5.373,0,12h4z"/></svg>
                    </div>
                  ) : savedSetsList.length === 0 ? (
                    <div className="p-6 text-center text-[#94A3B8] text-sm">{t.screening.noSavedSets}</div>
                  ) : (
                    <div className="divide-y divide-[#F1F5F9]">
                      {savedSetsList.map(setItem => (
                        <div key={setItem.id}>
                          <div
                            className="px-5 py-3 flex items-center justify-between hover:bg-[#F8FAFC] cursor-pointer transition-colors"
                            onClick={() => expandSet(setItem.id)}
                          >
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-[#F0F9FF] rounded-full flex items-center justify-center text-sm font-medium text-[#0369A1]">
                                {setItem.candidate_name?.charAt(0) || "?"}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-[#0F172A]">{setItem.candidate_name || setItem.cv_id}</p>
                                <p className="text-xs text-[#94A3B8]">
                                  {setItem.question_count} {t.screening.questionsCount} • {new Date(setItem.created_at).toLocaleDateString()}
                                </p>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {expandedSetId === setItem.id && setItem.questions && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); copyAllQuestions(setItem); }}
                                  className="px-2.5 py-1 text-xs rounded-md bg-[#F1F5F9] text-[#475569] hover:bg-[#E2E8F0] transition-colors"
                                >
                                  {copiedId === setItem.id ? t.screening.copied : t.screening.copyAll}
                                </button>
                              )}
                              <button
                                onClick={(e) => { e.stopPropagation(); deleteSet(setItem.id); }}
                                className="px-2.5 py-1 text-xs rounded-md text-[#DC2626] hover:bg-[#FEF2F2] transition-colors"
                              >
                                {t.screening.deleteSet}
                              </button>
                              <svg className={`w-4 h-4 text-[#94A3B8] transition-transform ${expandedSetId === setItem.id ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5,8.25l-7.5,7.5,-7.5,-7.5" />
                              </svg>
                            </div>
                          </div>
                          {expandedSetId === setItem.id && setItem.questions && (
                            <div className="px-5 pb-4 space-y-1.5">
                              {setItem.questions.map((q, qi) => (
                                <div key={qi} className={`flex items-start gap-2.5 p-2.5 rounded-lg text-sm ${q.liked ? "bg-[#F0F9FF]" : "bg-[#F8FAFC] opacity-50"}`}>
                                  <span className="shrink-0 w-5 h-5 rounded-full bg-white border border-[#E2E8F0] text-[#64748B] text-xs flex items-center justify-center mt-0.5">
                                    {qi + 1}
                                  </span>
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[#334155] leading-relaxed">{q.question}</p>
                                    <div className="flex items-center gap-1.5 mt-1">
                                      {q.type && <span className="text-xs px-1.5 py-0.5 rounded bg-[#F1F5F9] text-[#64748B]">{localizeInterviewQuestionType(q.type, t.screening)}</span>}
                                      {q.source === "custom" && <span className="text-xs px-1.5 py-0.5 rounded bg-[#FEF3C7] text-[#92400E]">{t.screening.customQuestion}</span>}
                                      {!q.liked && <span className="text-xs text-[#94A3B8]">✗</span>}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

        </div>
      )}
      {/* CV Detail Modal */}
      {cvDetailModal && (
        <CVDetailModal
          cvId={cvDetailModal.cvId}
          candidateName={cvDetailModal.name}
          onClose={() => setCvDetailModal(null)}
        />
      )}
    </div>
  );
}
