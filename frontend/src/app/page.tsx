"use client";

import { useEffect, useState } from "react";

import MatchCard from "@/components/MatchCard";
import type { ApiResponse, MatchPayload } from "@/types/api";

export default function JornadaPage() {
  const jornada = "1";
  const [matches, setMatches] = useState<MatchPayload[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchMatches() {
      try {
        const response = await fetch(`/api/modern/jornada/${jornada}`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`La API respondió con ${response.status}`);
        }

        const result = (await response.json()) as ApiResponse<MatchPayload[]>;
        if (result.status !== "success") {
          throw new Error(result.message);
        }
        setMatches(result.data);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "No se pudieron cargar los partidos.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void fetchMatches();
    return () => controller.abort();
  }, [jornada]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-white">
        <div className="animate-pulse font-black uppercase tracking-widest text-yellow-500">
          Cargando Arena...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 p-6 font-sans text-zinc-100">
      <header className="mb-12 flex items-center justify-between border-b border-zinc-800 pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Liga de <span className="text-yellow-500">Maestros</span>
          </h1>
          <p className="text-sm uppercase tracking-widest opacity-60">Humanos vs IA · Jornada {jornada}</p>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase opacity-50">Estado del sistema</div>
          <div className={`text-xs font-bold ${error ? "text-red-400" : "text-green-500"}`}>
            {error ? "Sin conexión" : "Sincronizado"}
          </div>
        </div>
      </header>

      {error && (
        <p role="alert" className="mx-auto mb-6 max-w-7xl rounded-lg border border-red-900 bg-red-950/50 p-4 text-sm text-red-200">
          No se pudieron cargar los partidos: {error}
        </p>
      )}

      <main className="mx-auto grid max-w-7xl grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {matches.map((match) => (
          <MatchCard key={match.id} match={match} />
        ))}
      </main>
    </div>
  );
}
