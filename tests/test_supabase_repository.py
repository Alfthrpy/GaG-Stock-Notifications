from datetime import datetime, timedelta, timezone

from fisch_tracker.supabase_repository import SupabaseSightingsRepository
from fisch_tracker.tracker import FirstSeenRecord, ServerSighting

T0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


class FakeExecuteResult:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    """Records the fluent-builder calls made on it and returns canned data."""

    def __init__(self, data):
        self._data = data
        self.calls: list[tuple[str, tuple, dict]] = []

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def eq(self, *args, **kwargs):
        self.calls.append(("eq", args, kwargs))
        return self

    def in_(self, *args, **kwargs):
        self.calls.append(("in_", args, kwargs))
        return self

    def order(self, *args, **kwargs):
        self.calls.append(("order", args, kwargs))
        return self

    def limit(self, *args, **kwargs):
        self.calls.append(("limit", args, kwargs))
        return self

    def upsert(self, *args, **kwargs):
        self.calls.append(("upsert", args, kwargs))
        return self

    def gte(self, *args, **kwargs):
        self.calls.append(("gte", args, kwargs))
        return self

    def lt(self, *args, **kwargs):
        self.calls.append(("lt", args, kwargs))
        return self

    def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))
        return self

    def range(self, *args, **kwargs):
        self.calls.append(("range", args, kwargs))
        return self

    def execute(self):
        return FakeExecuteResult(self._data)


class FakeSupabaseClient:
    def __init__(self, data=None, pages=None):
        """data= for the common single-response case (client.query holds
        the one FakeQuery built). pages= simulates real pagination: each
        .table() call consumes the next page and builds a fresh FakeQuery,
        recorded in client.queries so tests can inspect per-page calls."""
        self._pages = list(pages) if pages is not None else None
        self.queries: list[FakeQuery] = []
        self.table_names = []
        self.query = FakeQuery(data or []) if self._pages is None else None

    def table(self, name):
        self.table_names.append(name)
        if self._pages is not None:
            page_data = self._pages.pop(0) if self._pages else []
            query = FakeQuery(page_data)
            self.queries.append(query)
            self.query = query
            return query
        self.queries.append(self.query)
        return self.query


def test_get_first_seen_records_returns_empty_dict_without_querying_when_no_job_ids():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.get_first_seen_records([])

    assert result == {}
    assert client.table_names == []


def test_get_first_seen_records_parses_rows():
    client = FakeSupabaseClient(
        data=[
            {
                "job_id": "job-1",
                "first_seen": "2026-07-03T10:00:00+00:00",
                "first_seen_playing": 2,
                "age_confirmed": True,
            }
        ]
    )
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.get_first_seen_records(["job-1", "job-2"])

    assert result == {
        "job-1": FirstSeenRecord(
            first_seen=datetime(2026, 7, 3, 10, 0, 0, tzinfo=timezone.utc),
            first_seen_playing=2,
            age_confirmed=True,
        )
    }
    assert client.table_names == ["fisch_server_sightings"]
    assert ("eq", ("place_id", 42), {}) in client.query.calls
    assert ("in_", ("job_id", ["job-1", "job-2"]), {}) in client.query.calls


def test_get_epoch_returns_none_when_no_rows():
    client = FakeSupabaseClient(data=[])
    repo = SupabaseSightingsRepository(client, place_id=42)

    assert repo.get_epoch() is None


def test_get_epoch_returns_earliest_first_seen():
    client = FakeSupabaseClient(data=[{"first_seen": "2026-07-01T00:00:00+00:00"}])
    repo = SupabaseSightingsRepository(client, place_id=42)

    epoch = repo.get_epoch()

    assert epoch == datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert ("order", ("first_seen",), {}) in client.query.calls
    assert ("limit", (1,), {}) in client.query.calls


def test_list_sightings_parses_rows_into_server_sighting():
    client = FakeSupabaseClient(
        data=[
            {
                "job_id": "job-1",
                "first_seen": "2026-07-03T09:00:00+00:00",
                "first_seen_playing": 1,
                "last_seen": "2026-07-03T10:00:00+00:00",
                "playing": 5,
                "max_players": 20,
                "age_confirmed": True,
            }
        ]
    )
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.list_sightings()

    assert result == [
        ServerSighting(
            job_id="job-1",
            first_seen=datetime(2026, 7, 3, 9, 0, 0, tzinfo=timezone.utc),
            first_seen_playing=1,
            last_seen=datetime(2026, 7, 3, 10, 0, 0, tzinfo=timezone.utc),
            playing=5,
            max_players=20,
            age_confirmed=True,
        )
    ]
    assert client.table_names == ["fisch_server_sightings"]
    assert ("eq", ("place_id", 42), {}) in client.query.calls
    assert not any(c[0] == "gte" for c in client.query.calls)


def test_list_sightings_filters_by_since_when_given():
    client = FakeSupabaseClient(data=[])
    repo = SupabaseSightingsRepository(client, place_id=42)

    since = datetime(2026, 7, 3, 6, 0, 0, tzinfo=timezone.utc)
    repo.list_sightings(since=since)

    assert ("gte", ("last_seen", since.isoformat()), {}) in client.query.calls


def _row(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "first_seen": "2026-07-03T09:00:00+00:00",
        "first_seen_playing": 1,
        "last_seen": "2026-07-03T10:00:00+00:00",
        "playing": 1,
        "max_players": 20,
        "age_confirmed": False,
    }


def test_list_sightings_paginates_past_supabases_default_1000_row_cap():
    # Supabase/PostgREST caps a single response at 1000 rows by default --
    # without pagination, list_sightings would silently drop everything
    # past the first page once the table grows past that (confirmed live:
    # exactly this happened, a confirmed job_id vanished nondeterministically
    # once the sightings table crossed 1000 rows).
    page_size = SupabaseSightingsRepository.PAGE_SIZE
    full_page = [_row(f"job-{i}") for i in range(page_size)]
    partial_page = [_row(f"job-extra-{i}") for i in range(37)]
    client = FakeSupabaseClient(pages=[full_page, partial_page])
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.list_sightings()

    assert len(result) == page_size + 37
    assert len(client.queries) == 2
    assert ("range", (0, page_size - 1), {}) in client.queries[0].calls
    assert ("range", (page_size, 2 * page_size - 1), {}) in client.queries[1].calls


def test_list_sightings_stops_after_a_single_partial_page():
    client = FakeSupabaseClient(pages=[[_row("job-1"), _row("job-2")]])
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.list_sightings()

    assert len(result) == 2
    assert len(client.queries) == 1


def test_delete_stale_sightings_deletes_rows_older_than_given_time():
    client = FakeSupabaseClient(data=[])
    repo = SupabaseSightingsRepository(client, place_id=42)

    older_than = datetime(2026, 6, 30, 0, 0, 0, tzinfo=timezone.utc)
    repo.delete_stale_sightings(older_than=older_than)

    assert client.table_names == ["fisch_server_sightings"]
    assert ("delete", (), {}) in client.query.calls
    assert ("eq", ("place_id", 42), {}) in client.query.calls
    assert ("lt", ("last_seen", older_than.isoformat()), {}) in client.query.calls


def test_delete_sighting_deletes_a_single_job_id():
    client = FakeSupabaseClient(data=[])
    repo = SupabaseSightingsRepository(client, place_id=42)

    repo.delete_sighting("job-dead-1")

    assert client.table_names == ["fisch_server_sightings"]
    assert ("delete", (), {}) in client.query.calls
    assert ("eq", ("place_id", 42), {}) in client.query.calls
    assert ("eq", ("job_id", "job-dead-1"), {}) in client.query.calls


def test_upsert_sightings_sends_rows_with_on_conflict_place_id_job_id():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)
    sightings = [
        ServerSighting(
            job_id="job-1",
            first_seen=T0 - timedelta(hours=1),
            first_seen_playing=2,
            last_seen=T0,
            playing=3,
            max_players=8,
        )
    ]

    repo.upsert_sightings(sightings)

    upsert_call = next(c for c in client.query.calls if c[0] == "upsert")
    rows, kwargs = upsert_call[1][0], upsert_call[2]
    assert rows == [
        {
            "place_id": 42,
            "job_id": "job-1",
            "first_seen": (T0 - timedelta(hours=1)).isoformat(),
            "first_seen_playing": 2,
            "last_seen": T0.isoformat(),
            "playing": 3,
            "max_players": 8,
            "age_confirmed": False,
        }
    ]
    assert kwargs == {"on_conflict": "place_id,job_id"}


def test_upsert_sightings_does_nothing_for_empty_list():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)

    repo.upsert_sightings([])

    assert client.table_names == []


def test_confirm_age_upserts_first_seen_last_seen_and_age_confirmed_flag():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)

    repo.confirm_age("job-1", first_seen=T0 - timedelta(hours=2), confirmed_at=T0)

    upsert_call = next(c for c in client.query.calls if c[0] == "upsert")
    row, kwargs = upsert_call[1][0], upsert_call[2]
    assert row == {
        "place_id": 42,
        "job_id": "job-1",
        "first_seen": (T0 - timedelta(hours=2)).isoformat(),
        "last_seen": T0.isoformat(),
        "age_confirmed": True,
    }
    # first_seen_playing/playing/max_players are intentionally omitted (a
    # regular sweep fills those in); default_to_null=False makes postgrest
    # fall back to the columns' SQL defaults instead of sending NULL and
    # violating their NOT NULL constraint if this job_id is brand new.
    assert kwargs == {"on_conflict": "place_id,job_id", "default_to_null": False}
