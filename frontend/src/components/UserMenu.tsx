"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

export default function UserMenu() {
    const { user, isAuthenticated, logout } = useAuth();
    const { t } = useLanguage();
    const [isOpen, setIsOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    // Close menu on escape key
    useEffect(() => {
        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setIsOpen(false);
            }
        };

        document.addEventListener("keydown", handleEscape);
        return () => document.removeEventListener("keydown", handleEscape);
    }, []);

    if (!isAuthenticated || !user) {
        return (
            <Link
                href="/login"
                title={t.auth.login}
                aria-label={t.auth.login}
                className="flex items-center justify-center md:justify-center lg:justify-start gap-2 px-3 md:px-2 lg:px-4 py-2 bg-linear-to-r from-purple-500 to-indigo-600 text-white rounded-xl hover:shadow-lg hover:shadow-purple-500/30 transition-all"
            >
                <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11,16l-4,-4m0,0l4,-4m-4,4h14m-5,4v1a3,3,0,01,-3,3H6a3,3,0,01,-3,-3V7a3,3,0,013,-3h7a3,3,0,013,3v1" />
                </svg>
                <span className="hidden lg:inline">{t.auth.login}</span>
            </Link>
        );
    }

    const handleLogout = async () => {
        setIsOpen(false);
        await logout();
        window.location.href = "/login";
    };

    // Get user initials
    const initials = user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);

    // Role badge colors
    const roleColors = {
        admin: "bg-red-500",
        recruiter: "bg-blue-500",
        user: "bg-gray-500",
    };

    return (
        <div data-testid="usermenuaccount" ref={menuRef} className="relative">
            {/* User Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                aria-expanded={isOpen}
                aria-haspopup="true"
                aria-label={`User menu for ${user.name}`}
                className="flex items-center justify-center md:justify-center lg:justify-start gap-3 px-2 md:px-2 lg:px-3 py-2 rounded-xl hover:bg-white/5 transition-colors w-full"
            >
                {/* Avatar */}
                <div className="relative shrink-0">
                    <div className="w-10 h-10 rounded-full bg-linear-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white font-medium">
                        {initials}
                    </div>
                    {/* Online indicator */}
                    <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-slate-900" aria-hidden="true"></div>
                </div>

                {/* User Info - hidden when collapsed */}
                <div className="flex-1 text-left hidden lg:block">
                    <p className="text-sm font-medium text-white truncate">{user.name}</p>
                    <p data-testid="usermenuemail" className="text-xs text-gray-400 truncate">{user.email}</p>
                </div>

                {/* Chevron - hidden when collapsed */}
                <svg
                    className={`w-5 h-5 text-gray-400 transition-transform hidden lg:block ${isOpen ? "rotate-180" : ""}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19,9l-7,7,-7,-7" />
                </svg>
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
                <div className="absolute bottom-full left-0 right-0 mb-2 bg-slate-800 border border-white/10 rounded-xl shadow-xl overflow-hidden z-50">
                    {/* User Header */}
                    <div className="px-4 py-3 border-b border-white/10">
                        <p className="text-sm font-medium text-white">{user.name}</p>
                        <p data-testid="usermenuemail" className="text-xs text-gray-400">{user.email}</p>
                        <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded-full text-white ${roleColors[user.role]}`}>
                            {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                        </span>
                    </div>

                    {/* Menu Items */}
                    <div className="py-1">
                        {/* Settings */}
                        <Link
                            href="/settings"
                            onClick={() => setIsOpen(false)}
                            className="flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325,4.317c.426,-1.756,2.924,-1.756,3.35,0a1.724,1.724,0,002.573,1.066c1.543,-.94,3.31,.826,2.37,2.37a1.724,1.724,0,001.065,2.572c1.756,.426,1.756,2.924,0,3.35a1.724,1.724,0,00,-1.066,2.573c.94,1.543,-.826,3.31,-2.37,2.37a1.724,1.724,0,00,-2.572,1.065c-.426,1.756,-2.924,1.756,-3.35,0a1.724,1.724,0,00,-2.573,-1.066c-1.543,.94,-3.31,-.826,-2.37,-2.37a1.724,1.724,0,00,-1.065,-2.572c-1.756,-.426,-1.756,-2.924,0,-3.35a1.724,1.724,0,001.066,-2.573c-.94,-1.543,.826,-3.31,2.37,-2.37,.996,.608,2.296,.07,2.572,-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15,12a3,3,0,11,-6,0,3,3,0,016,0z" />
                            </svg>
                            Settings
                        </Link>

                        {/* Sessions */}
                        <Link
                            href="/settings#sessions"
                            onClick={() => setIsOpen(false)}
                            className="flex items-center gap-3 px-4 py-2 text-gray-300 hover:bg-white/5 hover:text-white transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75,17L9,20l-1,1h8l-1,-1,-.75,-3M3,13h18M5,17h14a2,2,0,002,-2V5a2,2,0,00,-2,-2H5a2,2,0,00,-2,2v10a2,2,0,002,2z" />
                            </svg>
                            {t.auth.sessions}
                        </Link>

                        {/* Logout */}
                        <div className="border-t border-white/10 my-1"></div>
                        <button
                            onClick={handleLogout}
                            className="flex items-center gap-3 px-4 py-2 text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors w-full"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17,16l4,-4m0,0l-4,-4m4,4H7m6,4v1a3,3,0,01,-3,3H6a3,3,0,01,-3,-3V7a3,3,0,013,-3h4a3,3,0,013,3v1" />
                            </svg>
                            {t.auth.logout}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
