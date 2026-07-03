import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "fisch-joined-servers";
const MAX_TRACKED = 20;

function load(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

/** Remembers which job_ids the user clicked "Join" on, persisted across
 * reloads -- the roblox:// deep link can background/reload the tab, and
 * the whole point of this feature is not losing track of which server
 * that was. Bounded FIFO so it doesn't grow forever. */
export function useJoinedServers() {
  const [joinedIds, setJoinedIds] = useState<string[]>(load);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(joinedIds));
  }, [joinedIds]);

  const markJoined = useCallback((jobId: string) => {
    setJoinedIds((prev) => [jobId, ...prev.filter((id) => id !== jobId)].slice(0, MAX_TRACKED));
  }, []);

  const clearJoined = useCallback(() => setJoinedIds([]), []);

  return { joinedIds: new Set(joinedIds), markJoined, clearJoined };
}
