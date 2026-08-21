"use client";

import CVDetailModal from "@/components/CVDetailModal";
import GuestBanner from "@/components/GuestBanner";
import {
  ArrowRightIcon,
  CheckIcon,
  DocumentIcon,
  DownloadIcon,
  ExclamationTriangleIcon,
  TrashIcon,
  UploadIcon,
  UserIcon,
} from "@/components/icons";
import { useAuth } from "@/contexts/AuthContext";
import { getCsrfHeaders } from "@/lib/csrf";
import { useJob } from "@/contexts/JobContext";
import { useGuestLimits } from "@/hooks/useGuestLimits";
import { useLanguage } from "@/i18n";
import axios from "axios";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CVData {
  cv_id: string;
  name: string;
  email?: string;
  phone?: string;
  experience_years?: number;
  education?: string;
  skills: string[];
  owner_user_id?: string;
  is_public?: boolean;
}

export default function CVsPageClient() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [cvDataList, setCvDataListState] = useState<CVData[]>(() => {
    if (typeof window !== "undefined") {
      const cached = sessionStorage.getItem("hr-cvs-list");
      if (cached) try { return JSON.parse(cached); } catch { /* ignore */ }
    }
    return [];
  });
  const setCvDataList = useCallback((updater: CVData[] | ((prev: CVData[]) => CVData[])) => {
    setCvDataListState(prev => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      sessionStorage.setItem("hr-cvs-list", JSON.stringify(next));
      return next;
    });
  }, []);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [isPublic, setIsPublic] = useState(false);
  const { t } = useLanguage();
  const { isAuthenticated, isAdmin, user } = useAuth();
  const { jobs, jobsLoading, refreshJobs } = useJob();
  const { isGuest, canUploadCV, getCVsRemaining, refreshUsage, limits } = useGuestLimits();

  // Existing CVs from backend
  interface ExistingCV {
    id: string;
    metadata: {
      name?: string;
      email?: string;
      experience_years?: number;
      skills?: string[];
      owner_user_id?: string;
      is_public?: boolean;
    };
  }
  const [existingCvs, setExistingCvs] = useState<ExistingCV[]>([]);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [showMyOnly, setShowMyOnly] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [cvDetailModal, setCvDetailModal] = useState<{ cvId: string; name: string } | null>(null);

  const loadExistingCvs = useCallback(async () => {
    setLoadingExisting(true);
    try {
      const res = await axios.get(`${API_URL}/api/cvs`, { withCredentials: true });
      setExistingCvs(res.data.cvs || []);
    } catch {
      // silent
    } finally {
      setLoadingExisting(false);
    }
  }, []);

  useEffect(() => { loadExistingCvs(); }, [loadExistingCvs]);

  // Refresh jobs on mount to avoid stale "no JD" warning
  useEffect(() => { refreshJobs(); }, [refreshJobs]);

  const isOwner = (cv: ExistingCV) =>
    user?.id && cv.metadata.owner_user_id === user.id;

  const toggleCvVisibility = async (cvId: string, currentPublic: boolean) => {
    setActionLoading(cvId);
    try {
      await axios.patch(`${API_URL}/api/cvs/${cvId}/visibility`, { is_public: !currentPublic }, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setExistingCvs(prev => prev.map(cv => cv.id === cvId ? { ...cv, metadata: { ...cv.metadata, is_public: !currentPublic } } : cv));
    } catch {
      alert(t.cvs.visibilityError || "Không thể thay đổi trạng thái");
    } finally {
      setActionLoading(null);
    }
  };

  const deleteCv = async (cvId: string) => {
    if (!confirm(t.cvs.confirmDelete || "Bạn chắc chắn muốn xóa CV này?")) return;
    setActionLoading(cvId);
    try {
      await axios.delete(`${API_URL}/api/cvs/${cvId}`, { headers: { ...getCsrfHeaders() }, withCredentials: true });
      setExistingCvs(prev => prev.filter(cv => cv.id !== cvId));
    } catch {
      alert(t.cvs.deleteError || "Không thể xóa CV");
    } finally {
      setActionLoading(null);
    }
  };

  const downloadCv = async (cvId: string) => {
    setActionLoading(cvId);
    try {
      const res = await axios.get(`${API_URL}/api/cvs/${cvId}/download`, {
        withCredentials: true,
        responseType: "blob",
      });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const disposition = res.headers["content-disposition"] || "";
      const match = disposition.match(/filename="?(.+?)"?$/);
      a.download = match ? match[1] : `CV_${cvId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (status === 403) {
        alert(t.cvs.downloadNoPermission);
      } else {
        alert(t.cvs.downloadError);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const filteredCvs = showMyOnly
    ? existingCvs.filter(cv => isOwner(cv))
    : existingCvs;

  // Check if user has created any jobs yet
  const hasJobs = jobs.length > 0;

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles(prev => [...prev, ...acceptedFiles]);
    setError("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      setError(t.cvs.pleaseUpload);
      return;
    }

    // Check guest quota before upload
    if (isGuest && !canUploadCV(files.length)) {
      const remaining = getCVsRemaining();
      setError(t.guest.limitReached.replace('{feature}', 'CV').replace('{limit}', String(limits.MAX_CVS)) +
        ` (${t.guest.quotaWarning.replace('{remaining}', String(remaining)).replace('{total}', String(limits.MAX_CVS))})`);
      return;
    }

    setLoading(true);
    setError("");
    setCvDataList([]);
    setProgress(0);

    // async-parallel: Parallel uploads with real-time progress tracking
    let completed = 0;
    let quotaExceeded = false;

    const uploadWithProgress = async (file: File): Promise<CVData | null> => {
      if (quotaExceeded) return null;
      const formData = new FormData();
      formData.append("file", file);
      try {
        const response = await axios.post(`${API_URL}/api/cvs?is_public=${isPublic}`, formData, {
          headers: { "Content-Type": "multipart/form-data", ...getCsrfHeaders() },
          withCredentials: true,
        });
        return response.data;
      } catch (err) {
        const axiosError = err as { response?: { status?: number; data?: { detail?: string; message?: string } } };
        if (axiosError.response?.status === 429) {
          quotaExceeded = true;
          setError(axiosError.response.data?.message || t.guest.limitReached.replace('{feature}', 'CV').replace('{limit}', String(limits.MAX_CVS)));
          if (isGuest) refreshUsage();
        } else if (axiosError.response?.status === 400) {
          const detail = axiosError.response.data?.detail || '';
          if (detail.includes('extract text') || detail.includes('scanned image')) {
            setError(t.cvs.imagePdfError);
          } else {
            setError(detail || t.cvs.uploadFailed);
          }
        } else {
          console.error(`Error uploading ${file.name}:`, err);
        }
        return null;
      } finally {
        completed++;
        setProgress(Math.round((completed / files.length) * 100));
      }
    };

    try {
      const uploadResults = await Promise.all(files.map(uploadWithProgress));
      const results = uploadResults.filter((r): r is CVData => r !== null);

      if (results.length === 0) {
        setError(t.cvs.uploadFailed);
      } else {
        setCvDataList(results);
        setFiles([]);
        if (results.length < files.length) {
          // Partial success — show actual progress, not 100%
          setProgress(Math.round((results.length / files.length) * 100));
        }
        // Refresh guest usage from backend after successful upload
        if (isGuest) {
          refreshUsage();
        }
        // Reload existing CVs list
        loadExistingCvs();
      }
    } catch (err) {
      console.error("Upload error:", err);
      setError(t.cvs.uploadFailed);
    }

    setLoading(false);
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Guest Privacy Warning */}
      {isGuest && (
        <>
          {!canUploadCV(1) ? (
            <GuestBanner
              variant="warning"
              feature="CV"
              remaining={getCVsRemaining()}
              total={limits.MAX_CVS}
              showUsage
            />
          ) : (
            <div className="bg-linear-to-r from-amber-50 via-orange-50 to-red-50 border border-amber-300 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                  <svg className="w-5 h-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-amber-900 mb-1">
                    {t.guest?.privacyWarningTitle}
                  </h3>
                  <p className="text-sm text-amber-800 mb-3">
                    {t.guest?.privacyWarningDesc}
                  </p>
                  <Link
                    href="/register"
                    className="inline-flex items-center gap-2 bg-linear-to-r from-emerald-500 to-teal-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:from-emerald-600 hover:to-teal-700 transition-all shadow-sm"
                  >
                    {t.guest?.privacyWarningCta}
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Progress Indicator */}
      <div className="mb-6 flex items-center gap-1.5 sm:gap-3">
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#059669] text-white rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">
          <CheckIcon />
        </span>
        <span className="hidden sm:inline text-[#64748B]">{t.nav.jobs}</span>
        <div className="flex-1 h-1 bg-[#059669] rounded"></div>
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#0369A1] text-white rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">2</span>
        <span className="hidden sm:inline text-[#0F172A] font-medium">{t.nav.cvs}</span>
        <div className="flex-1 h-1 bg-[#E2E8F0] rounded"></div>
        <span className="w-7 h-7 sm:w-8 sm:h-8 bg-[#E2E8F0] text-[#94A3B8] rounded-full flex items-center justify-center font-bold text-xs sm:text-sm">3</span>
      </div>

      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-[#0F172A] mb-2">{t.cvs.title}</h1>
        <p className="text-sm sm:text-base text-[#64748B]">{t.cvs.subtitle}</p>
      </div>

      {/* Existing CVs List */}
      {existingCvs.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-[#0F172A]">
              {t.cvs.existingCvs || "CV đã tải lên"} ({filteredCvs.length})
            </h2>
            {isAuthenticated && (
              <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showMyOnly}
                  onChange={(e) => setShowMyOnly(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300"
                />
                <span>{t.cvs.showMyOnly || "Chỉ CV của tôi"}</span>
              </label>
            )}
          </div>

          {/* Legend */}
          {isAuthenticated && (
            <div className="hidden sm:flex flex-wrap items-center gap-x-4 gap-y-1 mb-3 text-xs text-slate-500">
              <span className="font-medium text-slate-600">{t.cvs.legendTitle}:</span>
              <span className="flex items-center gap-1"><span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium">{t.cvs.mine}</span> {t.cvs.legendMine}</span>
              <span className="flex items-center gap-1"><span className="px-1.5 py-0.5 bg-green-50 text-green-700 rounded">{t.cvs.minePublic}</span> {t.cvs.legendPublic}</span>
              <span className="flex items-center gap-1"><span className="px-1.5 py-0.5 bg-slate-50 text-slate-500 rounded">{t.cvs.minePrivate}</span> {t.cvs.legendPrivate}</span>
              <span className="flex items-center gap-1"><span className="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded">{t.cvs.shared}</span> {t.cvs.legendShared}</span>
            </div>
          )}

          {loadingExisting ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg animate-pulse">
                  <div className="w-10 h-10 rounded-lg bg-slate-200 shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-slate-200 rounded w-1/3" />
                    <div className="h-3 bg-slate-100 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredCvs.map((cv) => {
                const m = cv.metadata;
                const mine = isOwner(cv);
                return (
                  <div
                    key={cv.id}
                    className="flex flex-wrap sm:flex-nowrap items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg hover:shadow-sm transition-shadow"
                  >
                    {/* Avatar */}
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm shrink-0 ${mine ? "bg-linear-to-br from-[#0369A1] to-[#0284C7] text-white" : "bg-slate-100 text-slate-600"}`}>
                      {(m.name || "?")[0].toUpperCase()}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
                        <span
                          className="font-medium text-[#0F172A] text-sm truncate hover:text-[#0369A1] cursor-pointer transition-colors"
                          onClick={(e) => { e.stopPropagation(); setCvDetailModal({ cvId: cv.id, name: m.name || "" }); }}
                          title={t.cvDetail?.clickToView || "Bấm để xem chi tiết"}
                        >{m.name || t.cvs.noName}</span>
                        {mine ? (
                          <>
                            <span className="text-[10px] sm:text-xs px-1 sm:px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium shrink-0">{t.cvs.mine}</span>
                            {m.is_public ? (
                              <span className="hidden sm:inline text-xs px-1.5 py-0.5 bg-green-50 text-green-700 rounded shrink-0">{t.cvs.minePublic}</span>
                            ) : (
                              <span className="hidden sm:inline text-xs px-1.5 py-0.5 bg-slate-50 text-slate-500 rounded shrink-0">{t.cvs.minePrivate}</span>
                            )}
                          </>
                        ) : (
                          <span className="hidden sm:inline text-xs px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded shrink-0">{t.cvs.shared}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 sm:gap-2 text-xs text-slate-500 mt-0.5">
                        {m.email && <span className="truncate max-w-[140px] sm:max-w-none">{m.email}</span>}
                        {m.experience_years ? <><span>•</span><span>{m.experience_years} {t.cvs.yearsExp}</span></> : null}
                        {m.skills && m.skills.length > 0 && <><span className="hidden sm:inline">•</span><span className="hidden sm:inline">{m.skills.length} {t.cvs.skills}</span></>}
                      </div>
                    </div>

                    {/* Actions — owner or admin */}
                    {(mine || isAdmin) && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => toggleCvVisibility(cv.id, m.is_public || false)}
                          disabled={actionLoading === cv.id}
                          className={`text-xs px-2.5 py-1 rounded-lg border transition-colors cursor-pointer ${
                            m.is_public
                              ? "text-slate-600 border-slate-200 hover:bg-slate-50"
                              : "text-green-600 border-green-200 hover:bg-green-50"
                          } disabled:opacity-50`}
                          title={m.is_public ? (t.cvs.makePrivate || "Chuyển Private") : (t.cvs.makePublic || "Chuyển Public")}
                        >
                          {actionLoading === cv.id ? "..." : m.is_public ? (t.cvs.makePrivate || "Private") : (t.cvs.makePublic || "Public")}
                        </button>
                        <button
                          onClick={() => downloadCv(cv.id)}
                          disabled={actionLoading === cv.id}
                          className="p-1.5 text-[#0369A1] hover:bg-blue-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                          title={t.cvs.downloadCv || "Tải xuống CV"}
                        >
                          <DownloadIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteCv(cv.id)}
                          disabled={actionLoading === cv.id}
                          className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                          title={t.cvs.deleteCv || "Xóa CV"}
                        >
                          <TrashIcon />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          <div className="border-t border-[#E2E8F0] my-6"></div>
        </div>
      )}

      {/* Empty State Warning - No Jobs Yet */}
      {!jobsLoading && !hasJobs && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <ExclamationTriangleIcon className="w-5 h-5 text-amber-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-800 mb-1">{t.cvs.noJobTitle}</h3>
              <p className="text-amber-700 text-sm mb-3">{t.cvs.noJobDesc}</p>
              <Link
                href="/jobs"
                className="inline-flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors"
              >
                {t.cvs.backToStep1}
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Upload Area */}
      <div
        {...getRootProps()}
        className={`card border-2 border-dashed cursor-pointer transition-all text-center py-12 mb-6 ${isDragActive
          ? "border-[#0369A1] bg-[#F0F9FF]"
          : "border-[#CBD5E1] hover:border-[#0369A1] hover:bg-[#F8FAFC]"
          }`}
        data-testid="cv-upload-dropzone"
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-4">
          <UploadIcon />
          <div>
            <p className="text-lg font-medium text-[#0F172A]">
              {isDragActive ? t.cvs.dropHere : t.cvs.dragDrop}
            </p>
            <p className="text-[#64748B]">{t.cvs.pdfOnly}</p>
          </div>
        </div>
      </div>

      {/* Public toggle */}
      {isAuthenticated && files.length > 0 && (
        <label className="flex items-center gap-2 mb-4 text-sm text-slate-600 cursor-pointer">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
            className="w-4 h-4 rounded border-slate-300"
          />
          <span>Make these CVs public (visible to all users)</span>
        </label>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="card mb-6" data-testid="selected-files-list">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-[#E2E8F0]">
            <h3 className="font-semibold text-[#0F172A]">
              {t.cvs.selectedFiles} <span className="text-[#0369A1]">({files.length})</span>
            </h3>
            <button
              onClick={() => setFiles([])}
              className="text-[#DC2626] hover:text-[#B91C1C] text-sm font-medium px-3 py-1.5 hover:bg-[#FEF2F2] rounded-lg transition-colors"
            >
              {t.cvs.clearAll}
            </button>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {files.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-[#F0F9FF] text-[#0369A1] rounded-lg flex items-center justify-center">
                    <DocumentIcon />
                  </div>
                  <div>
                    <p className="font-medium text-[#0F172A] text-sm">{file.name}</p>
                    <p className="text-xs text-[#64748B]">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(idx)}
                  className="p-2 text-[#DC2626] hover:bg-[#FEF2F2] rounded-lg transition-colors"
                >
                  <TrashIcon />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-[#FEF2F2] border border-[#FECACA] text-[#DC2626] p-4 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Progress Bar (during upload) */}
      {loading && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-[#0F172A]">{t.cvs.processing}</span>
            <span className="text-sm text-[#0369A1] font-bold">
              {progress === 0 ? (
                <span className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-[#0369A1] border-t-transparent"></div>
                  {t.cvs.aiAnalyzing}
                </span>
              ) : (
                `${progress}%`
              )}
            </span>
          </div>
          <div className="w-full bg-[#E2E8F0] rounded-full h-2 overflow-hidden">
            {progress === 0 ? (
              <div className="h-2 bg-linear-to-r from-[#0369A1] via-[#0284C7] to-[#0369A1] animate-pulse w-full"></div>
            ) : (
              <div
                className="bg-[#0369A1] h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              ></div>
            )}
          </div>
          <p className="text-xs text-[#64748B] mt-2">
            {t.cvs.processingHint}
          </p>
        </div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={loading || files.length === 0 || (isGuest && !canUploadCV(files.length))}
        className="btn-primary w-full py-4 text-lg flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="upload-cvs-button"
      >
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
            {t.cvs.analyzing}
          </>
        ) : (
          <>
            <UserIcon />
            {t.cvs.analyze} ({files.length} {t.cvs.files})
          </>
        )}
      </button>

      {/* Results */}
      {cvDataList.length > 0 && (
        <div className="mt-8">
          {/* Success Banner */}
          <div className="bg-[#059669] text-white p-6 rounded-xl mb-6">
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
                <CheckIcon />
              </div>
              <h2 className="text-2xl font-bold">
                {t.cvs.processed} {cvDataList.length} CV!
              </h2>
            </div>
            <p className="text-[#A7F3D0]">{t.cvs.success}</p>
          </div>

          {/* CV Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {cvDataList.map((cv, idx) => (
              <div key={idx} className="card hover:shadow-lg transition-shadow">
                <div className="flex items-start gap-4">
                  <div className="w-12 h-12 bg-linear-to-br from-[#0369A1] to-[#0284C7] text-white rounded-xl flex items-center justify-center font-bold text-lg">
                    {cv.name?.charAt(0) || "?"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3
                        className="font-bold text-[#0F172A] text-lg truncate hover:text-[#0369A1] cursor-pointer transition-colors"
                        onClick={() => setCvDetailModal({ cvId: cv.cv_id, name: cv.name || "" })}
                        title={t.cvDetail?.clickToView || "Bấm để xem chi tiết"}
                      >{cv.name || t.cvs.noName}</h3>
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-medium shrink-0">{t.cvs.mine || "Của tôi"}</span>
                    </div>
                    <p className="text-sm text-[#64748B]">{cv.email || t.cvs.noEmail}</p>
                    <div className="flex items-center gap-3 mt-2 text-sm">
                      <span className="text-[#0369A1] font-medium">
                        {cv.experience_years || 0} {t.cvs.yearsExp}
                      </span>
                      <span className="text-[#64748B]">•</span>
                      <span className="text-[#64748B]">{cv.skills?.length || 0} {t.cvs.skills}</span>
                    </div>
                  </div>
                </div>
                {cv.skills && cv.skills.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {cv.skills.slice(0, 5).map((skill, i) => (
                      <span key={i} className="skill-tag skill-tag-preferred">{skill}</span>
                    ))}
                    {cv.skills.length > 5 && (
                      <span className="text-xs text-[#64748B]">+{cv.skills.length - 5}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Next Step */}
          <div className="bg-[#F0F9FF] border border-[#BAE6FD] p-6 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-[#0369A1]">{t.cvs.nextStepTitle}</h3>
                <p className="text-[#0C4A6E]">{t.cvs.nextStepDesc}</p>
              </div>
              <Link href="/screening" className="btn-primary flex items-center gap-2">
                {t.cvs.startScreening}
                <ArrowRightIcon />
              </Link>
            </div>
          </div>

          {/* Upload More */}
          <button
            onClick={() => {
              setFiles([]);
              setCvDataList([]);
            }}
            className="mt-6 text-[#64748B] hover:text-[#0F172A] font-medium cursor-pointer"
          >
            {t.cvs.uploadMore}
          </button>
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
