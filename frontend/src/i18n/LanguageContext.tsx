"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { translations, Language, TranslationKeys } from './translations';

interface LanguageContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: TranslationKeys;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

const STORAGE_KEY = 'hr-assistant-language';

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Use lazy initialization to read from localStorage
  const [language, setLanguageState] = useState<Language>(() => {
    // This runs only on client during hydration
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(STORAGE_KEY) as Language;
      if (saved === 'vi' || saved === 'en') {
        return saved;
      }
    }
    return 'vi';
  });

  // Only sync document.lang attribute (external system), no setState
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  // Update localStorage and html lang attribute
  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem(STORAGE_KEY, lang);
  };

  // Get translations for current language
  const t = translations[language];

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
