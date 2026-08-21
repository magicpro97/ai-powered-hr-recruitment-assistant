"use client";

import { useLanguage } from '@/i18n';

interface LanguageSwitcherProps {
  collapsed?: boolean;
}

export default function LanguageSwitcher({ collapsed }: LanguageSwitcherProps) {
  const { language, setLanguage } = useLanguage();

  return (
    <div className={`flex items-center gap-1 bg-[#1E293B] rounded-lg p-1 ${collapsed ? 'md:flex-col lg:flex-row' : ''}`}>
      <button
        onClick={() => setLanguage('vi')}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all cursor-pointer ${collapsed ? 'md:px-1.5 md:py-1 md:text-xs lg:px-3 lg:py-1.5 lg:text-sm' : ''} ${
          language === 'vi'
            ? 'bg-[#0369A1] text-white'
            : 'text-[#94A3B8] hover:text-white'
        }`}
        title="Tiếng Việt"
      >
        VI
      </button>
      <button
        onClick={() => setLanguage('en')}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all cursor-pointer ${collapsed ? 'md:px-1.5 md:py-1 md:text-xs lg:px-3 lg:py-1.5 lg:text-sm' : ''} ${
          language === 'en'
            ? 'bg-[#0369A1] text-white'
            : 'text-[#94A3B8] hover:text-white'
        }`}
        title="English"
      >
        EN
      </button>
    </div>
  );
}
