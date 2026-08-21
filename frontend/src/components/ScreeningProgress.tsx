"use client";

import { useLanguage } from "@/i18n";
import { useEffect, useState } from "react";

const TIPS_VI = [
  "💡 Hệ thống đang phân tích kỹ năng, kinh nghiệm và độ phù hợp của từng ứng viên với yêu cầu công việc.",
  "📋 Kết quả sàng lọc là thông tin hỗ trợ; con người vẫn chịu trách nhiệm cho quyết định tuyển dụng.",
  "🎯 AI không chỉ so khớp từ khóa — mà còn hiểu ngữ cảnh: \"3 năm React\" cũng khớp với yêu cầu \"Frontend experience\".",
  "🔍 Mỗi ứng viên được chấm điểm 0-100 dựa trên: kỹ năng khớp, kinh nghiệm, và mức độ phù hợp tổng thể.",
  "⚡ Kết quả sàng lọc được lưu cache — lần sau xem lại sẽ hiển thị ngay lập tức.",
  "📝 Sau khi sàng lọc, bạn có thể tạo câu hỏi phỏng vấn riêng cho từng ứng viên bằng AI.",
  "🏆 Ứng viên được xếp hạng từ cao xuống thấp — giúp bạn ưu tiên phỏng vấn đúng người.",
  "🔬 Hệ thống sử dụng semantic matching (vector embedding) kết hợp LLM để đánh giá toàn diện.",
  "🧪 Hãy dùng dữ liệu tổng hợp khi trình diễn công khai ứng dụng.",
  "🌟 Mẹo: Xem lại kỹ năng, kinh nghiệm và phân tích trước khi quyết định phỏng vấn.",
];

const TIPS_EN = [
  "💡 The system is analyzing each candidate's skills, experience, and job fit against the requirements.",
  "📋 Screening results support review; humans remain responsible for hiring decisions.",
  "🎯 AI goes beyond keyword matching — it understands context: \"3 years React\" also matches \"Frontend experience\".",
  "🔍 Each candidate scores 0-100 based on: skill match, experience level, and overall fit.",
  "⚡ Screening results are cached — next time you view them, they'll load instantly.",
  "📝 After screening, you can generate tailored interview questions for each candidate using AI.",
  "🏆 Candidates are ranked from highest to lowest — helping you prioritize the right interviews.",
  "🔬 The system uses semantic matching (vector embeddings) combined with LLM analysis for comprehensive evaluation.",
  "🧪 Use synthetic data for public demonstrations of the application.",
  "🌟 Tip: Review skills, experience, and analysis before deciding whom to interview.",
];

interface ScreeningProgressProps {
  startTime: number;
}

export default function ScreeningProgress({ startTime }: ScreeningProgressProps) {
  const { language } = useLanguage();
  const tips = language === "vi" ? TIPS_VI : TIPS_EN;
  const [tipIndex, setTipIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [fadeIn, setFadeIn] = useState(true);

  // Rotate tips every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setFadeIn(false);
      setTimeout(() => {
        setTipIndex((prev) => (prev + 1) % tips.length);
        setFadeIn(true);
      }, 300);
    }, 5000);
    return () => clearInterval(interval);
  }, [tips.length]);

  // Track elapsed time
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
  };

  const statusText = language === "vi"
    ? "AI đang phân tích ứng viên..."
    : "AI is analyzing candidates...";

  const pleaseWait = language === "vi"
    ? "Vui lòng đợi trong giây lát"
    : "Please wait a moment";

  return (
    <div className="mt-6 mb-4 space-y-4 animate-in fade-in duration-500">
      {/* Progress card */}
      <div className="bg-white border border-blue-100 rounded-xl p-5 shadow-sm">
        {/* Status header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
                <svg className="w-5 h-5 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
              <div className="absolute -top-0.5 -right-0.5 w-3 h-3 bg-green-400 rounded-full animate-pulse" />
            </div>
            <div>
              <p className="font-semibold text-gray-800">{statusText}</p>
              <p className="text-sm text-gray-500">{pleaseWait}</p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-2xl font-mono font-bold text-blue-600">{formatTime(elapsed)}</span>
          </div>
        </div>

        {/* Animated progress bar */}
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-linear-to-r from-blue-500 via-indigo-500 to-blue-500 rounded-full transition-all duration-1000"
            style={{
              width: "100%",
              animation: "shimmer 2s ease-in-out infinite",
              backgroundSize: "200% 100%",
            }}
          />
        </div>

        {/* Steps indicator */}
        <div className="flex items-center justify-between mt-3 text-xs text-gray-400">
          <span className={elapsed >= 0 ? "text-blue-600 font-medium" : ""}>
            {language === "vi" ? "Trích xuất kỹ năng" : "Extract skills"}
          </span>
          <span className={elapsed >= 3 ? "text-blue-600 font-medium" : ""}>
            {language === "vi" ? "So khớp vector" : "Vector matching"}
          </span>
          <span className={elapsed >= 6 ? "text-blue-600 font-medium" : ""}>
            {language === "vi" ? "Phân tích AI" : "AI analysis"}
          </span>
          <span className={elapsed >= 10 ? "text-blue-600 font-medium" : ""}>
            {language === "vi" ? "Xếp hạng" : "Ranking"}
          </span>
        </div>
      </div>

      {/* Tips carousel */}
      <div className="bg-amber-50 border border-amber-100 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <span className="text-lg shrink-0">💭</span>
          <div className="min-h-[3rem] flex items-center">
            <p
              className={`text-sm text-amber-800 leading-relaxed transition-opacity duration-300 ${
                fadeIn ? "opacity-100" : "opacity-0"
              }`}
            >
              {tips[tipIndex]}
            </p>
          </div>
        </div>
        {/* Dot indicators */}
        <div className="flex justify-center gap-1.5 mt-3">
          {tips.map((_, i) => (
            <div
              key={i}
              className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${
                i === tipIndex ? "bg-amber-500" : "bg-amber-200"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Shimmer animation */}
      <style jsx>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  );
}
