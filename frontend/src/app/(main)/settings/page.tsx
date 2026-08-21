"use client";

import { ProtectedRoute, useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import axios from "axios";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Session {
    id: string;
    ip_address: string;
    user_agent: string;
    created_at: string;
    expires_at: string;
}

function SettingsContent() {
    const { user, changePassword, logoutAllSessions, error, clearError } = useAuth();
    const { t } = useLanguage();

    const [sessions, setSessions] = useState<Session[]>([]);
    const [loadingSessions, setLoadingSessions] = useState(true);
    const [revoking, setRevoking] = useState<string | null>(null);

    // Password change form
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState(false);
    const [changingPassword, setChangingPassword] = useState(false);

    // Load sessions
    useEffect(() => {
        const loadSessions = async () => {
            try {
                const response = await axios.get(`${API_URL}/api/auth/v2/sessions`, {
                    withCredentials: true,
                });
                setSessions(response.data.sessions || []);
            } catch (err) {
                console.error("Failed to load sessions:", err);
            } finally {
                setLoadingSessions(false);
            }
        };
        loadSessions();
    }, []);

    const handleRevokeSession = async (sessionId: string) => {
        setRevoking(sessionId);
        const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1];
        try {
            await axios.delete(`${API_URL}/api/auth/v2/sessions/${sessionId}`, {
                withCredentials: true,
                headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
            });
            setSessions(sessions.filter((s) => s.id !== sessionId));
        } catch (err) {
            console.error("Failed to revoke session:", err);
        } finally {
            setRevoking(null);
        }
    };

    const handleLogoutAll = async () => {
        if (!window.confirm(t.auth.logoutAllConfirm)) return;
        await logoutAllSessions();
        window.location.href = "/login";
    };

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordError("");
        setPasswordSuccess(false);
        clearError();

        if (!currentPassword || !newPassword || !confirmPassword) {
            setPasswordError("Please fill in all fields");
            return;
        }
        if (!/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/.test(newPassword)) {
            setPasswordError(t.auth.passwordRequirements);
            return;
        }
        if (newPassword !== confirmPassword) {
            setPasswordError(t.auth.passwordMismatch);
            return;
        }

        setChangingPassword(true);
        try {
            await changePassword(currentPassword, newPassword);
            setPasswordSuccess(true);
            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");
        } catch (err) {
            console.error("Password change failed:", err);
        } finally {
            setChangingPassword(false);
        }
    };

    // Parse user agent to friendly device name
    const parseDevice = (userAgent: string): string => {
        if (!userAgent) return "Unknown device";
        if (userAgent.includes("Chrome")) {
            if (userAgent.includes("Windows")) return "Chrome on Windows";
            if (userAgent.includes("Mac")) return "Chrome on Mac";
            if (userAgent.includes("Linux")) return "Chrome on Linux";
            return "Chrome";
        }
        if (userAgent.includes("Firefox")) return "Firefox";
        if (userAgent.includes("Safari") && !userAgent.includes("Chrome")) return "Safari";
        if (userAgent.includes("Edge")) return "Edge";
        return userAgent.substring(0, 30) + "...";
    };

    const displayError = passwordError || error;

    return (
        <div className="max-w-4xl mx-auto py-4 sm:py-8 px-4">
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-800 mb-6 sm:mb-8">Settings</h1>

            {/* Profile Section */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
                <h2 className="text-xl font-semibold text-slate-800 mb-4">Profile</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">Name</label>
                        <p className="text-slate-800">{user?.name}</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">Email</label>
                        <p className="text-slate-800">{user?.email}</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">Role</label>
                        <span className={`inline-block px-2 py-1 text-xs rounded-full ${user?.role === "admin" ? "bg-red-100 text-red-700" :
                                user?.role === "recruiter" ? "bg-blue-100 text-blue-700" :
                                    "bg-gray-100 text-gray-700"
                            }`}>
                            {user?.role?.charAt(0).toUpperCase()}{user?.role?.slice(1)}
                        </span>
                    </div>
                    {user?.organization && (
                        <div>
                            <label className="block text-sm font-medium text-slate-600 mb-1">Organization</label>
                            <p className="text-slate-800">{user.organization}</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Change Password Section */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 mb-6">
                <h2 className="text-xl font-semibold text-slate-800 mb-4">{t.auth.changePassword}</h2>

                {displayError && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                        {displayError}
                    </div>
                )}
                {passwordSuccess && (
                    <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
                        {t.auth.passwordChanged}
                    </div>
                )}

                <form onSubmit={handlePasswordChange} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                            {t.auth.currentPassword}
                        </label>
                        <input
                            type="password"
                            value={currentPassword}
                            onChange={(e) => setCurrentPassword(e.target.value)}
                            className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500"
                            disabled={changingPassword}
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                            {t.auth.newPassword}
                        </label>
                        <input
                            type="password"
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500"
                            disabled={changingPassword}
                        />
                        <p className="mt-1 text-xs text-slate-500">{t.auth.passwordRequirements}</p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-slate-600 mb-1">
                            {t.auth.confirmPassword}
                        </label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            className="w-full px-4 py-2 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500"
                            disabled={changingPassword}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={changingPassword}
                        className="px-6 py-2 bg-purple-600 text-white rounded-xl hover:bg-purple-700 transition disabled:opacity-50"
                    >
                        {changingPassword ? "Saving..." : t.auth.changePassword}
                    </button>
                </form>
            </div>

            {/* Sessions Section */}
            <div id="sessions" className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-slate-800">{t.auth.activeSessions}</h2>
                    <button
                        onClick={handleLogoutAll}
                        className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition"
                    >
                        {t.auth.logoutAllSessions}
                    </button>
                </div>

                {loadingSessions ? (
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full"></div>
                    </div>
                ) : sessions.length === 0 ? (
                    <p className="text-slate-500 text-center py-8">No active sessions</p>
                ) : (
                    <div className="space-y-3">
                        {sessions.map((session, index) => (
                            <div
                                key={session.id}
                                className="flex items-center justify-between p-4 bg-slate-50 rounded-xl"
                            >
                                <div className="flex items-center gap-4">
                                    <div className="w-10 h-10 bg-slate-200 rounded-full flex items-center justify-center">
                                        <svg className="w-5 h-5 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <p className="font-medium text-slate-800">{parseDevice(session.user_agent)}</p>
                                            {index === 0 && (
                                                <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">
                                                    {t.auth.currentSession}
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-slate-500">
                                            {session.ip_address} • {new Date(session.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                </div>
                                {index !== 0 && (
                                    <button
                                        onClick={() => handleRevokeSession(session.id)}
                                        disabled={revoking === session.id}
                                        className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-lg transition disabled:opacity-50"
                                    >
                                        {revoking === session.id ? "..." : t.auth.revokeSession}
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export default function SettingsPage() {
    return (
        <ProtectedRoute>
            <SettingsContent />
        </ProtectedRoute>
    );
}
