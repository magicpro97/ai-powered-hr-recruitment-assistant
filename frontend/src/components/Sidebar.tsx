"use client";

import {
  BriefcaseIcon,
  DocumentIcon,
  FolderIcon,
  HomeIcon,
  UsersIcon,
} from "@/components/icons";
import { useAuth } from "@/contexts/AuthContext";
import { useLanguage } from "@/i18n";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { FC, useState } from "react";
import LanguageSwitcher from "./LanguageSwitcher";
import UserMenu from "./UserMenu";

type NavKey = 'home' | 'jobs' | 'cvs' | 'screening';

interface IconProps {
  className?: string;
}

interface NavItem {
  key: NavKey;
  href: string;
  icon: FC<IconProps>;
  descKey: 'systemOverview' | 'step1Desc' | 'step2Desc' | 'step3Desc';
  step?: number;
}

const navigationConfig: NavItem[] = [
  { key: 'home', href: "/dashboard", icon: HomeIcon, descKey: 'systemOverview' },
  { key: 'jobs', href: "/jobs", icon: DocumentIcon, descKey: 'step1Desc', step: 1 },
  { key: 'cvs', href: "/cvs", icon: FolderIcon, descKey: 'step2Desc', step: 2 },
  { key: 'screening', href: "/screening", icon: UsersIcon, descKey: 'step3Desc', step: 3 },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { t, language } = useLanguage();
  const { isAuthenticated } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const subtitle = language === 'vi' ? 'Sàng lọc CV bằng AI' : 'AI-Powered CV Screening';

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed top-3 left-3 z-50 md:hidden w-11 h-11 bg-[#0F172A] rounded-lg flex items-center justify-center text-white shadow-lg cursor-pointer"
        aria-label="Open menu"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <nav
        role="navigation"
        aria-label="Main navigation"
        className={`
          fixed left-0 top-0 h-dvh w-64 bg-[#0F172A] border-r border-[#1E293B] flex flex-col transition-all duration-300 z-40
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:w-16 lg:w-64
        `}
      >
      {/* Logo */}
      <div className="p-4 lg:p-6 border-b border-[#1E293B]">
        <div className="flex items-center gap-3 justify-start lg:justify-start">
          <div className="w-10 h-10 bg-[#0369A1] rounded-lg flex items-center justify-center shrink-0">
            <BriefcaseIcon className="w-6 h-6 text-white" />
          </div>
          <div className="block lg:block md:hidden">
            <h1 className="text-lg font-bold text-white">HR Assistant</h1>
            <p className="text-xs text-[#94A3B8]">{subtitle}</p>
          </div>
          {/* Mobile close button */}
          <button
            onClick={() => setMobileOpen(false)}
            className="ml-auto md:hidden text-[#94A3B8] hover:text-white cursor-pointer"
            aria-label="Close menu"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Language Switcher */}
      <div className="px-2 lg:px-6 py-3 border-b border-[#1E293B]">
        <LanguageSwitcher collapsed />
      </div>

      {/* Workflow Steps Header */}
      <div className="block lg:block md:hidden px-6 py-4">
        <p className="text-xs text-[#64748B] uppercase tracking-wider font-semibold">{t.nav.workflow}</p>
      </div>

      {/* Navigation */}
      <div className="flex-1 px-2 lg:px-3 space-y-1 overflow-y-auto py-2 lg:py-0">
        {navigationConfig.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          const name = t.nav[item.key];
          const description = t.nav[item.descKey];

          return (
            <Link
              key={item.key}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              title={description}
              aria-label={name}
              aria-current={isActive ? "page" : undefined}
              className={`
                group relative flex items-center justify-start md:justify-center lg:justify-start gap-3 px-4 md:px-3 lg:px-4 py-3 rounded-lg transition-all duration-200 cursor-pointer
                ${isActive
                  ? "bg-[#0369A1] text-white"
                  : "text-[#94A3B8] hover:bg-[#1E293B] hover:text-white"
                }
              `}
            >
              <Icon />
              {/* Tooltip for tablet (md only) */}
              <span className="sidebar-tooltip hidden md:block lg:hidden">{name}</span>
              <div className="flex lg:flex md:hidden flex-1 items-center gap-2">
                {item.step && (
                  <span className={`
                    w-5 h-5 rounded-full text-xs font-bold flex items-center justify-center
                    ${isActive ? "bg-white/20 text-white" : "bg-[#334155] text-[#94A3B8]"}
                  `}>
                    {item.step}
                  </span>
                )}
                <span className="font-medium">{name}</span>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Quick Help - only show when authenticated and on desktop */}
      {isAuthenticated && (
        <div data-testid="sidebar-quick-help" className="block lg:block md:hidden p-4 mx-3 mb-3 bg-[#1E293B] rounded-lg">
          <p className="text-xs text-[#94A3B8] font-medium mb-2">{t.nav.quickHelp}</p>
          <p className="text-xs text-[#64748B] leading-relaxed">
            {t.nav.quickHelpText}
          </p>
        </div>
      )}

      {/* User Menu */}
      <div className="p-3 lg:p-3 border-t border-[#1E293B]">
        <UserMenu />
      </div>

      {/* Footer */}
      <div className="p-3 lg:p-4 border-t border-[#1E293B]">
        <div className="flex items-center justify-start md:justify-center lg:justify-start gap-2 text-xs text-[#64748B]">
          <div className="w-2 h-2 bg-[#059669] rounded-full animate-pulse" aria-hidden="true"></div>
          <span className="inline lg:inline md:hidden">GPT-4 • ChromaDB</span>
        </div>
      </div>
    </nav>
    </>
  );
}
