"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import {
  Position,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// Import dynamique de React Flow pour éviter les problèmes SSR
const ReactFlow = dynamic(
  () => import("@xyflow/react").then((mod) => mod.ReactFlow),
  { ssr: false }
);
const Background = dynamic(
  () => import("@xyflow/react").then((mod) => mod.Background),
  { ssr: false }
);
const Controls = dynamic(
  () => import("@xyflow/react").then((mod) => mod.Controls),
  { ssr: false }
);
const MiniMap = dynamic(
  () => import("@xyflow/react").then((mod) => mod.MiniMap),
  { ssr: false }
);

// Import du CSS
import "@xyflow/react/dist/style.css";

interface ColumnInfo {
  name: string;
  type: string;
}

interface TableSchema {
  name: string;
  columns: ColumnInfo[];
}

interface Relation {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relation_type: string;
}

interface ERDiagramProps {
  tables: TableSchema[];
  relations: Relation[];
}

// Layout algorithm simple : grille circulaire
function calculateNodePositions(
  tables: TableSchema[],
  radius = 200,
  centerX = 400,
  centerY = 300
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();

  tables.forEach((table, index) => {
    const angle = (2 * Math.PI * index) / tables.length;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    positions.set(table.name, { x, y });
  });

  return positions;
}

function createNodes(
  tables: TableSchema[],
  nodePositions: Map<string, { x: number; y: number }>
): Node[] {
  return tables.map((table) => {
    const position = nodePositions.get(table.name) ?? { x: 0, y: 0 };
    return {
      id: table.name,
      type: "default",
      position,
      data: {
        label: (
          <div className="space-y-1">
            <div className="font-semibold text-sm border-b border-border pb-1">
              {table.name}
            </div>
            <div className="space-y-0.5 text-xs text-muted-foreground">
              {table.columns.map((col) => (
                <div key={col.name} className="px-1 flex justify-between gap-2">
                  <span>{col.name}</span>
                  <span className="text-muted-foreground/60 font-mono text-[10px]">
                    {col.type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ),
      },
      style: {
        background: "hsl(var(--card))",
        border: "1px solid hsl(var(--border))",
        borderRadius: "8px",
        padding: "8px",
        minWidth: "150px",
        color: "hsl(var(--foreground))",
      },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });
}

function createEdges(relations: Relation[]): Edge[] {
  return relations.map((rel, index) => ({
    id: `edge-${rel.from_table}-${rel.to_table}-${index}`,
    source: rel.from_table,
    target: rel.to_table,
    label: `${rel.from_column} → ${rel.to_column}`,
    markerEnd: {
      type: MarkerType.ArrowClosed,
    },
    style: {
      stroke: "hsl(var(--primary))",
      strokeWidth: 2,
    },
    labelStyle: {
      fill: "hsl(var(--muted-foreground))",
      fontSize: "10px",
    },
    labelBgStyle: {
      fill: "hsl(var(--background))",
    },
  }));
}

function ERDiagramContent({
  tables,
  relations,
  isFullscreen = false,
}: ERDiagramProps & { isFullscreen?: boolean }) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const nodePositions = useMemo(
    () =>
      calculateNodePositions(
        tables,
        isFullscreen ? 350 : 200,
        isFullscreen ? 600 : 400,
        isFullscreen ? 400 : 300
      ),
    [tables, isFullscreen]
  );

  useEffect(() => {
    setNodes(createNodes(tables, nodePositions));
  }, [tables, nodePositions]);

  useEffect(() => {
    setEdges(createEdges(relations));
  }, [relations]);

  if (typeof window === "undefined") {
    return <div className="h-full w-full flex items-center justify-center text-muted-foreground">Chargement...</div>;
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={(changes) => {
        setNodes((nds) => {
          const updatedNodes = [...nds];
          changes.forEach((change) => {
            if (change.type === "position" && change.position) {
              const nodeIndex = updatedNodes.findIndex((n) => n.id === change.id);
              if (nodeIndex !== -1) {
                updatedNodes[nodeIndex] = {
                  ...updatedNodes[nodeIndex],
                  position: change.position,
                };
              }
            }
          });
          return updatedNodes;
        });
      }}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      nodesDraggable
      nodesConnectable={false}
      elementsSelectable
    >
      <Background color="hsl(var(--muted))" gap={16} />
      <Controls />
      <MiniMap
        nodeColor="hsl(var(--primary))"
        maskColor="hsl(var(--background) / 0.8)"
        style={{
          backgroundColor: "hsl(var(--card))",
        }}
      />
    </ReactFlow>
  );
}

export function ERDiagram({ tables, relations }: ERDiagramProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="h-[600px] w-full rounded-lg border border-border bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Chargement du diagramme...</p>
      </div>
    );
  }

  return (
    <>
      <div className="relative">
        <div className="h-[600px] w-full rounded-lg border border-border bg-background">
          <ERDiagramContent tables={tables} relations={relations} />
        </div>
        <Button
          variant="outline"
          size="sm"
          className="absolute top-3 right-3 z-10"
          onClick={() => setIsFullscreen(true)}
        >
          <svg
            className="h-4 w-4 mr-1.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
            />
          </svg>
          Plein écran
        </Button>
      </div>

      <Dialog open={isFullscreen} onOpenChange={setIsFullscreen}>
        <DialogContent className="max-w-[95vw] w-[95vw] h-[90vh] max-h-[90vh] p-0">
          <DialogHeader className="p-4 pb-0">
            <DialogTitle>Diagramme ER</DialogTitle>
          </DialogHeader>
          <div className="flex-1 h-[calc(90vh-60px)] w-full">
            <ERDiagramContent
              tables={tables}
              relations={relations}
              isFullscreen
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
