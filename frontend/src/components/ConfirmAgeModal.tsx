import { useState } from "react";
import { confirmAge } from "../api";

interface Props {
  jobId: string;
  onClose: () => void;
}

export function ConfirmAgeModal({ jobId, onClose }: Props) {
  const [days, setDays] = useState(0);
  const [hours, setHours] = useState(0);
  const [minutes, setMinutes] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (days * 86400 + hours * 3600 + minutes * 60 <= 0) {
      setError("Umur server harus lebih dari 0.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await confirmAge(jobId, { days, hours, minutes });
      setResult(`Makasih! Umur server ${jobId} udah dikonfirmasi jadi ${days}h ${hours}j ${minutes}m.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal nyimpen laporan.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h3>Lapor Umur Server</h3>
          <button className="modal-close" onClick={onClose} aria-label="Tutup">
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="modal-field">
            Job ID
            <input type="text" value={jobId} readOnly />
          </label>

          <div className="modal-row">
            <label className="modal-field">
              Hari
              <input
                type="number"
                min={0}
                value={days}
                onChange={(e) => setDays(Math.max(0, Number(e.target.value)))}
              />
            </label>
            <label className="modal-field">
              Jam
              <input
                type="number"
                min={0}
                max={23}
                value={hours}
                onChange={(e) => setHours(Math.max(0, Math.min(23, Number(e.target.value))))}
              />
            </label>
            <label className="modal-field">
              Menit
              <input
                type="number"
                min={0}
                max={59}
                value={minutes}
                onChange={(e) => setMinutes(Math.max(0, Math.min(59, Number(e.target.value))))}
              />
            </label>
          </div>

          <button type="submit" className="modal-submit" disabled={submitting}>
            {submitting ? "Ngirim..." : "Kirim Laporan"}
          </button>
        </form>

        {result && <p className="modal-result modal-result-ok">{result}</p>}
        {error && <p className="modal-result modal-result-error">{error}</p>}
      </div>
    </div>
  );
}
