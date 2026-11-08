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
    <div className="flex h-screen items-center justify-center bg-black text-green-500 font-mono">
      <div className="animate-pulse uppercase tracking-widest">
        [ SYSTEM LOADING: SYNCHRONIZING NASA TELEMETRY... ]
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-black text-green-500 p-6 font-mono relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none opacity-10" 
           style={{ backgroundImage: 'linear-gradient(#00ff00 1px, transparent 1px), linear-gradient(90deg, #00ff00 1px, transparent 1px)', 
                    backgroundSize: '40px 40px' }}></div>

      <header className="relative z-10 mb-12 flex items-center justify-between border-b-2 border-green-500 pb-6">
        <div className="flex flex-col">
          <h1 className="text-4xl font-black uppercase tracking-tighter">
            MISSION CONTROL: <span className="bg-green-500 text-black px-2">LIGA MAESTROS</span>
          </h1>
          <p className="text-xs opacity-80 uppercase tracking-widest mt-2">
            Sector: Earth-Orbital • Signal: Stable • Jornada 1
          </p>
        </div>
        <div className="text-right font-bold">
          <div className="text-[10px] opacity-60 uppercase">System Status</div>
          <div className="text-sm animate-pulse">● NOMINAL</div>
        </div>
      </header>

      <main className="relative z-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-7xl mx-auto">
        {matches.map((match, idx) => (
          <MatchCard key={idx} match={match} />
        ))}
      </main>

      <footer className="relative z-10 mt-12 text-center text-[10px] opacity-40 uppercase tracking-widest">
        NASA Control Center - Internal Use Only - Unauthorized Access Prohibited
      </footer>
    </div>
  );
}
