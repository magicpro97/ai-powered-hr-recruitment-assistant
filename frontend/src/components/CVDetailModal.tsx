"use client";

import { useLanguage } from "@/i18n";
import axios from "axios";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CVDetailData {
  id: string;
  text: string;
  metadata: {
    name?: string;
    email?: string;
    phone?: string;
    education?: string;
    experience_years?: string | number;
    skills?: string[] | string;
    summary?: string;
    work_history?: string[] | string;
    is_public?: boolean;
    owner_user_id?: string;
  };
}

interface CVDetailModalProps {
  cvId: string;
  candidateName?: string;
  onClose: () => void;
}

export default function CVDetailModal({ cvId, candidateName, onClose }: CVDetailModalProps) {
  const { t } = useLanguage();
  const [data, setData] = useState<CVDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/cvs/${cvId}`, { withCredentials: true });
        setData(res.data);
      } catch {
        setError(t.cvDetail?.loadError || "Không thể tải thông tin CV");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [cvId, t]);

  const parseArray = (val: string[] | string | undefined): string[] => {
    if (!val) return [];
    if (Array.isArray(val)) return val;
    try { return JSON.parse(val); } catch { return [val]; }
  };

  const m = data?.metadata;
  const skills = parseArray(m?.skills);
  const workHistory = parseArray(m?.work_history);

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-[calc(100vw-2rem)] sm:max-w-2xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-slate-200 bg-linear-to-r from-slate-50 to-blue-50">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-linear-to-br from-[#0369A1] to-[#0284C7] text-white rounded-xl flex items-center justify-center font-bold text-lg">
              {(candidateName || m?.name || "?")[0].toUpperCase()}
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">{candidateName || m?.name || t.cvs.noName}</h2>
              <p className="text-xs text-slate-500">{t.cvDetail?.title || "Chi tiết hồ sơ ứng viên"}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 sm:w-8 sm:h-8 flex items-center justify-center rounded-lg hover:bg-slate-200 transition-colors cursor-pointer"
          >
            <svg className="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6,18L18,6M6,6l12,12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-5">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-10 text-red-500 text-sm">{error}</div>
          ) : m ? (
            <>
              {/* Contact Info */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {m.email && (
                  <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3,8l7.89,5.26a2,2,0,002.22,0L21,8M5,19h14a2,2,0,002,-2V7a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
                    </svg>
                    <span className="text-sm text-slate-700 truncate">{m.email}</span>
                  </div>
                )}
                {m.phone && (
                  <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3,5a2,2,0,012,-2h3.28a1,1,0,01.948,.684l1.498,4.493a1,1,0,01,-.502,1.21l-2.257,1.13a11.042,11.042,0,005.516,5.516l1.13,-2.257a1,1,0,011.21,-.502l4.493,1.498a1,1,0,01.684,.949V19a2,2,0,01,-2,2h-1C9.716,21,3,14.284,3,6V5z" />
                    </svg>
                    <span className="text-sm text-slate-700">{m.phone}</span>
                  </div>
                )}
                {m.education && (
                  <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path d="M12,14l9,-5,-9,-5,-9,5,9,5z" /><path d="M12,14l6.16,-3.422a12.083,12.083,0,01.665,6.479A11.952,11.952,0,0012,20.055a11.952,11.952,0,00,-6.824,-2.998,12.078,12.078,0,01.665,-6.479L12,14z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12,14l9,-5,-9,-5,-9,5,9,5zm0,0l6.16,-3.422a12.083,12.083,0,01.665,6.479A11.952,11.952,0,0012,20.055a11.952,11.952,0,00,-6.824,-2.998,12.078,12.078,0,01.665,-6.479L12,14zm-4,6v-7.5l4,-2.222" />
                    </svg>
                    <span className="text-sm text-slate-700">{m.education}</span>
                  </div>
                )}
                {m.experience_years && (
                  <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                    <svg className="w-4 h-4 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21,13.255A23.931,23.931,0,0112,15c-3.183,0,-6.22,-.62,-9,-1.745M16,6V4a2,2,0,00,-2,-2h-4a2,2,0,00,-2,2v2m4,6h.01M5,20h14a2,2,0,002,-2V8a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
                    </svg>
                    <span className="text-sm text-slate-700">{m.experience_years} {t.cvs.yearsExp}</span>
                  </div>
                )}
              </div>

              {/* Summary */}
              {m.summary && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">{t.cvDetail?.summary || "Tóm tắt"}</h3>
                  <p className="text-sm text-slate-600 leading-relaxed bg-blue-50 p-3 rounded-lg border border-blue-100">{m.summary}</p>
                </div>
              )}

              {/* Skills */}
              {skills.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">{t.cvDetail?.skills || "Kỹ năng"}</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {skills.map((skill, i) => (
                      <span key={i} className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs rounded-lg border border-blue-200">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Work History */}
              {workHistory.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">{t.cvDetail?.workHistory || "Kinh nghiệm làm việc"}</h3>
                  <div className="space-y-2">
                    {workHistory.map((item, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm text-slate-600 p-2.5 bg-slate-50 rounded-lg">
                        <span className="w-5 h-5 bg-slate-200 text-slate-500 rounded-full flex items-center justify-center text-xs font-medium shrink-0 mt-0.5">{i + 1}</span>
                        <span className="leading-relaxed">{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
