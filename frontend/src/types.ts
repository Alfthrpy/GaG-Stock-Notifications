export interface ServerPrediction {
  job_id: string;
  playing: number;
  max_players: number;
  age_seconds: number;
  is_active: boolean;
  seconds_until_start: number;
  seconds_until_end: number;
  is_confirmed: boolean;
  join_link: string;
}

export interface ServersPayload {
  servers: ServerPrediction[];
  server_time: string;
  status: "ok" | "waiting_for_first_sweep";
}

export interface ConfirmAgeRequest {
  days: number;
  hours: number;
  minutes: number;
}
