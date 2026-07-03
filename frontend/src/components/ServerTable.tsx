import { formatCountdown } from "../format";
import type { ServerPrediction } from "../types";

interface Props {
  servers: ServerPrediction[];
  elapsedSeconds: number;
  onRowClick: (jobId: string) => void;
}

export function ServerTable({ servers, elapsedSeconds, onRowClick }: Props) {
  if (servers.length === 0) {
    return <p className="empty-state">Belum ada server yang reliable, coba lagi nanti.</p>;
  }

  return (
    <table className="server-table">
      <thead>
        <tr>
          <th>Job ID</th>
          <th>Players</th>
          <th>Umur Server</th>
          <th>Status Spawn</th>
          <th>Status Umur</th>
          <th>Join</th>
        </tr>
      </thead>
      <tbody>
        {servers.map((server) => {
          const liveAge = server.age_seconds + elapsedSeconds;
          const liveUntilStart = Math.max(0, server.seconds_until_start - elapsedSeconds);
          const liveUntilEnd = Math.max(0, server.seconds_until_end - elapsedSeconds);

          return (
            <tr key={server.job_id} onClick={() => onRowClick(server.job_id)}>
              <td className="job-id-cell">{server.job_id}</td>
              <td>
                {server.playing}/{server.max_players}
              </td>
              <td>{formatCountdown(liveAge)}</td>
              <td>
                {server.is_active
                  ? `AKTIF (${formatCountdown(liveUntilEnd)} lagi tutup)`
                  : `${formatCountdown(liveUntilStart)} lagi`}
              </td>
              <td>
                <span className={server.is_confirmed ? "badge badge-confirmed" : "badge badge-guessed"}>
                  {server.is_confirmed ? "✅ Terkonfirmasi" : "🔮 Tebakan (belum pasti)"}
                </span>
              </td>
              <td>
                <a
                  href={server.join_link}
                  className="join-link"
                  onClick={(event) => event.stopPropagation()}
                >
                  🎮 Join
                </a>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
