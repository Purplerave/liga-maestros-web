import Image from "next/image";

import type { MatchPayload } from "@/types/api";

type MatchCardProps = {
  match: MatchPayload;
};

const LIVE_STATUSES = new Set(["LIVE", "IN PLAY", "HT", "HALF TIME BREAK", "EN JUEGO"]);

function TeamBadge({ name, logo }: { name: string; logo?: string }) {
  if (logo) {
    return <Image src={logo} alt={`${name} escudo`} width={32} height={32} unoptimized className="h-8 w-8 object-contain" />;
  }

  return (
    <span aria-hidden="true" className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 text-xs font-bold">
      {name.trim().charAt(0) || "?"}
    </span>
  );
}

export default function MatchCard({ match }: MatchCardProps) {
  const isLive = LIVE_STATUSES.has(match.status.toUpperCase());

  return (
    <article
      className={`relative overflow-hidden rounded-xl border p-4 transition-all duration-300 ${
        isLive
          ? "border-accent bg-accent/10 shadow-[0_0_15px_rgba(var(--accent-rgb),0.3)]"
          : "border-border bg-card"
      }`}
    >
      {isLive && (
        <div className="absolute right-0 top-0 flex items-center gap-2 bg-accent px-2 py-1 text-[10px] font-bold uppercase tracking-tighter text-card">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-card opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-card" />
          </span>
          En vivo
        </div>
      )}

      <div className="flex items-center justify-between gap-4">
        <div className="flex flex-1 items-center justify-end gap-3">
          <span className="text-right text-sm font-medium opacity-90">{match.local}</span>
          <TeamBadge name={match.local} logo={match.logo_local} />
        </div>

        <div className="flex flex-col items-center justify-center px-4">
          <div className="text-2xl font-black tabular-nums tracking-tighter">{match.marcador}</div>
          {isLive && match.minuto_live && (
            <div className="text-[10px] font-bold uppercase text-accent">
              {match.minuto_live}&apos;
            </div>
          )}
        </div>

        <div className="flex flex-1 items-center justify-start gap-3">
          <TeamBadge name={match.visitante} logo={match.logo_visitante} />
          <span className="text-sm font-medium opacity-90">{match.visitante}</span>
        </div>
      </div>
    </article>
  );
}
