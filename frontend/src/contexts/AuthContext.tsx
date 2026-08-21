"use client";

import axios, { AxiosError } from "axios";
import {
    createContext,
    ReactNode,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";
import toast from "react-hot-toast";
import { notFound } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { getGuestToken, clearGuestTokenStorage, ensureGuestToken } from "@/hooks/useGuestToken";

// Configure axios to send cookies
axios.defaults.withCredentials = true;

// Auto-attach CSRF token + Guest token to requests
axios.interceptors.request.use((config) => {
    const method = config.method?.toLowerCase();
    if (method && method !== "get" && method !== "head" && method !== "options") {
        const match = document.cookie.match(/csrf_token=([^;]+)/);
        if (match) {
            config.headers["X-CSRF-Token"] = match[1];
        }
    }
    // Always send guest token for data ownership tracking
    // ensureGuestToken() creates one if missing (before any API call)
    const guestToken = ensureGuestToken();
    if (guestToken) {
        config.headers["X-Guest-Token"] = guestToken;
    }
    return config;
});

// Auto-refresh on 401: retry the request after refreshing the access token
let isRefreshing = false;
let refreshQueue: Array<{ resolve: (v: unknown) => void; reject: (e: unknown) => void }> = [];

axios.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const original = error.config;
        if (
            error.response?.status === 401 &&
            original &&
            !original.url?.includes("/api/auth/v2/refresh") &&
            !original.url?.includes("/api/auth/v2/login") &&
            !(original as unknown as Record<string, unknown>)._retried
        ) {
            if (isRefreshing) {
                return new Promise((resolve, reject) => {
                    refreshQueue.push({ resolve, reject });
                }).then(() => axios(original));
            }
            isRefreshing = true;
            (original as unknown as Record<string, unknown>)._retried = true;
            try {
                await axios.post(`${API_URL}/api/auth/v2/refresh`);
                refreshQueue.forEach((q) => q.resolve(undefined));
                refreshQueue = [];
                return axios(original);
            } catch {
                refreshQueue.forEach((q) => q.reject(error));
                refreshQueue = [];
                return Promise.reject(error);
            } finally {
                isRefreshing = false;
            }
        }
        return Promise.reject(error);
    }
);

// Toast on 429 (guest limit exceeded) — prompt login
let lastToast429 = 0;
axios.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
        if (error.response?.status === 429) {
            const now = Date.now();
            // Debounce: max 1 toast per 5 seconds
            if (now - lastToast429 > 5000) {
                lastToast429 = now;
                const data = error.response.data as Record<string, unknown> | undefined;
                const detail = data?.detail as Record<string, string> | undefined;
                const message = detail?.message || data?.message as string || "";

                toast(
                    (t) => {
                        const handleClick = () => {
                            toast.dismiss(t.id);
                            window.location.href = "/login";
                        };
                        return (
                            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                <span style={{ fontSize: "20px" }}>⚠️</span>
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 600, marginBottom: "2px" }}>
                                        {message || "Bạn đã hết lượt dùng thử"}
                                    </div>
                                    <button
                                        onClick={handleClick}
                                        style={{
                                            marginTop: "4px",
                                            padding: "4px 12px",
                                            background: "#7C3AED",
                                            color: "white",
                                            border: "none",
                                            borderRadius: "6px",
                                            cursor: "pointer",
                                            fontSize: "13px",
                                            fontWeight: 500,
                                        }}
                                    >
                                        Đăng nhập →
                                    </button>
                                </div>
                            </div>
                        );
                    },
                    {
                        duration: 6000,
                        style: {
                            background: "#FFFBEB",
                            border: "1px solid #F59E0B",
                            padding: "12px 16px",
                            maxWidth: "400px",
                        },
                    }
                );
            }
        }
        return Promise.reject(error);
    }
);

// ========== TYPES ==========

export interface User {
    id: string;
    email: string;
    name: string;
    role: "admin" | "recruiter" | "user";
    organization?: string;
}

export interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    isInitialized: boolean;
}

interface AuthContextType extends AuthState {
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string, name: string, organization?: string) => Promise<void>;
    logout: () => Promise<void>;
    logoutAllSessions: () => Promise<void>;
    refreshAuth: () => Promise<boolean>;
    forgotPassword: (email: string) => Promise<void>;
    resetPassword: (token: string, newPassword: string) => Promise<void>;
    changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
    isAdmin: boolean;
    isRecruiter: boolean;
    error: string | null;
    clearError: () => void;
}

// ========== CONTEXT ==========

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ========== PROVIDER ==========

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isInitialized, setIsInitialized] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Track refresh timer
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
    const lastRefreshRef = useRef<number>(0);
    const userRef = useRef<User | null>(null);

    // Keep userRef in sync
    useEffect(() => {
        userRef.current = user;
    }, [user]);

    // ========== REFRESH LOGIC ==========

    const refreshAuth = useCallback(async (): Promise<boolean> => {
        // Prevent concurrent refreshes
        const now = Date.now();
        if (now - lastRefreshRef.current < 10000) {
            return !!userRef.current;
        }
        lastRefreshRef.current = now;

        try {
            const response = await axios.post(`${API_URL}/api/auth/v2/refresh`);
            if (response.data.success) {
                return true;
            }
            return false;
        } catch {
            // Refresh failed - user needs to login again
            setUser(null);
            return false;
        }
    }, []);

    const scheduleRefresh = useCallback(() => {
        // Clear existing timer
        if (refreshTimerRef.current) {
            clearTimeout(refreshTimerRef.current);
        }

        // Refresh 1 minute before 15min expiry = 14 minutes
        const refreshIn = 14 * 60 * 1000;
        refreshTimerRef.current = setTimeout(async () => {
            const success = await refreshAuth();
            if (success) {
                scheduleRefresh();
            }
        }, refreshIn);
    }, [refreshAuth]);

    // ========== AUTH ACTIONS ==========

    const login = useCallback(
        async (email: string, password: string) => {
            setIsLoading(true);
            setError(null);
            try {
                const guestToken = getGuestToken();
                const response = await axios.post(`${API_URL}/api/auth/v2/login`, {
                    email,
                    password,
                    ...(guestToken && { guest_token: guestToken }),
                });
                if (response.data.success) {
                    setUser(response.data.user);
                    clearGuestTokenStorage();
                    scheduleRefresh();
                }
            } catch (err) {
                const axiosErr = err as AxiosError<{ message?: string; locked_until?: string }>;
                const status = axiosErr.response?.status;
                const data = axiosErr.response?.data;

                // Handle account lockout (HTTP 423)
                if (status === 423) {
                    const lockedUntil = data?.locked_until;
                    const message = lockedUntil
                        ? `Account locked until ${new Date(lockedUntil).toLocaleTimeString()}`
                        : "Account temporarily locked. Please try again later.";
                    setError(message);
                    throw new Error(message);
                }

                const message = data?.message || "Login failed";
                setError(message);
                throw new Error(message);
            } finally {
                setIsLoading(false);
            }
        },
        [scheduleRefresh]
    );

    const register = useCallback(
        async (email: string, password: string, name: string, organization?: string) => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await axios.post(`${API_URL}/api/auth/v2/register`, {
                    email,
                    password,
                    name,
                    organization,
                });
                if (response.data.success) {
                    // Registration successful - user needs to login
                    return;
                }
            } catch (err) {
                const axiosErr = err as AxiosError<{ message?: string }>;
                const message = axiosErr.response?.data?.message || "Registration failed";
                setError(message);
                throw new Error(message);
            } finally {
                setIsLoading(false);
            }
        },
        []
    );

    const clearUserStorage = useCallback(() => {
        if (typeof window === "undefined") return;
        // Clear all user-specific session/local storage
        const sessionKeys = [
            "hr-assistant-current-job", "hr-jobs-context-cache",
            "hr-cvs-list", "hr-sus-completed", "hr-guest-usage",
            "hr-guest-usage-time",
        ];
        sessionKeys.forEach(k => sessionStorage.removeItem(k));
        // Clear chat session caches (dynamic keys)
        for (let i = sessionStorage.length - 1; i >= 0; i--) {
            const key = sessionStorage.key(i);
            if (key?.startsWith("hr-chat-messages-")) sessionStorage.removeItem(key);
        }
        // Clear localStorage chat session IDs
        ["chatSessionId", "agent_session_id"].forEach(k => localStorage.removeItem(k));
        localStorage.removeItem("auth_token");
    }, []);

    const logout = useCallback(async () => {
        try {
            await axios.post(`${API_URL}/api/auth/v2/logout`);
        } catch {
            // Ignore errors - clear local state anyway
        } finally {
            clearUserStorage();
            setUser(null);
            if (refreshTimerRef.current) {
                clearTimeout(refreshTimerRef.current);
            }
        }
    }, [clearUserStorage]);

    const logoutAllSessions = useCallback(async () => {
        try {
            await axios.post(`${API_URL}/api/auth/v2/logout-all`);
        } catch {
            // Ignore errors
        } finally {
            clearUserStorage();
            setUser(null);
            if (refreshTimerRef.current) {
                clearTimeout(refreshTimerRef.current);
            }
        }
    }, [clearUserStorage]);

    const forgotPassword = useCallback(async (email: string) => {
        setError(null);
        try {
            await axios.post(`${API_URL}/api/auth/v2/forgot-password`, { email });
        } catch (err) {
            const axiosErr = err as AxiosError<{ message?: string }>;
            const message = axiosErr.response?.data?.message || "Request failed";
            setError(message);
            throw new Error(message);
        }
    }, []);

    const resetPassword = useCallback(async (token: string, newPassword: string) => {
        setError(null);
        try {
            await axios.post(`${API_URL}/api/auth/v2/reset-password`, {
                token,
                new_password: newPassword,
            });
        } catch (err) {
            const axiosErr = err as AxiosError<{ message?: string }>;
            const message = axiosErr.response?.data?.message || "Reset failed";
            setError(message);
            throw new Error(message);
        }
    }, []);

    const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
        setError(null);
        try {
            await axios.post(
                `${API_URL}/api/auth/v2/change-password`,
                {
                    current_password: currentPassword,
                    new_password: newPassword,
                },
            );
        } catch (err) {
            const axiosErr = err as AxiosError<{ message?: string }>;
            const message = axiosErr.response?.data?.message || "Password change failed";
            setError(message);
            throw new Error(message);
        }
    }, []);

    const clearError = useCallback(() => {
        setError(null);
    }, []);

    // ========== INITIALIZATION ==========

    useEffect(() => {
        const checkAuth = async () => {
            try {
                const response = await axios.get(`${API_URL}/api/auth/v2/status`);
                if (response.data.authenticated && response.data.user) {
                    setUser(response.data.user);
                    scheduleRefresh();
                } else {
                    setUser(null);
                    ensureGuestToken();
                }
            } catch {
                // Not authenticated — ensure guest token exists
                setUser(null);
                ensureGuestToken();
            } finally {
                setIsLoading(false);
                setIsInitialized(true);
            }
        };

        checkAuth();

        // Cleanup on unmount
        return () => {
            if (refreshTimerRef.current) {
                clearTimeout(refreshTimerRef.current);
            }
        };
    }, [scheduleRefresh]);

    // ========== DERIVED STATE ==========

    const isAuthenticated = !!user;
    const isAdmin = user?.role === "admin";
    const isRecruiter = user?.role === "recruiter" || user?.role === "admin";

    // ========== CONTEXT VALUE ==========

    const value: AuthContextType = {
        user,
        isAuthenticated,
        isLoading,
        isInitialized,
        isAdmin,
        isRecruiter,
        error,
        login,
        register,
        logout,
        logoutAllSessions,
        refreshAuth,
        forgotPassword,
        resetPassword,
        changePassword,
        clearError,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ========== HOOK ==========

export function useAuth() {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within AuthProvider");
    }
    return context;
}

// ========== PROTECTED ROUTE COMPONENT ==========

interface ProtectedRouteProps {
    children: ReactNode;
    requireAdmin?: boolean;
    requireRecruiter?: boolean;
    fallback?: ReactNode;
}

export function ProtectedRoute({
    children,
    requireAdmin = false,
    requireRecruiter = false,
    fallback,
}: ProtectedRouteProps) {
    const { isAuthenticated, isAdmin, isRecruiter, isInitialized, isLoading } = useAuth();

    // Show loading state while initializing
    if (!isInitialized || isLoading) {
        return fallback || <div className="flex items-center justify-center min-h-[100dvh]"><div className="w-8 h-8 rounded-full border-2 border-[#0369A1]/20 border-t-[#0369A1] animate-spin" /></div>;
    }

    // Not authenticated - show 404
    if (!isAuthenticated) {
        notFound();
    }

    // Check role requirements
    if ((requireAdmin && !isAdmin) || (requireRecruiter && !isRecruiter)) {
        notFound();
    }

    return <>{children}</>;
}
