interface Props {
  page: number;
  pageCount: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageCount, totalItems, pageSize, onPageChange }: Props) {
  if (totalItems === 0) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);

  return (
    <div className="pagination">
      <span className="pagination-summary">
        {start}-{end} dari {totalItems} server
      </span>
      <div className="pagination-controls">
        <button
          type="button"
          className="pagination-btn"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          ‹ Sebelumnya
        </button>
        <span className="pagination-page">
          Halaman {page} / {pageCount}
        </span>
        <button
          type="button"
          className="pagination-btn"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= pageCount}
        >
          Selanjutnya ›
        </button>
      </div>
    </div>
  );
}
