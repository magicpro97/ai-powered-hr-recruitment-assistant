"use client";

import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================
// SHARED TYPES
// ============================================

/**
 * Unified message interface for all chat components
 */
export interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    timestamp: Date;
    messageId?: string;
    isError?: boolean;
}

/**
 * Backend history message format
 */
interface HistoryMessage {
    role: string;
    content: string;
    timestamp?: string;
    message_id?: string;
}

/**
 * Backend chat response format
 */
interface ChatResponse {
    response: string;
    message_id?: string;
    suggestions?: string[];
}

// ============================================
// HOOK OPTIONS INTERFACE
// ============================================

export interface UseChatSessionOptions {
    /**
     * localStorage key for persisting session ID
     * @example "chatSessionId" for Chatbot, "agent_session_id" for Agent
     */
    sessionStorageKey: string;

    /**
     * Prefix for generating new session IDs
     * @example "session" → "session_1234567890"
     * @example "agent" → "agent_1234567890_abc123"
     */
    sessionIdPrefix: string;

    /**
     * Whether to include random suffix in session ID (agent style)
     * @default false
     */
    includeRandomSuffix?: boolean;

    /**
     * Number of history messages to load
     * @default 10
     */
    historyLimit?: number;

    /**
     * Current language for API requests
     */
    language: string;

    /**
     * Callback when quota exceeded (HTTP 429)
     */
    onQuotaExceeded?: (errorMessage: string) => void;

    /**
     * Callback when message sent successfully
     */
    onSendSuccess?: () => void;

    /**
     * Error message to show on send failure
     */
    errorMessage: string;

    /**
     * Fallback message when response is empty
     */
    noResponseMessage?: string;
}

// ============================================
// HOOK RETURN INTERFACE
// ============================================

export interface UseChatSessionReturn {
    /** Current messages in the session */
    messages: ChatMessage[];

    /** Set messages directly (for welcome message updates) */
    setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;

    /** Current input value */
    input: string;

    /** Set input value */
    setInput: (value: string) => void;

    /** Whether a message is being sent */
    loading: boolean;

    /** Current session ID */
    sessionId: string;

    /** Suggested follow-up questions */
    suggestions: string[];

    /** Set suggestions directly */
    setSuggestions: React.Dispatch<React.SetStateAction<string[]>>;

    /** Whether component has mounted (for hydration) */
    mounted: boolean;

    /** Ref for scrolling to bottom */
    messagesEndRef: React.RefObject<HTMLDivElement | null>;

    /** Send the current input as a message, or send a specific text */
    handleSend: (overrideInput?: string) => Promise<void>;

    /** Handle Enter key press */
    handleKeyDown: (e: React.KeyboardEvent) => void;

    /** @deprecated Use handleKeyDown instead */
    handleKeyPress: (e: React.KeyboardEvent) => void;

    /** Click a suggestion to auto-send it */
    handleSuggestionClick: (suggestion: string) => void;

    /** Clear all messages and history */
    clearHistory: () => Promise<void>;

    /** Retry the last failed message */
    retryLastMessage: () => Promise<void>;
}

// ============================================
// SESSION ID GENERATOR
// ============================================

function createSessionId(prefix: string, includeRandomSuffix: boolean): string {
    const timestamp = Date.now();
    if (includeRandomSuffix) {
        const randomPart = Math.random().toString(36).substring(7);
        return `${prefix}_${timestamp}_${randomPart}`;
    }
    return `${prefix}_${timestamp}`;
}

function getOrCreateSessionId(
    storageKey: string,
    prefix: string,
    includeRandomSuffix: boolean
): string {
    if (typeof window === 'undefined') return '';
    const saved = localStorage.getItem(storageKey);
    if (saved) return saved;
    const newSessionId = createSessionId(prefix, includeRandomSuffix);
    localStorage.setItem(storageKey, newSessionId);
    return newSessionId;
}

// ============================================
// HOOK IMPLEMENTATION
// ============================================

export function useChatSession(options: UseChatSessionOptions): UseChatSessionReturn {
    const {
        sessionStorageKey,
        sessionIdPrefix,
        includeRandomSuffix = false,
        historyLimit = 10,
        language,
        onQuotaExceeded,
        onSendSuccess,
        errorMessage,
        noResponseMessage,
    } = options;

    // ---- State ----
    const cacheKey = `hr-chat-messages-${sessionStorageKey}`;
    const [messages, setMessagesState] = useState<ChatMessage[]>(() => {
        if (typeof window !== "undefined") {
            const cached = sessionStorage.getItem(cacheKey);
            if (cached) try {
                return JSON.parse(cached).map((m: ChatMessage & { timestamp: string }) => ({
                    ...m,
                    timestamp: new Date(m.timestamp),
                }));
            } catch { /* ignore */ }
        }
        return [];
    });
    const setMessages = useCallback((updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
        setMessagesState(prev => {
            const next = typeof updater === "function" ? updater(prev) : updater;
            try {
                sessionStorage.setItem(cacheKey, JSON.stringify(next.slice(-50)));
            } catch { /* storage full */ }
            return next;
        });
    }, [cacheKey]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [sessionId] = useState<string>(() =>
        getOrCreateSessionId(sessionStorageKey, sessionIdPrefix, includeRandomSuffix)
    );
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [mounted] = useState(() => typeof window !== "undefined");

    // ---- Refs ----
    const messagesEndRef = useRef<HTMLDivElement | null>(null);

    // ---- Effects ----

    // Scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Load history on mount (skip if we have cached messages)
    useEffect(() => {
        const hasCached = typeof window !== "undefined" && sessionStorage.getItem(cacheKey);
        if (hasCached) return; // Already restored from cache

        const loadHistory = async (sid: string) => {
            if (!sid) return;
            try {
                const response = await axios.get<{ history: HistoryMessage[] }>(
                    `${API_URL}/api/chat/history/${sid}?limit=${historyLimit}`
                );
                const history = response.data.history || [];

                if (history.length > 0) {
                    const loadedMessages: ChatMessage[] = history.map((msg) => ({
                        role: msg.role === "assistant" ? "assistant" : "user",
                        content: msg.content,
                        timestamp: new Date(msg.timestamp || Date.now()),
                        messageId: msg.message_id,
                    }));
                    setMessages(loadedMessages);
                }
            } catch (error) {
                console.error("Failed to load history:", error);
            }
        };

        if (sessionId) {
            loadHistory(sessionId);
        }
    }, [sessionId, historyLimit, cacheKey, setMessages]);

    // ---- Handlers ----

    const handleSend = useCallback(async (overrideInput?: string) => {
        const messageText = (overrideInput ?? input).trim();
        if (!messageText || loading) return;

        const userMessage: ChatMessage = {
            role: "user",
            content: messageText,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setLoading(true);

        try {
            const response = await axios.post<ChatResponse>(`${API_URL}/api/chat/message`, {
                session_id: sessionId,
                message: messageText,
                language: language,
            });

            // Call success callback
            onSendSuccess?.();

            const assistantMessage: ChatMessage = {
                role: "assistant",
                content: response.data.response || noResponseMessage || "",
                timestamp: new Date(),
                messageId: response.data.message_id,
            };

            setMessages((prev) => [...prev, assistantMessage]);
            setSuggestions(response.data.suggestions || []);

        } catch (error) {
            const axiosError = error as { response?: { status?: number; data?: { message?: string } } };

            if (axiosError.response?.status === 429) {
                // Quota exceeded
                const quotaMessage = axiosError.response.data?.message || errorMessage;
                onQuotaExceeded?.(quotaMessage);

                const limitMessage: ChatMessage = {
                    role: "assistant",
                    content: quotaMessage,
                    timestamp: new Date(),
                    isError: true,
                };
                setMessages((prev) => [...prev, limitMessage]);
            } else {
                console.error("Chat error:", error);
                const errorMessageObj: ChatMessage = {
                    role: "assistant",
                    content: errorMessage,
                    timestamp: new Date(),
                    isError: true,
                };
                setMessages((prev) => [...prev, errorMessageObj]);
            }
        } finally {
            setLoading(false);
        }
    }, [input, loading, sessionId, language, errorMessage, noResponseMessage, onSendSuccess, onQuotaExceeded, setMessages]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    }, [handleSend]);

    // Keep handleKeyPress as alias for backwards compat
    const handleKeyPress = handleKeyDown;

    const handleSuggestionClick = useCallback((suggestion: string) => {
        handleSend(suggestion);
    }, [handleSend]);

    const clearHistory = useCallback(async () => {
        try {
            await axios.post(`${API_URL}/api/chat/clear/${sessionId}`);
        } catch (error) {
            console.error("Failed to clear history:", error);
        }
        setMessages([]);
        setSuggestions([]);
        sessionStorage.removeItem(cacheKey);
    }, [sessionId, cacheKey, setMessages]);

    const retryLastMessage = useCallback(async () => {
        // Use functional update to read latest messages (avoids stale closure)
        let userText = '';
        setMessages(prev => {
            const lastErrorIdx = [...prev].reverse().findIndex(m => m.isError);
            if (lastErrorIdx === -1) return prev;
            const errorIdx = prev.length - 1 - lastErrorIdx;
            for (let i = errorIdx - 1; i >= 0; i--) {
                if (prev[i].role === 'user') {
                    userText = prev[i].content;
                    break;
                }
            }
            if (!userText) return prev;
            return prev.filter((_, i) => i !== errorIdx);
        });
        if (userText) {
            await handleSend(userText);
        }
    }, [handleSend, setMessages]);

    return {
        messages,
        setMessages,
        input,
        setInput,
        loading,
        sessionId,
        suggestions,
        setSuggestions,
        mounted,
        messagesEndRef,
        handleSend,
        handleKeyDown,
        handleKeyPress,
        handleSuggestionClick,
        clearHistory,
        retryLastMessage,
    };
}
