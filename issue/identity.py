import hashlib


def piece_id_for(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
