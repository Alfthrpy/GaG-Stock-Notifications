interface Props {
  total: number;
  activeNow: number;
  confirmed: number;
}

export function StatsBar({ total, activeNow, confirmed }: Props) {
  return (
    <div className="stats-bar">
      <div className="stat-tile">
        <span className="stat-label">Total server</span>
        <span className="stat-value">{total}</span>
      </div>
      <div className="stat-tile stat-tile-active">
        <span className="stat-label">Aktif sekarang</span>
        <span className="stat-value">{activeNow}</span>
      </div>
      <div className="stat-tile">
        <span className="stat-label">Terkonfirmasi</span>
        <span className="stat-value">{confirmed}</span>
      </div>
    </div>
  );
}
