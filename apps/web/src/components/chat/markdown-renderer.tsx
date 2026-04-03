"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SmartTable, parseMarkdownTable } from "./smart-table";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // Check if content contains a markdown table
  const tableData = parseMarkdownTable(content);
  
  if (tableData) {
    // Split content: text before table, the table, text after table
    const lines = content.split('\n');
    const tableStartIdx = lines.findIndex(l => l.trim().startsWith('|'));
    const tableEndIdx = lines.slice(tableStartIdx).findIndex(l => !l.trim().startsWith('|'));
    const actualEndIdx = tableEndIdx === -1 ? lines.length : tableStartIdx + tableEndIdx;
    
    const beforeTable = lines.slice(0, tableStartIdx).join('\n');
    const afterTable = lines.slice(actualEndIdx).join('\n');
    
    return (
      <div className="text-sm">
        {beforeTable && (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {beforeTable}
          </ReactMarkdown>
        )}
        <SmartTable headers={tableData.headers} rows={tableData.rows} />
        {afterTable && (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {afterTable}
          </ReactMarkdown>
        )}
      </div>
    );
  }

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}

const components = {
  p: ({ children }: { children?: React.ReactNode }) => (
    <div className="mb-2 last:mb-0">{children}</div>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{children}</strong>
  ),
  em: ({ children }: { children?: React.ReactNode }) => (
    <em className="italic">{children}</em>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>
  ),
  li: ({ children }: { children?: React.ReactNode }) => (
    <li className="ml-2">{children}</li>
  ),
  pre: ({ children }: { children?: React.ReactNode }) => (
    <pre className="p-3 bg-muted rounded-lg overflow-x-auto my-2">{children}</pre>
  ),
  code: ({ children, className }: { children?: React.ReactNode; className?: string }) => {
    const isBlock = Boolean(className);
    return isBlock ? (
      <code className="text-xs font-mono">{children}</code>
    ) : (
      <code className="px-1.5 py-0.5 bg-muted rounded text-xs font-mono">{children}</code>
    );
  },
};
