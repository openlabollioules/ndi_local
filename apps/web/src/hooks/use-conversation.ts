"use client";

import { useState, useCallback, useRef } from "react";
import {
  conversationQueryStream,
  getConversationHistory,
  deleteConversation,
  imageChat,
  type ChartConfig,
  type ImageChatResponse,
} from "@/lib/api";

export type MessageType = "query" | "follow_up" | "analysis" | "explanation" | "error";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  type?: MessageType;
  query?: string;
  queryType?: "sql" | "nosql";
  rows?: Record<string, unknown>[];
  rowCount?: number;
  analysisType?: string;
  sampleSize?: number;
  chartConfig?: ChartConfig;
  timestamp: Date;
  // Streaming state
  isStreaming?: boolean;
  status?: string;
}

export interface UseConversationReturn {
  messages: ChatMessage[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
  sendMessage: (question: string) => Promise<void>;
  sendImageMessage: (file: File, message?: string) => Promise<void>;
  loadHistory: (id: string) => Promise<void>;
  restoreConversation: (id: string, msgs: ChatMessage[]) => void;
  clearConversation: () => void;
  deleteCurrentConversation: () => Promise<void>;
  regenerateLastMessage: () => Promise<void>;
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9);
}

export function useConversation(): UseConversationReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lastUserMessageRef = useRef<string | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim()) return;

    setIsLoading(true);
    setError(null);
    lastUserMessageRef.current = question;

    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: question,
      timestamp: new Date(),
    };

    const streamingId = generateId();

    // Ensure we have a conversation ID (generate one if first message)
    const activeConvId = conversationId || generateId() + generateId();
    if (!conversationId) {
      setConversationId(activeConvId);
    }

    // Add user message + placeholder streaming assistant message
    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: streamingId,
        role: "assistant",
        content: "",
        thinking: "",
        status: "Connexion…",
        isStreaming: true,
        timestamp: new Date(),
      },
    ]);

    try {
      await conversationQueryStream(
        {
          question,
          conversation_id: activeConvId,
        },
        {
          onStatus: (status) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamingId ? { ...m, status } : m,
              ),
            );
          },
          onThinking: (chunk) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamingId
                  ? { ...m, thinking: (m.thinking ?? "") + chunk, status: "Raisonnement…" }
                  : m,
              ),
            );
          },
          onContent: (chunk) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamingId
                  ? { ...m, content: m.content + chunk, status: "" }
                  : m,
              ),
            );
          },
          onAnswer: (result) => {
            // Use server conversation_id if provided, otherwise keep client-generated one
            if (result.conversation_id) {
              setConversationId(result.conversation_id);
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamingId
                  ? {
                      ...m,
                      content: result.answer || m.content,
                      thinking: result.thinking ?? m.thinking,
                      type: (result.question_type as MessageType) || "query",
                      query: result.query,
                      queryType: result.query_type,
                      rows: result.rows,
                      rowCount: result.row_count,
                      chartConfig: result.chart_suggestion,
                      isStreaming: false,
                      status: undefined,
                    }
                  : m,
              ),
            );
          },
          onError: (errMsg) => {
            setError(errMsg);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamingId
                  ? { ...m, content: `Erreur: ${errMsg}`, type: "error" as MessageType, isStreaming: false, status: undefined }
                  : m,
              ),
            );
          },
        },
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Une erreur est survenue";
      setError(errorMessage);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === streamingId
            ? { ...m, content: `Erreur: ${errorMessage}`, type: "error" as MessageType, isStreaming: false, status: undefined }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [conversationId]);

  const loadHistory = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const history = await getConversationHistory(id);

      const chatMessages: ChatMessage[] = history.messages.map((msg, index) => ({
        id: generateId() + index,
        role: msg.role === "user" ? "user" : "assistant",
        content: msg.content,
        thinking: msg.thinking,
        type: msg.intent as MessageType,
        query: msg.query,
        queryType: msg.query_type,
        rowCount: msg.results_count,
        analysisType: msg.analysis,
        timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
      }));

      setMessages(chatMessages);
      setConversationId(id);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur lors du chargement";
      setError(message);
      throw err instanceof Error ? err : new Error(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const restoreConversation = useCallback((id: string, msgs: ChatMessage[]) => {
    setConversationId(id);
    setMessages(msgs);
    setError(null);
    const lastUser = [...msgs].reverse().find(m => m.role === "user");
    lastUserMessageRef.current = lastUser?.content ?? null;
  }, []);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setConversationId(null);
    setError(null);
    lastUserMessageRef.current = null;
  }, []);

  const deleteCurrentConversation = useCallback(async () => {
    if (!conversationId) return;

    try {
      await deleteConversation(conversationId);
      clearConversation();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de la suppression");
    }
  }, [conversationId, clearConversation]);

  const regenerateLastMessage = useCallback(async () => {
    if (!lastUserMessageRef.current) return;

    setMessages((prev) => {
      const lastUserIndex = [...prev].reverse().findIndex(m => m.role === "user");
      if (lastUserIndex === -1) return prev;
      const actualIndex = prev.length - 1 - lastUserIndex;
      return prev.slice(0, actualIndex + 1);
    });

    await sendMessage(lastUserMessageRef.current);
  }, [sendMessage]);

  const sendImageMessage = useCallback(async (file: File, message?: string) => {
    setIsLoading(true);
    setError(null);
    lastUserMessageRef.current = message || `[Image: ${file.name}]`;

    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: message ? `${message} [Image: ${file.name}]` : `[Image: ${file.name}]`,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const response: ImageChatResponse = await imageChat({
        file,
        message,
        conversation_id: conversationId || undefined,
      });

      if (!conversationId) {
        setConversationId(response.conversation_id);
      }

      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: response.answer,
        type: response.action_taken === "ingest_table" ? "query" : "analysis",
        rowCount: response.rows_ingested,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Une erreur est survenue";
      setError(errorMessage);

      const errorMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: `Erreur: ${errorMessage}`,
        type: "error",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }, [conversationId]);

  return {
    messages,
    conversationId,
    isLoading,
    error,
    sendMessage,
    sendImageMessage,
    loadHistory,
    restoreConversation,
    clearConversation,
    deleteCurrentConversation,
    regenerateLastMessage,
  };
}
