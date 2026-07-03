import { memo } from "react";
import { formatCountdown } from "../format";
import type { ServerPrediction } from "../types";

interface RowProps {
  server: ServerPrediction;
  elapsedSeconds: number;
  onRowClick: (jobId: string) => void;
}

const ServerRow = memo(function ServerRow({ server, elapsedSeconds, onRowClick }: RowProps) {
  const liveAge = server.age_seconds + elapsedSeconds;
  const liveUntilStart = Math.max(0, server.seconds_until_start - elapsedSeconds);
  const liveUntilEnd = Math.max(0, server.seconds_until_end - elapsedSeconds);

  return (
    <tr
      className={server.is_active ? "row-active" : undefined}
      onClick={() => onRowClick(server.job_id)}
    >
      <td className="job-id-cell">{server.job_id}</td>
      <td className="num-cell">
        {server.playing}/{server.max_players}
      </td>
      <td className="num-cell">{formatCountdown(liveAge)}</td>
      <td className="num-cell">
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
        <a href={server.join_link} className="join-link" onClick={(event) => event.stopPropagation()}>
          🎮 Join
        </a>
      </td>
    </tr>
  );
});

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
    <div className="server-table-wrap">
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
          {servers.map((server) => (
            <ServerRow key={server.job_id} server={server} elapsedSeconds={elapsedSeconds} onRowClick={onRowClick} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
