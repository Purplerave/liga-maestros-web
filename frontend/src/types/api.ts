export type ApiResponse<T> =
  | { status: "success"; data: T }
  | { status: "error"; message: string };

export type MatchPayload = {
  id: number | string;
  local: string;
  visitante: string;
  logo_local?: string;
  logo_visitante?: string;
  marcador: string;
  status: string;
  minuto_live?: string;
};

export type StandingEntry = {
  id: string;
  name: string;
  hits: number;
  points: number;
};
