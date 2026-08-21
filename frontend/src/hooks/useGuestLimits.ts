"use client";

import { useAuth } from "@/contexts/AuthContext";
import axios from "axios";
import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Guest limitations - must match backend/guest_limits.py
export const GUEST_LIMITS = {
    MAX_JOBS: 3,
    MAX_CVS: 10,
    MAX_CHAT_MESSAGES: 20,
    MAX_SCREENINGS: 5,
} as const;

interface GuestUsage {
    jobs: number;
    cvs: number;
    chatMessages: number;
    screenings: number;
}

interface BackendUsageResponse {
    is_authenticated: boolean;
    usage: {
        jobs: number;
        cvs: number;
        chat: number;
        screenings: number;
    } | null;
    limits: {
        MAX_JOBS: number;
        MAX_CVS: number;
        MAX_CHAT_MESSAGES: number;
        MAX_SCREENINGS: number;
    } | null;
    remaining: {
        jobs: number;
        cvs: number;
        chat: number;
        screenings: number;
    } | null;
    window_resets_at: string | null;
}

interface UseGuestLimitsReturn {
    usage: GuestUsage;
    limits: typeof GUEST_LIMITS;
    isGuest: boolean;
    isLoading: boolean;
    windowResetsAt: string | null;
    canUploadJob: () => boolean;
    canUploadCV: (count?: number) => boolean;
    canSendMessage: () => boolean;
    canPerformScreening: () => boolean;
    refreshUsage: () => Promise<void>;
    getJobsRemaining: () => number;
    getCVsRemaining: () => number;
    getChatMessagesRemaining: () => number;
    getScreeningsRemaining: () => number;
}

export function useGuestLimits(): UseGuestLimitsReturn {
    const { isAuthenticated, isInitialized } = useAuth();
    const [usage, setUsage] = useState<GuestUsage>({
        jobs: 0,
        cvs: 0,
        chatMessages: 0,
        screenings: 0,
    });
    const [isLoading, setIsLoading] = useState(true);
    const [windowResetsAt, setWindowResetsAt] = useState<string | null>(null);

    const isGuest = isInitialized && !isAuthenticated;

    // Fetch usage from backend API (with short-term cache)
    const refreshUsage = useCallback(async () => {
        if (!isInitialized) return;

        // Short-term cache: skip if fetched within last 10 seconds
        const cacheKey = "hr-guest-usage-cache";
        const cacheTimeKey = "hr-guest-usage-time";
        const cached = sessionStorage.getItem(cacheKey);
        const cachedTime = Number(sessionStorage.getItem(cacheTimeKey) || 0);
        if (cached && Date.now() - cachedTime < 10000) {
            try {
                const data = JSON.parse(cached);
                if (data.usage) {
                    setUsage({
                        jobs: data.usage.jobs,
                        cvs: data.usage.cvs,
                        chatMessages: data.usage.chat,
                        screenings: data.usage.screenings,
                    });
                    setWindowResetsAt(data.window_resets_at);
                }
                setIsLoading(false);
                return;
            } catch { /* fall through to fetch */ }
        }

        try {
            const response = await axios.get<BackendUsageResponse>(
                `${API_URL}/api/guest/usage`,
                { withCredentials: true }
            );

            // Cache the response
            sessionStorage.setItem(cacheKey, JSON.stringify(response.data));
            sessionStorage.setItem(cacheTimeKey, String(Date.now()));

            if (response.data.usage) {
                setUsage({
                    jobs: response.data.usage.jobs,
                    cvs: response.data.usage.cvs,
                    chatMessages: response.data.usage.chat,
                    screenings: response.data.usage.screenings,
                });
                setWindowResetsAt(response.data.window_resets_at);
            } else {
                // Authenticated user - reset to 0
                setUsage({ jobs: 0, cvs: 0, chatMessages: 0, screenings: 0 });
                setWindowResetsAt(null);
            }
        } catch (error) {
            console.error("Failed to fetch guest usage:", error);
        } finally {
            setIsLoading(false);
        }
    }, [isInitialized]);

    // Fetch usage on mount and when auth state changes
    useEffect(() => {
        refreshUsage();
    }, [refreshUsage, isAuthenticated]);

    // Check permissions - for guests, use local state for immediate feedback
    // Backend will enforce the actual limits
    const canUploadJob = useCallback(
        () => !isGuest || usage.jobs < GUEST_LIMITS.MAX_JOBS,
        [isGuest, usage.jobs]
    );

    const canUploadCV = useCallback(
        (count = 1) => !isGuest || usage.cvs + count <= GUEST_LIMITS.MAX_CVS,
        [isGuest, usage.cvs]
    );

    const canSendMessage = useCallback(
        () => !isGuest || usage.chatMessages < GUEST_LIMITS.MAX_CHAT_MESSAGES,
        [isGuest, usage.chatMessages]
    );

    const canPerformScreening = useCallback(
        () => !isGuest || usage.screenings < GUEST_LIMITS.MAX_SCREENINGS,
        [isGuest, usage.screenings]
    );

    // Remaining counts
    const getJobsRemaining = useCallback(
        () => isGuest ? Math.max(0, GUEST_LIMITS.MAX_JOBS - usage.jobs) : Infinity,
        [isGuest, usage.jobs]
    );

    const getCVsRemaining = useCallback(
        () => isGuest ? Math.max(0, GUEST_LIMITS.MAX_CVS - usage.cvs) : Infinity,
        [isGuest, usage.cvs]
    );

    const getChatMessagesRemaining = useCallback(
        () => isGuest ? Math.max(0, GUEST_LIMITS.MAX_CHAT_MESSAGES - usage.chatMessages) : Infinity,
        [isGuest, usage.chatMessages]
    );

    const getScreeningsRemaining = useCallback(
        () => isGuest ? Math.max(0, GUEST_LIMITS.MAX_SCREENINGS - usage.screenings) : Infinity,
        [isGuest, usage.screenings]
    );

    return {
        usage,
        limits: GUEST_LIMITS,
        isGuest,
        isLoading,
        windowResetsAt,
        canUploadJob,
        canUploadCV,
        canSendMessage,
        canPerformScreening,
        refreshUsage,
        getJobsRemaining,
        getCVsRemaining,
        getChatMessagesRemaining,
        getScreeningsRemaining,
    };
}
