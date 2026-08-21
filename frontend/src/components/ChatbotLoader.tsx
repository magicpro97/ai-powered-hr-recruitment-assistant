"use client";

import dynamic from "next/dynamic";

// bundle-dynamic-imports: Lazy load heavy Chatbot component
const Chatbot = dynamic(() => import("@/components/Chatbot"), {
    ssr: false,
    loading: () => null,
});

export default function ChatbotLoader() {
    return <Chatbot />;
}
