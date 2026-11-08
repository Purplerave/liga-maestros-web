from liga_maestros.services import cache as cache_module
from liga_maestros.services.cache import CacheService


def test_memory_cache_expires_entries_and_returns_isolated_values(monkeypatch):
    monkeypatch.setattr(cache_module, "redis_module", None)
    clock = [100.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: clock[0])
    cache = CacheService(default_ttl=5, max_entries=2)

    source = {"items": [1, 2]}
    cache.set("fixture", source)
    source["items"].append(3)
    retrieved = cache.get("fixture")
    retrieved["items"].append(4)

    assert cache.get("fixture") == {"items": [1, 2]}
    clock[0] = 106.0
    assert cache.get("fixture") is None


def test_memory_cache_evicts_least_recently_used_entry(monkeypatch):
    monkeypatch.setattr(cache_module, "redis_module", None)
    cache = CacheService(default_ttl=30, max_entries=2)
    cache.set("first", 1)
    cache.set("second", 2)
    assert cache.get("first") == 1
    cache.set("third", 3)

    assert cache.get("first") == 1
    assert cache.get("second") is None
    assert cache.get("third") == 3
