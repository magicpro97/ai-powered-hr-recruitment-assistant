"use client";

import GuestBanner from "@/components/GuestBanner";
import {
  ArrowRightIcon,
  CheckIcon,
  CloseIcon,
  DocumentIcon,
  TrashIcon,
} from "@/components/icons";
import { useAuth } from "@/contexts/AuthContext";
import { getCsrfHeaders } from "@/lib/csrf";
import { useJob, Job } from "@/contexts/JobContext";
import { useGuestLimits } from "@/hooks/useGuestLimits";
import { useLanguage } from "@/i18n";
import axios from "axios";
import Link from "next/link";
import { useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface JobData {
  job_id: string;
  title: string;
  experience_years?: string;
  education?: string;
  required_skills: string[];
  preferred_skills: string[];
  responsibilities: string[];
  owner_user_id?: string;
  is_public?: boolean;
}

interface JobDetail {
  id: string;
  text: string;
  metadata: {
    title?: string;
    experience_years?: string;
    education?: string;
    required_skills?: string[];
    preferred_skills?: string[];
    responsibilities?: string[];
    owner_user_id?: string;
    is_public?: boolean;
  };
}

export default function JobsPageClient() {
  const [jobText, setJobText] = useState("");
  const [loading, setLoading] = useState(false);
  const [jobData, setJobData] = useState<JobData | null>(null);
  const [error, setError] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [showMyJobsOnly, setShowMyJobsOnly] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const { t } = useLanguage();
  const { user, isAuthenticated, isAdmin } = useAuth();
  const { jobs, refreshJobs } = useJob();
  const { isGuest, canUploadJob, getJobsRemaining, refreshUsage, limits } = useGuestLimits();

  // Client-side filter: show only my jobs or all (including public)
  const existingJobs = useMemo(() => {
    if (!showMyJobsOnly || !user) return jobs;
    return jobs.filter((j) => j.owner_user_id === user.id);
  }, [jobs, showMyJobsOnly, user]);

  const handleToggleVisibility = async (jobId: string, currentIsPublic: boolean) => {
    try {
      await axios.patch(
        `${API_URL}/api/jobs/${jobId}/visibility`,
        { is_public: !currentIsPublic },
        { headers: { ...getCsrfHeaders() }, withCredentials: true }
      );
      refreshJobs();
    } catch (err) {
      console.error('Error toggling visibility:', err);
    }
  };

  const handleViewDetail = async (jobId: string) => {
    setLoadingDetail(true);
    try {
      const response = await axios.get(`${API_URL}/api/jobs/${jobId}`, {
        withCredentials: true,
      });
      setSelectedJob(response.data);
    } catch (err) {
      console.error('Error loading job detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm(t.jobs.confirmDelete || 'Are you sure you want to delete this job?')) return;
    setDeleting(true);
    try {
      await axios.delete(`${API_URL}/api/jobs/${jobId}`, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setSelectedJob(null);
      refreshJobs();
    } catch (err) {
      console.error('Error deleting job:', err);
    } finally {
      setDeleting(false);
    }
  };

  const handleSubmit = async () => {
    if (!jobText.trim()) {
      setError(t.jobs.pleaseEnter);
      return;
    }

    // Check guest quota before creating job
    if (isGuest && !canUploadJob()) {
      setError(t.guest.limitReached.replace('{feature}', 'Job').replace('{limit}', String(limits.MAX_JOBS)) +
        ` ${t.guest.signInForMore}`);
      return;
    }

    setLoading(true);
    setError("");
    setJobData(null);

    try {
      const response = await axios.post(`${API_URL}/api/jobs`, {
        job_text: jobText,
        is_public: isPublic,
      }, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setJobData(response.data);
      // Refresh guest usage from backend after successful creation
      if (isGuest) {
        refreshUsage();
      }
      // Reload existing jobs list after successful creation
      refreshJobs();
    } catch (err: unknown) {
      const axiosError = err as { response?: { status?: number; data?: { detail?: string; error?: string; message?: string } } };
      // Handle 429 rate limit error from backend
      if (axiosError.response?.status === 429) {
        setError(axiosError.response.data?.message || t.guest.limitReached.replace('{feature}', 'Job').replace('{limit}', String(limits.MAX_JOBS)));
        refreshUsage(); // Sync usage on limit hit
      } else {
        setError(axiosError.response?.data?.detail || t.common.error);
      }
    } finally {
      setLoading(false);
    }
  };

  const isOwner = (job: Job) => {
    return user && job.owner_user_id === user.id;
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Guest Banner - show value proposition */}
      {isGuest && (
        <GuestBanner
          variant={!canUploadJob() ? 'warning' : 'compact'}
          feature="Job"
          remaining={getJobsRemaining()}
          total={limits.MAX_JOBS}
          showUsage
        />
      )}

      {/* Progress Indicator */}
      <div className="mb-6 flex items-center gap-1.5 sm:gap-3">
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#0369A1] text-white rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">1</span>
        <span className="hidden sm:inline text-[#0F172A] font-medium">{t.nav.jobs}</span>
        <div className="flex-1 h-1 bg-[#E2E8F0] rounded"></div>
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#E2E8F0] text-[#94A3B8] rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">2</span>
        <div className="flex-1 h-1 bg-[#E2E8F0] rounded"></div>
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#E2E8F0] text-[#94A3B8] rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">3</span>
      </div>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-[#0F172A] mb-2">{t.jobs.title}</h1>
        <p className="text-sm sm:text-base text-[#64748B] mb-5">{t.jobs.subtitle}</p>
      </div>

      {/* Welcome Card for First-time Users */}
      {existingJobs.length === 0 && !jobData && (
        <div className="mb-6 bg-linear-to-r from-sky-50 to-blue-50 border border-sky-200 rounded-lg p-5">
          <div className="flex items-start gap-4">
            <div className="shrink-0 w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center">
              <span className="text-2xl">🚀</span>
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-sky-900 text-lg mb-2">{t.jobs.welcomeTitle}</h3>
              <p className="text-sky-700 text-sm mb-2">{t.jobs.welcomeDesc}</p>
              <p className="text-sky-600 text-sm">{t.jobs.welcomeTip}</p>
            </div>
          </div>
        </div>
      )}

      {/* Existing Jobs List */}
      {existingJobs.length > 0 && !jobData && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[#0F172A]">
              {t.jobs.existingJobs} ({existingJobs.length})
            </h2>
            {isAuthenticated && (
              <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showMyJobsOnly}
                  onChange={(e) => setShowMyJobsOnly(e.target.checked)}
                  className="w-5 h-5 sm:w-4 sm:h-4 rounded border-slate-300"
                />
                {t.jobs.myJobsOnly || "My jobs only"}
              </label>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {existingJobs.map((job) => (
              <div
                key={job.job_id}
                className="card p-4! hover:shadow-md transition-shadow cursor-pointer group"
                onClick={() => handleViewDetail(job.job_id)}
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-[#F0F9FF] text-[#0369A1] rounded-lg flex items-center justify-center">
                    <DocumentIcon />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-[#0F172A] truncate group-hover:text-[#0369A1] transition-colors">{job.title}</h3>
                      {job.is_public ? (
                        <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">Public</span>
                      ) : (
                        <span className="text-xs px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">Private</span>
                      )}
                    </div>
                    <p className="text-sm text-[#64748B]">
                      {job.experience_years ? `${job.experience_years} ${t.cvs.yearsExp}` : ""}
                    </p>
                    {job.required_skills && job.required_skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {job.required_skills.slice(0, 3).map((skill, idx) => (
                          <span key={idx} className="text-xs px-2 py-0.5 bg-[#E0F2FE] text-[#0369A1] rounded">
                            {skill}
                          </span>
                        ))}
                        {job.required_skills.length > 3 && (
                          <span className="text-xs text-[#64748B]">+{job.required_skills.length - 3}</span>
                        )}
                      </div>
                    )}
                    {/* Visibility toggle for owner or admin */}
                    {(isOwner(job) || isAdmin) && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleToggleVisibility(job.job_id, job.is_public || false); }}
                        className="mt-2 text-xs text-purple-600 hover:text-purple-800 underline"
                      >
                        {job.is_public ? "Make Private" : "Make Public"}
                      </button>
                    )}
                  </div>
                  <svg className="w-5 h-5 text-slate-300 group-hover:text-[#0369A1] transition-colors shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9,5l7,7,-7,7" />
                  </svg>
                </div>
              </div>
            ))}
          </div>
          <div className="border-t border-[#E2E8F0] my-6"></div>
        </div>
      )}

      {/* Input Card */}
      <div className="card mb-6">
        <div className="flex items-center gap-2 mb-3">
          <DocumentIcon />
          <label className="text-base font-semibold text-[#0F172A]">
            {t.jobs.inputLabel}
          </label>
        </div>
        <textarea
          value={jobText}
          onChange={(e) => setJobText(e.target.value)}
          placeholder={t.jobs.placeholder}
          className="input h-72 resize-none"
          data-testid="jobdescriptioninput"
        />

        {/* Public toggle */}
        {isAuthenticated && (
          <label className="flex items-center gap-2 mt-3 text-sm text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300"
            />
            <span>Make this job public (visible to all users)</span>
          </label>
        )}

        <div className="flex items-start gap-2 mt-3 p-3 bg-[#F0F9FF] border border-[#BAE6FD] rounded-lg">
          <svg className="w-4 h-4 text-[#0369A1] mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13,16h-1v-4h-1m1,-4h.01M21,12a9,9,0,11,-18,0,9,9,0,0118,0z" />
          </svg>
          <p className="text-sm text-[#0369A1]">{t.jobs.tip}</p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full py-4 text-lg flex items-center justify-center gap-3 bg-linear-to-r from-[#0369A1] to-[#0284C7] text-white rounded-xl font-semibold hover:from-[#0284C7] hover:to-[#0EA5E9] transition-all shadow-md hover:shadow-lg disabled:opacity-50 cursor-pointer"
        data-testid="analyzejobbutton"
      >
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
            {t.jobs.analyzing}
          </>
        ) : (
          <>
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663,17h4.673M12,3v1m6.364,1.636l-.707,.707M21,12h-1M4,12H3m3.343,-5.657l-.707,-.707m2.828,9.9a5,5,0,117.072,0l-.548,.547A3.374,3.374,0,0014,18.469V19a2,2,0,11,-4,0v-.531c0,-.895,-.356,-1.754,-.988,-2.386l-.548,-.547z" />
            </svg>
            {t.jobs.analyze}
          </>
        )}
      </button>

      {/* Results */}
      {jobData && (
        <div className="mt-8">
          {/* Success Banner */}
          <div className="bg-[#059669] text-white p-6 rounded-xl mb-6">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                <CheckIcon />
              </div>
              <h2 className="text-2xl font-bold">{jobData.title}</h2>
            </div>
            <p className="text-[#A7F3D0]">{t.jobs.success}</p>
          </div>

          {/* Info Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            <div className="card">
              <p className="text-sm text-[#64748B] mb-1">{t.jobs.experience}</p>
              <p className="text-2xl font-bold text-[#0F172A]">{jobData.experience_years || "N/A"}</p>
            </div>
            <div className="card">
              <p className="text-sm text-[#64748B] mb-1">{t.jobs.education}</p>
              <p className="text-lg font-semibold text-[#0F172A]">{jobData.education || t.jobs.notRequired}</p>
            </div>
            <div className="card">
              <p className="text-sm text-[#64748B] mb-1">{t.jobs.jobId}</p>
              <p className="text-sm font-mono text-[#64748B] break-all">{jobData.job_id.substring(0, 16)}...</p>
            </div>
          </div>

          {/* Skills */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
            <div className="card">
              <h3 className="font-semibold text-[#0F172A] mb-3">{t.jobs.requiredSkills}</h3>
              <div className="flex flex-wrap gap-2">
                {jobData.required_skills.map((skill, idx) => (
                  <span key={idx} className="skill-tag skill-tag-required">{skill}</span>
                ))}
              </div>
            </div>
            <div className="card">
              <h3 className="font-semibold text-[#0F172A] mb-3">{t.jobs.preferredSkills}</h3>
              <div className="flex flex-wrap gap-2">
                {jobData.preferred_skills.map((skill, idx) => (
                  <span key={idx} className="skill-tag skill-tag-preferred">{skill}</span>
                ))}
              </div>
            </div>
          </div>

          {/* Responsibilities */}
          {jobData.responsibilities.length > 0 && (
            <div className="card mb-6">
              <h3 className="font-semibold text-[#0F172A] mb-3">{t.jobs.responsibilities}</h3>
              <ul className="space-y-2">
                {jobData.responsibilities.slice(0, 5).map((resp, idx) => (
                  <li key={idx} className="flex items-start gap-3 text-[#475569]">
                    <span className="w-6 h-6 bg-[#F0F9FF] text-[#0369A1] rounded-full flex items-center justify-center text-sm font-medium shrink-0">
                      {idx + 1}
                    </span>
                    {resp}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Next Step */}
          <div className="bg-[#F0F9FF] border border-[#BAE6FD] p-6 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-[#0369A1]">{t.jobs.nextStepTitle}</h3>
                <p className="text-[#0C4A6E]">{t.jobs.nextStepDesc}</p>
              </div>
              <Link href="/cvs" className="btn-primary flex items-center gap-2 cursor-pointer">
                {t.jobs.uploadCv}
                <ArrowRightIcon />
              </Link>
            </div>
          </div>

          {/* Reset Button */}
          <button
            onClick={() => {
              setJobText("");
              setJobData(null);
            }}
            className="mt-6 text-[#64748B] hover:text-[#0F172A] font-medium cursor-pointer"
          >
            {t.jobs.enterAnother}
          </button>
        </div>
      )}
      {/* Job Detail Modal */}
      {(selectedJob || loadingDetail) && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => !loadingDetail && setSelectedJob(null)}>
          <div
            className="bg-white rounded-2xl shadow-2xl max-w-[calc(100vw-2rem)] sm:max-w-3xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {loadingDetail ? (
              <div className="p-12 flex flex-col items-center gap-3">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-[#0369A1] border-t-transparent"></div>
                <p className="text-slate-500 text-sm">{t.jobs.analyzing || 'Loading...'}</p>
              </div>
            ) : selectedJob ? (
              <>
                {/* Modal Header */}
                <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 rounded-t-2xl flex items-center justify-between">
                  <h2 className="text-xl font-bold text-[#0F172A] truncate pr-4">
                    {selectedJob.metadata.title || 'Untitled'}
                  </h2>
                  <div className="flex items-center gap-2 shrink-0">
                    {(isAdmin || (user && selectedJob.metadata.owner_user_id === user.id)) && (
                      <button
                        onClick={() => handleDeleteJob(selectedJob.id)}
                        disabled={deleting}
                        className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                        title={t.common.delete}
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    )}
                    <button
                      onClick={() => setSelectedJob(null)}
                      className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                    >
                      <CloseIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                {/* Modal Body */}
                <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
                  {/* Info Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">{t.jobs.experience}</p>
                      <p className="text-lg font-bold text-[#0F172A]">{selectedJob.metadata.experience_years || 'N/A'}</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">{t.jobs.education}</p>
                      <p className="text-sm font-semibold text-[#0F172A]">{selectedJob.metadata.education || t.jobs.notRequired}</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500 mb-1">{t.jobs.jobId}</p>
                      <p className="text-xs font-mono text-slate-500 break-all">{selectedJob.id.substring(0, 16)}...</p>
                    </div>
                  </div>

                  {/* Skills */}
                  {selectedJob.metadata.required_skills && selectedJob.metadata.required_skills.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-[#0F172A] mb-2">{t.jobs.requiredSkills}</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.metadata.required_skills.map((skill, idx) => (
                          <span key={idx} className="text-sm px-3 py-1 bg-[#E0F2FE] text-[#0369A1] rounded-lg font-medium">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedJob.metadata.preferred_skills && selectedJob.metadata.preferred_skills.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-[#0F172A] mb-2">{t.jobs.preferredSkills}</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.metadata.preferred_skills.map((skill, idx) => (
                          <span key={idx} className="text-sm px-3 py-1 bg-amber-50 text-amber-700 rounded-lg font-medium">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Responsibilities */}
                  {selectedJob.metadata.responsibilities && selectedJob.metadata.responsibilities.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-[#0F172A] mb-2">{t.jobs.responsibilities}</h3>
                      <ul className="space-y-2">
                        {selectedJob.metadata.responsibilities.map((resp, idx) => (
                          <li key={idx} className="flex items-start gap-3 text-sm text-[#475569]">
                            <span className="w-6 h-6 bg-[#F0F9FF] text-[#0369A1] rounded-full flex items-center justify-center text-xs font-medium shrink-0">
                              {idx + 1}
                            </span>
                            {resp}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Original JD Text */}
                  {selectedJob.text && (
                    <div>
                      <h3 className="font-semibold text-[#0F172A] mb-2">{t.jobs.originalText || 'Nội dung gốc'}</h3>
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 max-h-64 overflow-y-auto">
                        <pre className="text-sm text-slate-600 whitespace-pre-wrap font-sans leading-relaxed">{selectedJob.text}</pre>
                      </div>
                    </div>
                  )}
                </div>

                {/* Modal Footer */}
                <div className="border-t border-slate-200 px-6 py-4 flex items-center justify-between">
                  <button
                    onClick={() => setSelectedJob(null)}
                    className="text-sm text-slate-500 hover:text-slate-700 cursor-pointer"
                  >
                    {t.common.close}
                  </button>
                  <Link
                    href="/cvs"
                    className="btn-primary flex items-center gap-2 text-sm cursor-pointer"
                    onClick={() => setSelectedJob(null)}
                  >
                    {t.jobs.uploadCv}
                    <ArrowRightIcon className="w-4 h-4" />
                  </Link>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
