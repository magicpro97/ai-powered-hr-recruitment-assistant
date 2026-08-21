"use client";

import {
  AttachIcon,
  BotIcon,
  ChatIcon,
  CloseIcon,
  DocumentIcon,
  SendIcon,
  TrashIcon,
} from "@/components/icons";
import { ChatMessage, useChatSession } from "@/hooks";
import { useGuestLimits } from "@/hooks/useGuestLimits";
import { useLanguage } from "@/i18n";
import axios from "axios";
import Link from "next/link";
import { startTransition, useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Chatbot() {
  const { t, language } = useLanguage();
  const { isGuest, canSendMessage, getChatMessagesRemaining, refreshUsage, limits } = useGuestLimits();

  // Chatbot-specific UI state
  const [isOpen, setIsOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [guestLimitReached, setGuestLimitReached] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [longWait, setLongWait] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Stats for context-aware welcome message
  const [stats, setStats] = useState<{ jobs: number; cvs: number }>({ jobs: 0, cvs: 0 });

  const loadStats = useCallback(async () => {
    try {
      const [jobsRes, cvsRes] = await Promise.all([
        axios.get(`${API_URL}/api/jobs`),
        axios.get(`${API_URL}/api/cvs`),
      ]);
      setStats({
        jobs: jobsRes.data.jobs?.length || 0,
        cvs: cvsRes.data.cvs?.length || 0,
      });
    } catch (err) {
      console.error("Failed to load stats for chatbot:", err);
    }
  }, []);

  // Get context-aware welcome message
  const getContextAwareWelcome = useCallback(() => {
    if (stats.jobs === 0) {
      return t.chatbot.welcomeNoJobs;
    } else if (stats.cvs === 0) {
      return t.chatbot.welcomeNoCVs.replace('{jobCount}', String(stats.jobs));
    } else {
      return t.chatbot.welcomeReady
        .replace('{jobCount}', String(stats.jobs))
        .replace('{cvCount}', String(stats.cvs));
    }
  }, [stats, t.chatbot.welcomeNoJobs, t.chatbot.welcomeNoCVs, t.chatbot.welcomeReady]);

  // Initialize stats on mount
  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // Callbacks for the hook
  const handleQuotaExceeded = useCallback(() => {
    setGuestLimitReached(true);
    if (isGuest) refreshUsage();
  }, [isGuest, refreshUsage]);

  const handleSendSuccess = useCallback(() => {
    if (isGuest) refreshUsage();
  }, [isGuest, refreshUsage]);

  // Use the shared chat session hook
  const {
    messages,
    setMessages,
    input,
    setInput,
    loading,
    sessionId,
    suggestions,
    mounted,
    messagesEndRef,
    handleSend: baseSend,
    handleSuggestionClick,
    clearHistory: baseClearHistory,
    retryLastMessage: baseRetry,
  } = useChatSession({
    sessionStorageKey: "chatSessionId",
    sessionIdPrefix: "session",
    historyLimit: 10,
    language,
    onQuotaExceeded: handleQuotaExceeded,
    onSendSuccess: handleSendSuccess,
    errorMessage: t.chatbot.error,
  });

  // Set welcome message when stats load and no history
  useEffect(() => {
    if (mounted && messages.length === 0 && stats.jobs !== undefined) {
      startTransition(() => {
        setMessages([{
          role: "assistant",
          content: getContextAwareWelcome(),
          timestamp: new Date(),
        }]);
      });
    }
  }, [mounted, stats, messages.length, getContextAwareWelcome, setMessages]);

  // Wrap handleSend to check guest limits first
  const handleSend = useCallback(async (overrideInput?: string) => {
    if (isGuest && !canSendMessage()) {
      setGuestLimitReached(true);
      return;
    }
    await baseSend(overrideInput);
  }, [isGuest, canSendMessage, baseSend]);

  // Wrap retry
  const retryLastMessage = useCallback(async () => {
    if (isGuest && !canSendMessage()) {
      setGuestLimitReached(true);
      return;
    }
    await baseRetry();
  }, [isGuest, canSendMessage, baseRetry]);

  // Wrap clearHistory to use inline confirm dialog
  const clearHistory = useCallback(async () => {
    setShowConfirmDialog(true);
  }, []);

  const confirmClearHistory = useCallback(async () => {
    setShowConfirmDialog(false);
    await baseClearHistory();
    setMessages([{
      role: "assistant",
      content: t.chatbot.cleared,
      timestamp: new Date(),
    }]);
  }, [baseClearHistory, setMessages, t.chatbot.cleared]);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Long-wait timer
  useEffect(() => {
    if (!loading) return;
    const timer = setTimeout(() => setLongWait(true), 8000);
    return () => {
      clearTimeout(timer);
      setLongWait(false);
    };
  }, [loading]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setToast(t.chatbot.pdfOnly);
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setToast(t.chatbot.maxSize);
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('session_id', sessionId);

    try {
      const uploadingMessage: ChatMessage = {
        role: "user",
        content: `📎 ${t.chatbot.uploading}: ${selectedFile.name}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, uploadingMessage]);

      const response = await axios.post(`${API_URL}/api/chat/upload-cv`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.data.message || `✅ ${t.chatbot.uploadSuccess}\n\n${response.data.summary || ''}`,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (error: unknown) {
      console.error('Upload error:', error);
      const errorMsg = error instanceof Error ? error.message : t.chatbot.unknownError;
      const apiError = error as { response?: { data?: { detail?: string } } };
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: `❌ ${t.chatbot.uploadFailed}: ${apiError.response?.data?.detail || errorMsg}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget === e.target) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      const file = files[0];

      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setToast(t.chatbot.pdfOnly);
        return;
      }

      if (file.size > 10 * 1024 * 1024) {
        setToast(t.chatbot.maxSize);
        return;
      }

      setSelectedFile(file);
    }
  };

  // Prevent hydration mismatch
  if (!mounted) {
    return null;
  }

  // Floating button when closed
  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 md:bottom-6 md:right-6 bg-[#0369A1] text-white p-3.5 md:p-4 rounded-full shadow-lg hover:bg-[#0284C7] hover:shadow-xl transition-all duration-200 z-50 group cursor-pointer"
        aria-label={t.chatbot.openAssistant}
      >
        <ChatIcon />
        <span className="absolute -top-12 right-0 bg-[#0F172A] text-white px-3 py-2 rounded-lg text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap shadow-lg">
          {t.chatbot.assistant}
        </span>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 sm:inset-auto sm:bottom-6 sm:right-6 w-full sm:w-[400px] h-full sm:h-[600px] bg-white sm:rounded-xl shadow-2xl flex flex-col z-50 sm:border border-[#E2E8F0] overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="bg-[#0F172A] text-white p-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-[#0369A1] rounded-lg flex items-center justify-center">
            <BotIcon />
          </div>
          <div>
            <h3 className="font-semibold">{t.chatbot.title}</h3>
            <p className="text-xs text-[#94A3B8]">{t.chatbot.alwaysReady}</p>
          </div>
        </div>
        <div className="flex gap-1">
          <button
            onClick={clearHistory}
            className="hover:bg-white/10 p-2 rounded-lg transition-colors duration-200 cursor-pointer"
            title={t.chatbot.clearHistory}
            aria-label={t.chatbot.clearHistory}
          >
            <TrashIcon />
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="hover:bg-white/10 p-2 rounded-lg transition-colors duration-200 cursor-pointer"
            title={t.chatbot.close}
            aria-label={t.chatbot.close}
          >
            <CloseIcon />
          </button>
        </div>
      </div>

      {/* Messages with Drag & Drop */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#F8FAFC] relative"
        aria-live="polite"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {/* Drag Overlay */}
        {isDragging && (
          <div className="absolute inset-0 bg-[#0369A1]/90 backdrop-blur-sm z-10 flex items-center justify-center pointer-events-none">
            <div className="text-center text-white">
              <div className="w-16 h-16 mx-auto mb-4 bg-white/20 rounded-full flex items-center justify-center">
                <AttachIcon />
              </div>
              <p className="text-xl font-semibold mb-2">{t.chatbot.dropHere}</p>
              <p className="text-[#93C5FD] text-sm">{t.chatbot.pdfOnlyMax}</p>
            </div>
          </div>
        )}

        {messages.map((message, idx) => (
          <div
            key={message.messageId || `msg-${idx}`}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} animate-slide-up`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-3 ${message.role === "user"
                ? "bg-[#0369A1] text-white"
                : "bg-white text-[#0F172A] border border-[#E2E8F0] shadow-sm"
                }`}
            >
              <div className={`text-sm leading-relaxed prose prose-sm max-w-none [&>p]:my-1 [&>ul]:my-1 [&>ol]:my-1 [&>li]:my-0.5 [&>h1]:text-base [&>h2]:text-sm [&>h3]:text-sm [&_code]:px-1 [&_code]:rounded [&_table]:border-collapse [&_table]:w-full [&_th]:border [&_th]:border-slate-300 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:bg-slate-50 [&_td]:border [&_td]:border-slate-200 [&_td]:px-2 [&_td]:py-1 ${message.role === "user"
                ? "text-white prose-invert [&_*]:text-white [&_strong]:text-white [&_a]:!text-[#93C5FD] [&_code]:bg-white/15"
                : "prose-slate [&_strong]:font-bold [&_strong]:text-[#0F172A] [&_a]:text-[#0369A1] [&_code]:bg-slate-100"
                }`}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    a: ({ href, children }) => {
                      // Handle CV download links (relative /api/cvs/{id}/download)
                      if (href && /^\/api\/cvs\/[^/]+\/download$/.test(href)) {
                        const downloadUrl = `${API_URL}${href}`;
                        return (
                          <a
                            href={downloadUrl}
                            className="text-[#0369A1] hover:text-[#0284C7] underline inline-flex items-center gap-1 cursor-pointer"
                            onClick={async (e) => {
                              e.preventDefault();
                              try {
                                const res = await axios.get(downloadUrl, { withCredentials: true, responseType: "blob" });
                                const blob = new Blob([res.data], { type: "application/pdf" });
                                const url = window.URL.createObjectURL(blob);
                                const a = document.createElement("a");
                                a.href = url;
                                const disposition = res.headers["content-disposition"] || "";
                                const match = disposition.match(/filename="?(.+?)"?$/);
                                a.download = match ? match[1] : "CV_download.pdf";
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(url);
                              } catch {
                                alert("Cannot download CV");
                              }
                            }}
                          >
                            📥 {children}
                          </a>
                        );
                      }
                      const safeHref = href && /^https?:\/\//i.test(href) ? href : undefined;
                      return (
                        <a href={safeHref} target="_blank" rel="noopener noreferrer" className={message.role === "user" ? "text-[#93C5FD] hover:text-white underline" : "text-[#0369A1] hover:text-[#0284C7] underline"}>
                          {children}
                        </a>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
              <div className={`flex items-center justify-between mt-2 ${message.role === "user" ? "text-[#93C5FD]" : "text-[#94A3B8]"
                }`}>
                <p className="text-xs">
                  {message.timestamp.toLocaleTimeString(language === 'vi' ? "vi-VN" : "en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              {/* Retry button for error messages */}
              {message.role === "assistant" && message.isError && (
                <button
                  onClick={retryLastMessage}
                  disabled={loading}
                  className="mt-1 text-xs text-[#0369A1] hover:text-[#0284C7] hover:underline font-medium disabled:opacity-50 cursor-pointer"
                >
                  ↻ {t.chatbot.retry}
                </button>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white text-[#0F172A] border border-[#E2E8F0] rounded-xl px-4 py-3 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 bg-[#0369A1] rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-[#0369A1] rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-[#0369A1] rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                {longWait && (
                  <span className="text-xs text-[#64748B] animate-fade-in">{t.chatbot.longWait}</span>
                )}
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-[#E2E8F0] bg-white">
        {/* Guest Limit Warning */}
        {isGuest && (guestLimitReached || getChatMessagesRemaining() <= 3) && (
          <div className={`mb-3 p-3 rounded-lg ${guestLimitReached ? 'bg-red-50 border border-red-200' : 'bg-amber-50 border border-amber-200'}`}>
            <div className="flex items-center gap-2 text-sm">
              <span className={guestLimitReached ? 'text-red-600' : 'text-amber-700'}>
                {guestLimitReached
                  ? `🔒 ${t.guest.limitReached.replace('{feature}', 'chat').replace('{limit}', String(limits.MAX_CHAT_MESSAGES))}`
                  : `⚠️ ${t.guest.quotaWarning.replace('{remaining}', String(getChatMessagesRemaining())).replace('{total}', String(limits.MAX_CHAT_MESSAGES))}`
                }
              </span>
              <Link href="/login" className="text-[#0369A1] hover:underline font-medium ml-auto">
                {t.guest.signInForMore}
              </Link>
            </div>
          </div>
        )}

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {suggestions.map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => handleSuggestionClick(suggestion)}
                className="text-xs bg-[#F1F5F9] text-[#334155] px-3 py-2 sm:py-1.5 rounded-full hover:bg-[#E2E8F0] transition-colors duration-200 font-medium border border-[#E2E8F0] cursor-pointer"
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {/* Selected File Preview */}
        {selectedFile && (
          <div className="mb-3 bg-[#F0F9FF] border border-[#BAE6FD] rounded-lg p-3 flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <div className="w-8 h-8 bg-[#0369A1] rounded-lg flex items-center justify-center text-white">
                <DocumentIcon />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[#0F172A] truncate">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-[#64748B]">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleFileUpload}
                disabled={uploading}
                className="btn-primary text-sm px-3 py-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? t.chatbot.uploadingBtn : t.chatbot.upload}
              </button>
              <button
                onClick={handleRemoveFile}
                disabled={uploading}
                className="text-[#64748B] hover:text-[#DC2626] px-2 py-1 transition-colors duration-200 disabled:opacity-50 cursor-pointer"
              >
                <CloseIcon />
              </button>
            </div>
          </div>
        )}

        {/* Input Row */}
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf"
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || uploading}
            className="bg-[#F1F5F9] text-[#475569] p-3 rounded-lg hover:bg-[#E2E8F0] transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed border border-[#E2E8F0] cursor-pointer"
            title={t.chatbot.attachCv}
            aria-label={t.chatbot.attachCv}
          >
            <AttachIcon />
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder={t.chatbot.placeholder}
            className="input flex-1"
            disabled={loading || uploading}
            aria-label={t.chatbot.placeholder}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || uploading || !input.trim()}
            className="bg-[#0369A1] text-white p-3 rounded-lg hover:bg-[#0284C7] transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            aria-label={t.chatbot.send || "Send message"}
          >
            <SendIcon />
          </button>
        </div>

        <p className="text-xs text-[#94A3B8] mt-2 text-center">
          {t.chatbot.hint}
        </p>
      </div>

      {/* Toast Notification */}
      {toast && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 bg-[#0F172A] text-white px-4 py-2 rounded-lg shadow-lg text-sm z-30 animate-fade-in">
          {toast}
        </div>
      )}

      {/* Confirm Clear Dialog */}
      {showConfirmDialog && (
        <div className="absolute inset-0 bg-black/50 flex items-center justify-center z-20 p-4">
          <div className="bg-white rounded-xl p-6 shadow-xl max-w-sm w-full">
            <p className="text-[#0F172A] font-medium mb-4">{t.chatbot.confirmClear}</p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirmDialog(false)}
                className="px-4 py-2 text-[#64748B] hover:bg-[#F1F5F9] rounded-lg transition-colors cursor-pointer"
              >
                {t.chatbot.cancel}
              </button>
              <button
                onClick={confirmClearHistory}
                className="px-4 py-2 bg-red-500 text-white hover:bg-red-600 rounded-lg transition-colors cursor-pointer"
              >
                {t.chatbot.confirmBtn}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
