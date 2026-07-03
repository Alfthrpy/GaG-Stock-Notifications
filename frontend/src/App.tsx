import { useEffect, useMemo, useState } from "react";
import { ConfirmAgeModal } from "./components/ConfirmAgeModal";
import { FilterToggle, type FilterChoice } from "./components/FilterToggle";
import { Pagination } from "./components/Pagination";
import { ServerTable } from "./components/ServerTable";
import { StatsBar } from "./components/StatsBar";
import { WS_URL } from "./config";
import { useJoinedServers } from "./hooks/useJoinedServers";
import { useNow } from "./hooks/useNow";
import { useServerFeed } from "./hooks/useServerFeed";
import "./App.css";

const PAGE_SIZE = 25;

function App() {
  const { snapshot, connected } = useServerFeed(WS_URL);
  const now = useNow(1000);
  const [filter, setFilter] = useState<FilterChoice>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const { joinedIds, markJoined, clearJoined } = useJoinedServers();

  const elapsedSeconds = snapshot ? (now - snapshot.receivedAt) / 1000 : 0;

  const visibleServers = useMemo(() => {
    if (!snapshot) return [];
    return filter === "confirmed" ? snapshot.servers.filter((s) => s.is_confirmed) : snapshot.servers;
  }, [snapshot, filter]);

  const pageCount = Math.max(1, Math.ceil(visibleServers.length / PAGE_SIZE));

  useEffect(() => {
    setPage(1);
  }, [filter]);

  useEffect(() => {
    if (page > pageCount) setPage(pageCount);
  }, [page, pageCount]);

  const pagedServers = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return visibleServers.slice(start, start + PAGE_SIZE);
  }, [visibleServers, page]);

  const stats = useMemo(
    () => ({
      total: snapshot?.servers.length ?? 0,
      activeNow: snapshot?.servers.filter((s) => s.is_active).length ?? 0,
      confirmed: snapshot?.servers.filter((s) => s.is_confirmed).length ?? 0,
    }),
    [snapshot],
  );

  return (
    <div className="app">
      <header>
        <h1>Fisch Sunken Treasure Tracker</h1>
        <p className="subtitle">
          Server diurutkan berdasarkan seberapa dekat window Sunken Treasure (aktif duluan, lalu yang
          paling deket mulai). Kolom <strong>Status Umur</strong> nunjukkin apakah umur server itu udah
          dikonfirmasi manual (akurat) atau masih tebakan (bisa meleset). Klik <strong>Join</strong> buat
          langsung masuk ke server itu, atau klik baris mana aja buat lapor umur asli yang lo liat di UI
          Fisch.
        </p>
        <span className={connected ? "ws-status ws-status-ok" : "ws-status ws-status-down"}>
          {connected ? "● Terhubung" : "○ Terputus, nyambung ulang..."}
        </span>
      </header>

      {snapshot?.status === "ok" && <StatsBar {...stats} />}

      <div className="toolbar">
        <FilterToggle value={filter} onChange={setFilter} />
        {joinedIds.size > 0 && (
          <button type="button" className="clear-joined-btn" onClick={clearJoined}>
            Hapus tanda 📍 ({joinedIds.size})
          </button>
        )}
      </div>

      {!snapshot ? (
        <p className="empty-state">Nunggu data dari server...</p>
      ) : snapshot.status === "waiting_for_first_sweep" ? (
        <p className="empty-state">Belum ada data, menunggu sweep pertama...</p>
      ) : (
        <>
          <ServerTable
            servers={pagedServers}
            elapsedSeconds={elapsedSeconds}
            joinedIds={joinedIds}
            onRowClick={setSelectedJobId}
            onJoinClick={markJoined}
          />
          <Pagination
            page={page}
            pageCount={pageCount}
            totalItems={visibleServers.length}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}

      {selectedJobId && (
        <ConfirmAgeModal jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
      )}
    </div>
  );
}

export default App;
