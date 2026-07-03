import { useMemo, useState } from "react";
import { ConfirmAgeModal } from "./components/ConfirmAgeModal";
import { FilterToggle, type FilterChoice } from "./components/FilterToggle";
import { ServerTable } from "./components/ServerTable";
import { WS_URL } from "./config";
import { useNow } from "./hooks/useNow";
import { useServerFeed } from "./hooks/useServerFeed";
import "./App.css";

function App() {
  const { snapshot, connected } = useServerFeed(WS_URL);
  const now = useNow(1000);
  const [filter, setFilter] = useState<FilterChoice>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const elapsedSeconds = snapshot ? (now - snapshot.receivedAt) / 1000 : 0;

  const visibleServers = useMemo(() => {
    if (!snapshot) return [];
    return filter === "confirmed" ? snapshot.servers.filter((s) => s.is_confirmed) : snapshot.servers;
  }, [snapshot, filter]);

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

      <FilterToggle value={filter} onChange={setFilter} />

      {!snapshot ? (
        <p className="empty-state">Nunggu data dari server...</p>
      ) : snapshot.status === "waiting_for_first_sweep" ? (
        <p className="empty-state">Belum ada data, menunggu sweep pertama...</p>
      ) : (
        <ServerTable servers={visibleServers} elapsedSeconds={elapsedSeconds} onRowClick={setSelectedJobId} />
      )}

      {selectedJobId && (
        <ConfirmAgeModal jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
      )}
    </div>
  );
}

export default App;
