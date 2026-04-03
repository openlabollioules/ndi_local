"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ApiKeyDialog() {
  const [apiKey, setApiKey] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [hasKey, setHasKey] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("ndi_api_key");
    if (stored) {
      setApiKey(stored);
      setHasKey(true);
    }
  }, []);

  const handleSave = () => {
    if (apiKey.trim()) {
      localStorage.setItem("ndi_api_key", apiKey.trim());
      setHasKey(true);
      setIsOpen(false);
      window.location.reload(); // Recharger pour appliquer la nouvelle clé
    }
  };

  const handleClear = () => {
    localStorage.removeItem("ndi_api_key");
    setApiKey("");
    setHasKey(false);
    setIsOpen(false);
    window.location.reload();
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={hasKey ? "text-green-600" : "text-amber-600"}
        >
          {hasKey ? "🔑 Clé API configurée" : "⚠️ Clé API requise"}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Configuration de la clé API</DialogTitle>
          <DialogDescription>
            Entrez votre clé API pour accéder aux fonctionnalités protégées.
            La clé est stockée localement dans votre navigateur.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="api-key">Clé API (X-API-Key)</Label>
            <Input
              id="api-key"
              type="password"
              placeholder="sk-ndiv2-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
          {process.env.NEXT_PUBLIC_API_KEY && (
            <p className="text-xs text-muted-foreground">
              Clé par défaut configurée dans l&apos;environnement.
            </p>
          )}
        </div>
        <div className="flex justify-between">
          {hasKey && (
            <Button variant="destructive" size="sm" onClick={handleClear}>
              Supprimer
            </Button>
          )}
          <div className="flex gap-2 ml-auto">
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSave} disabled={!apiKey.trim()}>
              Enregistrer
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
