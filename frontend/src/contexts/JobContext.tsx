"use client";

import { useAuth } from "@/contexts/AuthContext";
import axios from "axios";
import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Job {
    job_id: string;
    title: string;
    required_skills?: string[];
    experience_years?: string;
    owner_user_id?: string;
    is_public?: boolean;
}

export interface ScreeningCandidate {
    cv_id: string;
    name: string;
    title?: string;
    score?: number;
    matching_skills?: string[];
    missing_skills?: string[];
    analysis?: string;
}

export interface ScreeningResult {
    job_id: string;
    job_title: string;
    candidates: ScreeningCandidate[];
}

interface JobContextType {
    currentJob: Job | null;
    setCurrentJob: (job: Job | null) => void;
    clearJob: () => void;
    jobs: Job[];
    jobsLoading: boolean;
    jobsError: string | null;
    refreshJobs: () => Promise<void>;
    // Screening cache
    screeningResult: ScreeningResult | null;
    screeningLoading: boolean;
    screeningError: string | null;
    runScreening: (jobId: string, topK?: number) => Promise<ScreeningResult | null>;
    clearScreening: () => void;
    // Initialization flag to prevent race conditions
    isInitialized: boolean;
}

const JobContext = createContext<JobContextType | undefined>(undefined);

export function JobProvider({ children }: { children: ReactNode }) {
    const { isInitialized: authInitialized, user } = useAuth();
    const [currentJob, setCurrentJobState] = useState<Job | null>(null);
    const [jobs, setJobs] = useState<Job[]>([]);
    const [jobsLoading, setJobsLoading] = useState(false);
    const [jobsError, setJobsError] = useState<string | null>(null);
    const [screeningResult, setScreeningResult] = useState<ScreeningResult | null>(null);
    const [screeningTopK, setScreeningTopK] = useState<number>(0);
    const [screeningLoading, setScreeningLoading] = useState(false);
    const [screeningError, setScreeningError] = useState<string | null>(null);
    const [isInitialized] = useState(() => typeof window !== "undefined");

    useEffect(() => {
        const stored = sessionStorage.getItem("hr-assistant-current-job");
        if (stored) {
            try {
                setCurrentJobState(JSON.parse(stored) as Job);
            } catch {
                sessionStorage.removeItem("hr-assistant-current-job");
            }
        }
        const cachedJobs = sessionStorage.getItem("hr-jobs-context-cache");
        if (cachedJobs) {
            try {
                setJobs(JSON.parse(cachedJobs) as Job[]);
            } catch {
                sessionStorage.removeItem("hr-jobs-context-cache");
            }
        }
    }, []);

    const setCurrentJob = useCallback((job: Job | null) => {
        setCurrentJobState(job);
        // Persist to sessionStorage for cross-page navigation
        if (job) {
            sessionStorage.setItem("hr-assistant-current-job", JSON.stringify(job));
        } else {
            sessionStorage.removeItem("hr-assistant-current-job");
        }
        // Clear screening cache when job changes
        setScreeningResult(null);
    }, []);

    const clearJob = useCallback(() => {
        setCurrentJobState(null);
        sessionStorage.removeItem("hr-assistant-current-job");
        setScreeningResult(null);
    }, []);

    const refreshJobs = useCallback(async () => {
        setJobsLoading(true);
        setJobsError(null);
        try {
            const response = await axios.get(`${API_URL}/api/jobs`, {
                params: { include_public: true, _t: Date.now() },
                withCredentials: true,
            });
            const mappedJobs: Job[] = (response.data.jobs || []).map(
                (job: { id: string; metadata?: { title?: string; required_skills?: string[]; experience_years?: string; owner_user_id?: string; is_public?: boolean } }) => ({
                    job_id: job.id,
                    title: job.metadata?.title || "Untitled",
                    required_skills: job.metadata?.required_skills || [],
                    experience_years: job.metadata?.experience_years,
                    owner_user_id: job.metadata?.owner_user_id,
                    is_public: job.metadata?.is_public,
                })
            );
            setJobs(mappedJobs);
            // Cache for instant render on next navigation
            sessionStorage.setItem("hr-jobs-context-cache", JSON.stringify(mappedJobs));
        } catch (err) {
            console.error("Failed to load jobs:", err);
            setJobsError("Failed to load jobs. Please try again.");
        } finally {
            setJobsLoading(false);
        }
    }, []);

    const runScreening = useCallback(async (jobId: string, topK: number = 10): Promise<ScreeningResult | null> => {
        // Return in-memory cached result if same job AND topK is <= cached topK
        if (screeningResult && screeningResult.job_id === jobId && topK <= screeningTopK) {
            return screeningResult;
        }

        setScreeningLoading(true);
        setScreeningError(null);
        try {
            // Try DB cache first (GET), fallback to full screening (POST)
            try {
                const cached = await axios.get<ScreeningResult>(`${API_URL}/api/screening/${jobId}`, {
                    withCredentials: true,
                });
                if (cached.data && cached.data.candidates && cached.data.candidates.length >= topK) {
                    const result = cached.data;
                    setScreeningResult(result);
                    setScreeningTopK(cached.data.candidates.length);
                    return result;
                }
            } catch {
                // Cache miss (404) — proceed to POST
            }

            const response = await axios.post<ScreeningResult>(`${API_URL}/api/screening`, {
                job_id: jobId,
                top_k: topK,
            }, {
                withCredentials: true,
            });
            const result = response.data;
            setScreeningResult(result);
            setScreeningTopK(topK);
            return result;
        } catch (err) {
            console.error("Failed to run screening:", err);
            setScreeningError("Failed to run screening. Please try again.");
            return null;
        } finally {
            setScreeningLoading(false);
        }
    }, [screeningResult, screeningTopK]);

    const clearScreening = useCallback(() => {
        setScreeningResult(null);
        setScreeningTopK(0);
        setScreeningError(null);
    }, []);

    // Single effect: fetch jobs once auth is initialized, re-fetch when user changes (login/logout)
    // Sentinel ensures first fetch always fires (guest user?.id is undefined, which would match undefined init)
    const prevUserId = useRef<string | undefined | null>(null);
    useEffect(() => {
        if (!authInitialized) return;
        const currentUserId = user?.id;
        // Skip if user hasn't changed since last fetch
        if (prevUserId.current === currentUserId) return;
        prevUserId.current = currentUserId;
        refreshJobs();
    }, [authInitialized, user, refreshJobs]);

    // Context value includes isInitialized for consumers to know when ready
    const contextValue: JobContextType = {
        currentJob,
        setCurrentJob,
        clearJob,
        jobs,
        jobsLoading,
        jobsError,
        refreshJobs,
        screeningResult,
        screeningLoading,
        screeningError,
        runScreening,
        clearScreening,
        isInitialized,
    };

    return (
        <JobContext.Provider value={contextValue}>
            {children}
        </JobContext.Provider>
    );
}

export function useJob() {
    const context = useContext(JobContext);
    if (context === undefined) {
        throw new Error("useJob must be used within a JobProvider");
    }
    return context;
}
