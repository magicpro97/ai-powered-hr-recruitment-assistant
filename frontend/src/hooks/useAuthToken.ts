"use client";

import { useCallback } from "react";

/**
 * Hook to get auth headers from localStorage.
 * Returns a stable callback that reads token fresh on each call.
 */
export function useAuthToken() {
    // Stable function that reads token fresh each time (handles login/logout)
    const getAuthHeaders = useCallback(() => {
        if (typeof window === "undefined") return {};
        const token = localStorage.getItem("auth_token");
        return token ? { Authorization: `Bearer ${token}` } : {};
    }, []);

    return { getAuthHeaders };
}

/**
 * Get auth token synchronously (for use outside React components)
 */
export function getAuthToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("auth_token");
}
