"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { useAuth } from "@/contexts/AuthContext";

const GUEST_TOKEN_KEY = "hr-guest-token";
const GUEST_TOKEN_EVENT = "hr-guest-token-change";

function subscribeGuestToken(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(GUEST_TOKEN_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(GUEST_TOKEN_EVENT, callback);
  };
}

function generateToken(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/**
 * Manages a persistent guest token (UUID) in localStorage.
 * Used to track guest-created data so it can be migrated on login.
 */
export function useGuestToken() {
  const { isAuthenticated, isInitialized } = useAuth();
  const storedToken = useSyncExternalStore(
    subscribeGuestToken,
    getGuestToken,
    () => null,
  );

  useEffect(() => {
    if (isInitialized && !isAuthenticated) ensureGuestToken();
  }, [isAuthenticated, isInitialized]);

  const clearToken = useCallback(() => {
    clearGuestTokenStorage();
  }, []);

  return {
    guestToken: isInitialized && !isAuthenticated ? storedToken : null,
    clearGuestToken: clearToken,
  };
}

/**
 * Get guest token synchronously (for use outside React components, e.g., axios interceptors).
 */
export function getGuestToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(GUEST_TOKEN_KEY);
}

/**
 * Ensure a guest token exists in localStorage (creates one if missing).
 * Call this when auth state is known and user is NOT authenticated.
 */
export function ensureGuestToken(): string {
  if (typeof window === "undefined") return "";
  let token = localStorage.getItem(GUEST_TOKEN_KEY);
  if (!token) {
    token = generateToken();
    localStorage.setItem(GUEST_TOKEN_KEY, token);
    window.dispatchEvent(new Event(GUEST_TOKEN_EVENT));
  }
  return token;
}

export function clearGuestTokenStorage(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(GUEST_TOKEN_KEY);
  window.dispatchEvent(new Event(GUEST_TOKEN_EVENT));
}
