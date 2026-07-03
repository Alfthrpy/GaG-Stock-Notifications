export type FilterChoice = "all" | "confirmed";

interface Props {
  value: FilterChoice;
  onChange: (value: FilterChoice) => void;
}

export function FilterToggle({ value, onChange }: Props) {
  return (
    <div className="filter-toggle" role="radiogroup" aria-label="Filter">
      <label>
        <input
          type="radio"
          name="filter"
          checked={value === "all"}
          onChange={() => onChange("all")}
        />
        Semua
      </label>
      <label>
        <input
          type="radio"
          name="filter"
          checked={value === "confirmed"}
          onChange={() => onChange("confirmed")}
        />
        Cuma Terkonfirmasi
      </label>
    </div>
  );
}
