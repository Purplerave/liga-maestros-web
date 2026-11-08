import React from 'react';

export default function MatchCard({ match }) {
  const isLive = ["LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO"].includes(match.status);
  
  return (
    <div className={`relative overflow-hidden rounded-xl border p-4 transition-all duration-300 
      ${isLive 
        ? 'border-accent bg-accent/10 shadow-[0_0_15px_rgba(var(--accent-rgb),0.3)]' 
        : 'border-border bg-card'}`}>
      
      {isLive && (
        <div className="absolute top-0 right-0 flex items-center gap-2 bg-accent px-2 py-1 text-[10px] font-bold text-card uppercase tracking-tighter">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-card opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-card"></span>
          </span>
          En Vivo
        </div>
      )}

      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-1 items-center justify-end gap-3">
          <span className="text-sm font-medium opacity-90">{match.local}</span>
          <img src={match.logo_local} alt="" className="h-8 w-8 object-contain" />
        </div>

        <div className="flex flex-col items-center justify-center px-4">
          <div className="text-2xl font-black tabular-nums tracking-tighter">
            {match.marcador}
          </div>
          {isLive && (
            <div className="text-[10px] font-bold text-accent uppercase">
              {match.minuto_live}'
            </div>
          )}
        </div>

        <div className="flex flex-1 items-center justify-start gap-3">
          <img src={match.logo_visitante} alt="" className="h-8 w-8 object-contain" />
          <span className="text-sm font-medium opacity-90">{match.visitante}</span>
        </div>
      </div>
    </div>
  );
}
