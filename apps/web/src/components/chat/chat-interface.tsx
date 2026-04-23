"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useConversation, type ChatMessage, type MessageType } from "@/hooks/use-conversation";
import { type ChartConfig } from "@/lib/api";
import { ExportButtons } from "./export-buttons";
import { MarkdownRenderer } from "./markdown-renderer";
import { ChartRenderer } from "../chart/chart-renderer";
import { ChartConfigDialog } from "../chart/chart-config-dialog";

/** Serialisable version of ChatMessage (Date → ISO string, rows stripped). */
export interface SerializedChatMessage {
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
  timestamp: string;
}

export interface ConversationItem {
  id: string;
  question: string;
  answer: string;
  timestamp: string;
  sql?: string | null;
  rows?: Record<string, unknown>[];
  messages: SerializedChatMessage[];
}

// Re-export for backward compatibility
export type { ChatMessage, MessageType } from "@/hooks/use-conversation";

function serializeMessages(msgs: ChatMessage[]): SerializedChatMessage[] {
  return msgs.map(({ id, role, content, thinking, type, query, queryType, rows, rowCount, analysisType, sampleSize, chartConfig, timestamp }) => ({
    id, role, content, thinking, type, query, queryType, rows, rowCount, analysisType, sampleSize, chartConfig,
    timestamp: timestamp instanceof Date ? timestamp.toISOString() : String(timestamp),
  }));
}

function deserializeMessages(msgs: SerializedChatMessage[]): ChatMessage[] {
  return msgs.map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
}

interface ChatInterfaceProps {
  databaseMode?: string;
  selectedConversationId?: string | null;
  conversations?: ConversationItem[];
  onConversationUpdate?: (item: ConversationItem) => void;
  onConversationSelect?: (id: string) => void;
}

function getMessageTypeLabel(type?: MessageType): { label: string; variant: "default" | "secondary" | "outline"; className?: string } {
  switch (type) {
    case "query":
      return { label: "Requête", variant: "default" };
    case "follow_up":
      return { label: "Suivi", variant: "secondary" };
    case "analysis":
      return { label: "Analyse", variant: "outline" };
    case "explanation":
      return { label: "Explication", variant: "outline" };
    case "error":
      return { label: "Erreur", variant: "outline", className: "border-red-200 bg-red-50 text-red-700" };
    default:
      return { label: "Réponse", variant: "default" };
  }
}

function formatTimestamp(date: Date): string {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function ChatInterface({ 
  databaseMode = "sql",
  selectedConversationId,
  conversations = [],
  onConversationUpdate,
  onConversationSelect,
}: ChatInterfaceProps) {
  const {
    messages: liveMessages,
    conversationId: liveConversationId,
    isLoading,
    error,
    sendMessage,
    sendImageMessage,
    loadHistory,
    restoreConversation,
    clearConversation,
    regenerateLastMessage,
  } = useConversation();

  const [input, setInput] = useState("");
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const lastSnapshotRef = useRef<string | null>(null);

  const displayMessages = liveMessages;
  const displayConversationId = liveConversationId;

  const prevSelectedRef = useRef(selectedConversationId);

  // Restore full conversation when selecting a sidebar entry, or clear on "new"
  useEffect(() => {
    const wasSelected = prevSelectedRef.current;
    prevSelectedRef.current = selectedConversationId;

    if (!selectedConversationId) {
      if (wasSelected) {
        clearConversation();
        lastSnapshotRef.current = null;
      }
      return;
    }

    if (selectedConversationId === liveConversationId) return;

    const conv = conversations.find(c => c.id === selectedConversationId);

    void (async () => {
      try {
        await loadHistory(selectedConversationId);
      } catch {
        if (conv?.messages?.length) {
          restoreConversation(conv.id, deserializeMessages(conv.messages));
        }
      }
    })();
  }, [selectedConversationId, conversations, liveConversationId, loadHistory, restoreConversation, clearConversation]);

  // Sync all messages to parent on every change
  useEffect(() => {
    if (!liveConversationId || liveMessages.length === 0) return;
    if (!onConversationUpdate) return;

    const snapshot = JSON.stringify({
      id: liveConversationId,
      messages: serializeMessages(liveMessages),
    });
    if (snapshot === lastSnapshotRef.current) return;
    lastSnapshotRef.current = snapshot;

    const firstUser = liveMessages.find(m => m.role === "user");
    const lastAssistant = [...liveMessages].reverse().find(m => m.role === "assistant");
    if (!firstUser) return;

    onConversationUpdate({
      id: liveConversationId,
      question: firstUser.content,
      answer: lastAssistant?.content ?? "",
      timestamp: new Date().toISOString(),
      sql: lastAssistant?.query ?? null,
      rows: lastAssistant?.rows,
      messages: serializeMessages(liveMessages),
    });
  }, [liveConversationId, liveMessages, onConversationUpdate]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [displayMessages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (isLoading) return;

    // If image is selected, use image chat
    if (selectedImage) {
      await handleImageSubmit();
      return;
    }

    // Otherwise use text chat
    if (!input.trim()) return;
    const question = input.trim();
    setInput("");
    await sendMessage(question);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
    textareaRef.current?.focus();
  };

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"];
    if (!allowedTypes.includes(file.type)) {
      alert("Type de fichier non supporté. Utilisez: JPG, PNG, GIF, WebP, BMP");
      return;
    }

    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert("Fichier trop volumineux. Maximum: 10 Mo");
      return;
    }

    setSelectedImage(file);
    
    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setImagePreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const clearSelectedImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleImageSubmit = async () => {
    if (!selectedImage) return;
    
    const message = input.trim();
    setInput("");
    await sendImageMessage(selectedImage, message || undefined);
    clearSelectedImage();
  };

  const suggestions = databaseMode === "nosql"
    ? [
        "Montre les 10 premiers documents",
        "Compte le nombre total d'enregistrements",
        "Quelles sont les valeurs distinctes de la colonne statut ?",
        "Évalue la cohérence entre Motif et Commentaires",
        "📷 Upload une image de tableau à extraire",
      ]
    : [
        "Montre les 10 premières lignes",
        "Compte le nombre total de lignes",
        "Quelles sont les valeurs distinctes de la colonne statut ?",
        "Évalue la cohérence entre Motif et Commentaires",
        "📷 Upload une image de tableau à extraire",
      ];

  return (
    <div className="flex flex-col h-full">
      {/* Header with conversation info */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Conversation</span>
          {displayConversationId && (
            <Badge variant="outline" className="text-xs">
              #{displayConversationId.slice(0, 8)}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {displayMessages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                clearConversation();
                if (onConversationSelect) {
                  onConversationSelect("");
                }
              }}
              className="text-muted-foreground hover:text-foreground"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mr-1"
              >
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 12" />
                <path d="M3 3v9h9" />
              </svg>
              Nouvelle
            </Button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {displayMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
            <div className="text-muted-foreground">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mx-auto mb-4 opacity-50"
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <p className="text-lg font-medium">Commencez une conversation</p>
              <p className="text-sm mt-1">
                Posez une question sur vos données, uploadez une image 📷, ou essayez une suggestion ci-dessous.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg">
              {suggestions.map((suggestion, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => handleSuggestionClick(suggestion)}
                  className="text-xs"
                >
                  {suggestion}
                </Button>
              ))}
            </div>
          </div>
        ) : (
          displayMessages.map((message, index) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLast={index === displayMessages.length - 1}
              onRegenerate={message.role === "assistant" && index === displayMessages.length - 1 ? regenerateLastMessage : undefined}
            />
          ))
        )}
        {isLoading && !displayMessages.some(m => m.isStreaming) && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary border-t-transparent" />
            <span className="text-sm">L&apos;assistant réfléchit...</span>
          </div>
        )}
        {error && (
          <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
            {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t p-4 bg-background">
        {/* Image preview */}
        {imagePreview && (
          <div className="mb-3 relative inline-block">
            <div className="relative rounded-lg overflow-hidden border border-border">
              <img 
                src={imagePreview} 
                alt="Preview" 
                className="max-h-[150px] max-w-full object-contain"
              />
              <button
                type="button"
                onClick={clearSelectedImage}
                className="absolute top-1 right-1 bg-background/80 hover:bg-background text-foreground rounded-full p-1"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6 6 18"/><path d="m6 6 12 12"/>
                </svg>
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {selectedImage?.name} ({(selectedImage!.size / 1024 / 1024).toFixed(2)} Mo)
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          <div className="relative">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={imagePreview 
                ? "Décrivez ce que vous voulez faire avec cette image... (ex: 'Extraire le tableau')" 
                : "Posez une question... (Shift+Enter pour nouvelle ligne)"}
              className="min-h-[60px] max-h-[200px] pr-24 resize-none"
              disabled={isLoading}
              rows={1}
            />
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              {/* Image upload button */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageSelect}
                className="hidden"
              />
              <Button
                type="button"
                size="icon"
                variant="ghost"
                disabled={isLoading}
                onClick={() => fileInputRef.current?.click()}
                className={`h-8 w-8 ${imagePreview ? 'text-primary' : 'text-muted-foreground'}`}
                title="Joindre une image"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
                  <circle cx="9" cy="9" r="2"/>
                  <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
                </svg>
              </Button>
              {/* Send button */}
              <Button
                type="submit"
                size="icon"
                disabled={(!input.trim() && !imagePreview) || isLoading}
                className="h-8 w-8"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m22 2-7 20-4-9-9-4Z" />
                  <path d="M22 2 11 13" />
                </svg>
              </Button>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Mode: {databaseMode === "nosql" ? "Documents" : "SQL"} •{" "}
              {displayMessages.filter(m => m.role === "user").length} message(s)
              {imagePreview && " • Image prête à l'envoi"}
            </span>
            <span>
              {imagePreview 
                ? "Décrivez l'action souhaitée puis envoyez" 
                : "Entrée pour envoyer • Shift+Entrée pour nouvelle ligne"}
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}

interface MessageBubbleProps {
  message: ChatMessage;
  isLast: boolean;
  onRegenerate?: () => void;
}

function MessageBubble({ message, isLast, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const typeInfo = getMessageTypeLabel(message.type);
  const [localChartConfig, setLocalChartConfig] = useState<ChartConfig | null>(null);

  const activeChart = localChartConfig ?? message.chartConfig ?? null;
  const hasRows = message.rows && message.rows.length > 0;
  const thinkingText = message.thinking?.trim() ?? "";
  const hasThinking = thinkingText.length > 0;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[85%] ${isUser ? "bg-primary text-primary-foreground" : "bg-muted"} rounded-lg px-4 py-3`}>
        {/* Header with timestamp and type badge */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs opacity-70">
            {formatTimestamp(message.timestamp)}
          </span>
          {!isUser && message.type && (
            <Badge variant={typeInfo.variant} className={`text-[10px] px-1 py-0 ${typeInfo.className || ""}`}>
              {typeInfo.label}
            </Badge>
          )}
        </div>

        {/* Streaming status indicator */}
        {message.isStreaming && message.status && (
          <div className="flex items-center gap-2 mb-2 text-xs text-muted-foreground">
            <div className="animate-spin rounded-full h-3 w-3 border-2 border-primary border-t-transparent" />
            <span>{message.status}</span>
          </div>
        )}

        {/* Thinking block */}
        {hasThinking && (
          <details className="mb-2" open={message.isStreaming}>
            <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground transition-colors flex items-center gap-1 select-none">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 18 6-6-6-6" />
              </svg>
              <span>Raisonnement</span>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                {thinkingText.length} car.
              </span>
              {message.isStreaming && (
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
              )}
            </summary>
            <div className="mt-1 p-2 rounded border border-border bg-muted/30 text-xs text-muted-foreground whitespace-pre-wrap max-h-[200px] overflow-y-auto font-mono leading-relaxed">
              {thinkingText}
              {message.isStreaming && <span className="animate-pulse">|</span>}
            </div>
          </details>
        )}

        {/* Message content */}
        <div className="text-sm">
          {message.content ? (
            <MarkdownRenderer content={message.content} />
          ) : message.isStreaming ? (
            <span className="text-muted-foreground text-xs italic">En attente de la réponse…</span>
          ) : null}
          {message.isStreaming && message.content && (
            <span className="animate-pulse">|</span>
          )}
        </div>

        {/* Query display - collapsible */}
        {message.query && (
          <details className="mt-2 text-xs">
            <summary className="text-muted-foreground cursor-pointer hover:text-foreground transition-colors flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 18 6-6-6-6"/>
              </svg>
              {message.queryType === "sql" ? "SQL" : "Requête"}
            </summary>
            <div className="mt-1 p-2 bg-muted/50 rounded font-mono text-[10px] overflow-x-auto">
              <code>{message.query}</code>
            </div>
          </details>
        )}

        {/* Results info */}
        {message.rowCount !== undefined && message.rowCount > 0 && (
          <div className="mt-2 text-xs opacity-70">
            {message.rowCount} ligne(s) retournée(s)
          </div>
        )}

        {/* Analysis info */}
        {message.analysisType && (
          <div className="mt-2 text-xs opacity-70">
            Analyse: {message.analysisType}
            {message.sampleSize && ` (sur ${message.sampleSize} échantillons)`}
          </div>
        )}

        {/* Chart: auto or manual */}
        {hasRows && activeChart && (
          <ChartRenderer data={message.rows!} config={activeChart} />
        )}

        {/* Export + chart config buttons */}
        {hasRows && (
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <ExportButtons data={message.rows!} />
            <ChartConfigDialog
              rows={message.rows!}
              initialConfig={activeChart}
              onApply={setLocalChartConfig}
            />
          </div>
        )}

        {/* Regenerate button for last assistant message */}
        {!isUser && isLast && onRegenerate && (
          <div className="mt-2 flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={onRegenerate}
              className="h-6 text-xs opacity-50 hover:opacity-100"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mr-1"
              >
                <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
                <path d="M21 3v5h-5" />
                <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
                <path d="M8 16H3v5" />
              </svg>
              Régénérer
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
