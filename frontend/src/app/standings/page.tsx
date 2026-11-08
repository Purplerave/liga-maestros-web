import React, { useEffect, useState } from 'react';

export default function StandingsPage() {
  const [standings, setStandings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStandings() {
      try {
        const response = await fetch('http://127.0.0.1:5000/api/modern/standings/');
        const result = await response.json();
        if (result.status === 'success') {
          setStandings(result.data);
        }
      } catch (e) {
        console.error('Error fetching standings:', e);
      } finally {
        setLoading(false);
      }
    }
    fetchStandings();
  }, []);

  if (loading) return (
    <div className="flex h-screen items-center justify-center bg-zinc-950 text-white">
      <div className="animate-pulse text-yellow-500 font-black uppercase tracking-widest">Sincronizando Ranking...</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 font-sans">
      <header className="mb-12 flex items-center justify-between border-b border-zinc-800 pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Ranking de <span className="text-yellow-500">Maestros</span>
          </h1>
          <p className="text-sm opacity-60 uppercase tracking-widest">Clasificación Global • Temporada 2026</p>
        </div>
      </header>

      <div className="max-w-4xl mx-auto overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/50 backdrop-blur-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-zinc-800/50 text-xs uppercase tracking-widest text-zinc-400">
              <th className="p-4 font-medium">Pos</th>
              <th className="p-4 font-medium">Jugador</th>
              <th className="p-4 font-medium text-center">Aciertos</th>
              <th className="p-4 font-medium text-right">Puntos</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {standings.length > 0 ? (
              standings.map((player, idx) => (
                <tr key={idx} className="hover:bg-zinc-800/30 transition-colors group">
                  <td className="p-4 font-black text-zinc-500 group-hover:text-yellow-500 transition-colors">
                    {idx + 1}
                  </td>
                  <td className="p-4 font-bold">{player.name || 'Desconocido'}</td>
                  <td className="p-4 text-center tabular-nums">{player.hits || 0}</td>
                  <td className="p-4 text-right font-black tabular-nums text-yellow-500">
                    {player.points || 0}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={4} className="p-12 text-center text-zinc-500 italic">
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
