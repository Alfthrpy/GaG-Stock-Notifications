import { memo } from "react";
import { formatCountdown } from "../format";
import type { ServerPrediction } from "../types";

interface RowProps {
  server: ServerPrediction;
  elapsedSeconds: number;
  isJoined: boolean;
  onRowClick: (jobId: string) => void;
  onJoinClick: (jobId: string) => void;
}

const ServerRow = memo(function ServerRow({ server, elapsedSeconds, isJoined, onRowClick, onJoinClick }: RowProps) {
  const liveAge = server.age_seconds + elapsedSeconds;
  const liveUntilStart = Math.max(0, server.seconds_until_start - elapsedSeconds);
  const liveUntilEnd = Math.max(0, server.seconds_until_end - elapsedSeconds);

  const rowClasses = [server.is_active ? "row-active" : "", isJoined ? "row-joined" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <tr className={rowClasses || undefined} onClick={() => onRowClick(server.job_id)}>
      <td className="job-id-cell">
        {isJoined && (
          <span className="joined-marker" title="Server yang lo klik Join">
            📍{" "}
          </span>
        )}
        {server.job_id}
      </td>
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
        <a
          href={server.join_link}
          className="join-link"
          onClick={(event) => {
            event.stopPropagation();
            onJoinClick(server.job_id);
          }}
        >
          🎮 Join
        </a>
      </td>
    </tr>
  );
});

interface Props {
  servers: ServerPrediction[];
  elapsedSeconds: number;
  joinedIds: Set<string>;
  onRowClick: (jobId: string) => void;
  onJoinClick: (jobId: string) => void;
}

export function ServerTable({ servers, elapsedSeconds, joinedIds, onRowClick, onJoinClick }: Props) {
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
            <ServerRow
              key={server.job_id}
              server={server}
              elapsedSeconds={elapsedSeconds}
              isJoined={joinedIds.has(server.job_id)}
              onRowClick={onRowClick}
              onJoinClick={onJoinClick}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
