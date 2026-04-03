"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  generateSkill,
  injectSkill,
  getActiveSkill,
  deactivateSkill,
  refineSkill,
  regenerateSkill,
  type SkillData,
} from "@/lib/api";

export function SkillManager() {
  const [userInput, setUserInput] = useState("");
  const [skillContent, setSkillContent] = useState<string | null>(null);
  const [skillName, setSkillName] = useState<string>("");
  const [skillSource, setSkillSource] = useState<string>("");
  const [isActive, setIsActive] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [injecting, setInjecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  type RefinePhase = "idle" | "loading" | "answering" | "regenerating";
  const [refinePhase, setRefinePhase] = useState<RefinePhase>("idle");
  const [refineQuestions, setRefineQuestions] = useState<string[]>([]);
  const [refineAnswers, setRefineAnswers] = useState<string[]>([]);
  const [originalInput, setOriginalInput] = useState<string>("");

  const clearMessages = () => { setError(null); setSuccess(null); };

  const loadActiveSkill = useCallback(async () => {
    try {
      const data = await getActiveSkill();
      if (data.active && data.skill) {
        setSkillContent(data.skill.content);
        setSkillName(data.skill.name);
        setSkillSource(data.skill.source);
        setIsActive(true);
      } else {
        setIsActive(false);
      }
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => { void loadActiveSkill(); }, [loadActiveSkill]);

  const handleGenerate = async () => {
    if (!userInput.trim() || userInput.trim().length < 10) {
      setError("Le contexte métier doit faire au moins 10 caractères.");
      return;
    }
    clearMessages();
    setGenerating(true);
    setRefinePhase("idle");
    setRefineQuestions([]);
    setRefineAnswers([]);
    try {
      setOriginalInput(userInput);
      const result: SkillData = await generateSkill(userInput);
      setSkillContent(result.content);
      setSkillName(result.name);
      setSkillSource(result.source);
      setIsActive(result.active);
      setSuccess("Skill généré et injecté dans la session. Vous pouvez le raffiner ci-dessous.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de la génération.");
    } finally {
      setGenerating(false);
    }
  };

  const handleExport = () => {
    if (!skillContent) return;
    const now = new Date().toISOString().slice(0, 10);
    const filename = `skill_${skillName || "custom"}_${now}.md`;
    const blob = new Blob([skillContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const processImportedFile = async (file: File) => {
    if (!file.name.endsWith(".md")) {
      setError("Seuls les fichiers .md sont acceptés.");
      return;
    }
    clearMessages();
    setInjecting(true);
    try {
      const text = await file.text();
      if (text.trim().length < 10) {
        setError("Le fichier est trop court.");
        return;
      }
      const name = file.name.replace(/\.md$/, "").replace(/^skill_/, "");
      const result = await injectSkill(name, text);
      setSkillContent(result.content);
      setSkillName(result.name);
      setSkillSource(result.source);
      setIsActive(result.active);
      setSuccess(`Skill "${result.name}" importé et injecté.`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de l'import.");
    } finally {
      setInjecting(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void processImportedFile(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void processImportedFile(file);
  };

  const handleDeactivate = async () => {
    clearMessages();
    try {
      await deactivateSkill();
      setIsActive(false);
      setSkillContent(null);
      setSkillName("");
      setSkillSource("");
      setSuccess("Skill désactivé.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur.");
    }
  };

  const handleRefine = async () => {
    if (!skillContent) return;
    clearMessages();
    setRefinePhase("loading");
    try {
      const { questions } = await refineSkill(skillContent);
      setRefineQuestions(questions);
      setRefineAnswers(new Array(questions.length).fill(""));
      setRefinePhase("answering");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de l'analyse.");
      setRefinePhase("idle");
    }
  };

  const handleRegenerate = async () => {
    if (!skillContent || !originalInput) return;
    const refinements = refineQuestions
      .map((q, i) => ({ question: q, answer: refineAnswers[i]?.trim() || "" }))
      .filter((r) => r.answer.length > 0);

    if (refinements.length === 0) {
      setError("Répondez à au moins une question pour raffiner le skill.");
      return;
    }

    clearMessages();
    setRefinePhase("regenerating");
    try {
      const result: SkillData = await regenerateSkill(
        originalInput,
        skillContent,
        refinements,
        skillName || undefined,
      );
      setSkillContent(result.content);
      setSkillName(result.name);
      setSkillSource(result.source);
      setIsActive(result.active);
      setRefinePhase("idle");
      setRefineQuestions([]);
      setRefineAnswers([]);
      setSuccess("Skill enrichi avec vos précisions et réinjecté.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erreur lors de la régénération.");
      setRefinePhase("answering");
    }
  };

  const updateAnswer = (index: number, value: string) => {
    setRefineAnswers((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  };

  const canRefine = isActive && skillContent && originalInput && refinePhase === "idle";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left column — Generate + Import */}
      <div className="flex flex-col gap-6">
        {/* Generate */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Générer un Skill
            </CardTitle>
            <CardDescription>
              Décrivez votre contexte métier, règles ou données brutes. L&apos;agent les transformera en un skill structuré.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <Textarea
              placeholder="Ex: Dans notre chantier naval, les aléas sont classés par motif (Main d'Oeuvre, Matériel, Management). Chaque OT a un nombre d'heures d'aléas. Les motifs les plus fréquents sont..."
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              rows={8}
              className="resize-y"
            />
            <Button
              onClick={handleGenerate}
              disabled={generating || !userInput.trim()}
              className="w-full"
            >
              {generating ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full" />
                  Génération en cours…
                </span>
              ) : (
                "Générer Skill"
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Import */}
        <Card>
          <CardHeader>
            <CardTitle>Importer un Skill</CardTitle>
            <CardDescription>
              Glissez-déposez un fichier .md ou sélectionnez-le pour le charger dans la session.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              className={`
                border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
                transition-colors duration-200
                ${isDragOver
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-primary/50"
                }
              `}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".md"
                className="hidden"
                onChange={handleFileSelect}
              />
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <p className="text-sm font-medium">
                  {injecting ? "Import en cours…" : "Glissez un fichier .md ici"}
                </p>
                <p className="text-xs">ou cliquez pour sélectionner</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Right column — Preview + Status */}
      <div className="flex flex-col gap-6">
        {/* Status bar */}
        {(error || success) && (
          <div className={`rounded-lg px-4 py-3 text-sm ${error ? "bg-red-500/10 text-red-600 border border-red-500/20" : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"}`}>
            {error || success}
          </div>
        )}

        {/* Active skill indicator */}
        {isActive && (
          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="flex items-center justify-between py-4 px-6">
              <div className="flex items-center gap-3">
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-medium text-sm">Skill actif : {skillName}</span>
                <Badge variant="secondary">{skillSource}</Badge>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleExport} disabled={!skillContent}>
                  Exporter .md
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefine}
                  disabled={!canRefine}
                >
                  Raffiner
                </Button>
                <Button variant="outline" size="sm" onClick={handleDeactivate} className="text-red-600 hover:text-red-700">
                  Désactiver
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Refinement Q&A */}
        {refinePhase === "loading" && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardContent className="py-6 flex items-center justify-center gap-3">
              <span className="animate-spin h-4 w-4 border-2 border-amber-500 border-t-transparent rounded-full" />
              <span className="text-sm text-amber-700 dark:text-amber-400">Analyse du skill en cours…</span>
            </CardContent>
          </Card>
        )}

        {refinePhase === "answering" && (
          <Card className="border-amber-500/30">
            <CardHeader>
              <CardTitle className="text-base">Affiner le skill</CardTitle>
              <CardDescription>
                Répondez aux questions ci-dessous pour enrichir le skill. Les réponses vides seront ignorées.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {refineQuestions.map((q, i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <Label htmlFor={`refine-q-${i}`} className="text-sm font-medium">
                    {q}
                  </Label>
                  <Input
                    id={`refine-q-${i}`}
                    placeholder="Votre réponse…"
                    value={refineAnswers[i] ?? ""}
                    onChange={(e) => updateAnswer(i, e.target.value)}
                  />
                </div>
              ))}
              <div className="flex gap-2 pt-2">
                <Button onClick={handleRegenerate} className="flex-1">
                  Régénérer le skill
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => { setRefinePhase("idle"); setRefineQuestions([]); setRefineAnswers([]); }}
                >
                  Annuler
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {refinePhase === "regenerating" && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardContent className="py-6 flex items-center justify-center gap-3">
              <span className="animate-spin h-4 w-4 border-2 border-amber-500 border-t-transparent rounded-full" />
              <span className="text-sm text-amber-700 dark:text-amber-400">Régénération enrichie en cours…</span>
            </CardContent>
          </Card>
        )}

        {/* Preview */}
        <Card className="flex-1">
          <CardHeader>
            <CardTitle>Prévisualisation</CardTitle>
            <CardDescription>
              {skillContent
                ? `${skillContent.length} caractères · ~${Math.round(skillContent.length / 4)} tokens`
                : "Aucun skill chargé. Générez ou importez un skill."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {skillContent ? (
              <div className="prose prose-sm max-w-none dark:prose-invert overflow-y-auto max-h-[60vh] rounded-lg border border-border p-4 bg-muted/30">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {skillContent}
                </ReactMarkdown>
              </div>
            ) : (
              <div className="flex items-center justify-center h-48 text-muted-foreground text-sm border border-dashed border-border rounded-lg">
                Le skill apparaîtra ici
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
