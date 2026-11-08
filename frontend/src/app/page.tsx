import React, { useEffect, useState } from 'react';
import MatchCard from '@/components/MatchCard';

export default function JornadaPage() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchMatches() {
      try {
        const response = await fetch('http://127.0.0.1:5000/api/modern/jornada/1');
        const result = await response.json();
        if (result.status === 'success') {
          setMatches(result.data);
        }
      } catch (e) {
        console.error('Error fetching matches:', e);
      } finally {
        setLoading(false);
      }
    }
    fetchMatches();
  }, []);

  if (loading) return (
    <div className="flex h-screen items-center justify-center bg-zinc-950 text-white">
      <div className="animate-pulse text-yellow-500 font-black uppercase tracking-widest">Cargando Arena...</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 font-sans">
      <header className="mb-12 flex items-center justify-between border-b border-zinc-800 pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase italic tracking-tighter">
            Liga de <span className="text-yellow-500">Maestros</span>
          </h1>
          <p className="text-sm opacity-60 uppercase tracking-widest">Humanos vs IA • Jornada 1</p>
        </div}
        <div className="text-right">
          <div className="text-xs opacity-50 uppercase">Estado del Sistema</div>
          <div className="text-xs font-bold text-green-500">Sincronizado</div>
        </div}
      </header>

      <main className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-7xl mx-auto">
        {matches.map((match, idx) => (
          <MatchCard key={idx} match={match} />
        ))}
      </main>
    </div>
  );
}
