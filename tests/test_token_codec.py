import time

from src.hosted.token_codec import TokenCodec


def test_round_trip_all_kinds():
    codec = TokenCodec("test-secret")
    for kind in ("client", "txn", "code", "access", "refresh"):
        blob = codec.encode(kind, {"value": kind, "n": 7}, ttl_seconds=60)
        payload = codec.decode(kind, blob)
        assert payload is not None
        assert payload["value"] == kind
        assert payload["n"] == 7
        assert payload["exp"] > time.time()


def test_tampered_blob_returns_none():
    codec = TokenCodec("test-secret")
    blob = codec.encode("access", {"value": 1}, 60)
    assert codec.decode("access", blob[:-4] + "AAAA") is None
    assert codec.decode("access", "not-a-blob") is None
    assert codec.decode("access", "") is None


def test_expired_blob_returns_none():
    codec = TokenCodec("test-secret")
    blob = codec.encode("access", {"value": 1}, ttl_seconds=-5)
    assert codec.decode("access", blob) is None


def test_kind_mismatch_rejected():
    # An access token must never be replayable as an authorization code (or any other kind).
    codec = TokenCodec("test-secret")
    blob = codec.encode("access", {"value": 1}, 60)
    assert codec.decode("code", blob) is None
    assert codec.decode("refresh", blob) is None


def test_different_secret_cannot_decode():
    blob = TokenCodec("secret-a").encode("access", {"value": 1}, 60)
    assert TokenCodec("secret-b").decode("access", blob) is None
