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

    def execute(self):
        return FakeExecuteResult(self._data)


class FakeSupabaseClient:
    def __init__(self, data=None):
        self.query = FakeQuery(data or [])
        self.table_names = []

    def table(self, name):
        self.table_names.append(name)
        return self.query


def test_get_first_seen_records_returns_empty_dict_without_querying_when_no_job_ids():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.get_first_seen_records([])

    assert result == {}
    assert client.table_names == []


def test_get_first_seen_records_parses_rows():
    client = FakeSupabaseClient(
        data=[{"job_id": "job-1", "first_seen": "2026-07-03T10:00:00+00:00", "first_seen_playing": 2}]
    )
    repo = SupabaseSightingsRepository(client, place_id=42)

    result = repo.get_first_seen_records(["job-1", "job-2"])

    assert result == {
        "job-1": FirstSeenRecord(
            first_seen=datetime(2026, 7, 3, 10, 0, 0, tzinfo=timezone.utc), first_seen_playing=2
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
        )
    ]
    assert client.table_names == ["fisch_server_sightings"]
    assert ("eq", ("place_id", 42), {}) in client.query.calls


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
        }
    ]
    assert kwargs == {"on_conflict": "place_id,job_id"}


def test_upsert_sightings_does_nothing_for_empty_list():
    client = FakeSupabaseClient()
    repo = SupabaseSightingsRepository(client, place_id=42)

    repo.upsert_sightings([])

    assert client.table_names == []
