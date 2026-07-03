export type FilterChoice = "all" | "confirmed";

interface Props {
  value: FilterChoice;
  onChange: (value: FilterChoice) => void;
}

export function FilterToggle({ value, onChange }: Props) {
  return (
    <div className="filter-toggle" role="tablist" aria-label="Filter">
      <button
        type="button"
        role="tab"
        aria-selected={value === "all"}
        className={value === "all" ? "filter-btn filter-btn-active" : "filter-btn"}
        onClick={() => onChange("all")}
      >
        Semua
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === "confirmed"}
        className={value === "confirmed" ? "filter-btn filter-btn-active" : "filter-btn"}
        onClick={() => onChange("confirmed")}
      >
        Cuma Terkonfirmasi
      </button>
    </div>
  );
}
