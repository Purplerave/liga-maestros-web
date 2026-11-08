"use client";

import { useEffect, useState } from "react";

import type { ApiResponse, StandingEntry } from "@/types/api";

export default function StandingsPage() {
  const [standings, setStandings] = useState<StandingEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchStandings() {
      try {
        const response = await fetch("/api/modern/standings/?jornada=1", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`La API respondió con ${response.status}`);
        }

        const result = (await response.json()) as ApiResponse<StandingEntry[]>;
        if (result.status !== "success") {
          throw new Error(result.message);
        }
        setStandings(result.data);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "No se pudo cargar la clasificación.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void fetchStandings();
    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-white">
        <div className="animate-pulse font-black uppercase tracking-widest text-yellow-500">
          Sincronizando ranking...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 p-6 font-sans text-zinc-100">
      <header className="mx-auto mb-12 flex max-w-4xl items-center justify-between border-b border-zinc-800 pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Ranking de <span className="text-yellow-500">Maestros</span>
          </h1>
          <p className="text-sm uppercase tracking-widest opacity-60">Clasificación global · Temporada 2026</p>
        </div>
      </header>

      {error && (
        <p role="alert" className="mx-auto mb-6 max-w-4xl rounded-lg border border-red-900 bg-red-950/50 p-4 text-sm text-red-200">
          No se pudo cargar la clasificación: {error}
        </p>
      )}

      <div className="mx-auto max-w-4xl overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="bg-zinc-800/50 text-xs uppercase tracking-widest text-zinc-400">
              <th scope="col" className="p-4 font-medium">Pos</th>
              <th scope="col" className="p-4 font-medium">Jugador</th>
              <th scope="col" className="p-4 text-center font-medium">Aciertos</th>
              <th scope="col" className="p-4 text-right font-medium">Puntos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {standings.length > 0 ? (
              standings.map((player, index) => (
                <tr key={player.id} className="group transition-colors hover:bg-zinc-800/30">
                  <td className="p-4 font-black text-zinc-500 transition-colors group-hover:text-yellow-500">
                    {index + 1}
                  </td>
                  <td className="p-4 font-bold">{player.name || "Desconocido"}</td>
                  <td className="p-4 text-center tabular-nums">{player.hits}</td>
                  <td className="p-4 text-right font-black tabular-nums text-yellow-500">{player.points}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="p-12 text-center italic text-zinc-500">
                  No hay datos disponibles en este momento.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
