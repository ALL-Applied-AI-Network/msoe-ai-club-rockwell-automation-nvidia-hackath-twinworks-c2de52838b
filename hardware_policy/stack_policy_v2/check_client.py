import hashlib
import json
from pathlib import Path


def verify(client):
    client = Path(client).resolve()
    expected = json.loads(Path(__file__).with_name("client_revision.json").read_text())
    for name, digest in expected.items():
        path = client / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Client differs from reviewed source: {name}; preserve and inspect before continuing")
    return client
