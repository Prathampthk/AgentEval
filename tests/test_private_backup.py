import runpy
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken

encrypt = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/backup_private_server.py")
)["encrypt_snapshot"]


def test_encrypted_snapshot_round_trip_tamper_detection_and_preservation(tmp_path):
    key, other = Fernet.generate_key(), Fernet.generate_key()
    raw = b"explicitly synthetic database dump fixture"
    path = tmp_path / "dump.fernet"
    encrypted = encrypt(raw, key, path)
    assert raw not in encrypted and Fernet(key).decrypt(encrypted) == raw
    with pytest.raises(InvalidToken):
        Fernet(other).decrypt(encrypted)
    corrupted = bytearray(encrypted)
    corrupted[len(corrupted) // 2] ^= 1
    with pytest.raises(InvalidToken):
        Fernet(key).decrypt(bytes(corrupted))
    with pytest.raises(FileExistsError):
        encrypt(b"different", key, path)
    assert path.read_bytes() == encrypted
