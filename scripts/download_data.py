"""Download public WANDS source files without mixing them with processed outputs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/wayfair/WANDS/main/"


def main():
    destination = ROOT / "data/raw"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {"downloaded_utc": datetime.now(timezone.utc).isoformat(), "files": []}
    for remote, local in [("dataset/product.csv", "product.csv"), ("dataset/query.csv", "query.csv"),
                          ("dataset/label.csv", "label.csv"), ("LICENSE", "WANDS_LICENSE")]:
        path = destination / local
        temporary = path.with_suffix(path.suffix + ".download")
        with urlopen(BASE + remote, timeout=120) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024*1024)
                if not chunk: break
                output.write(chunk)
        temporary.replace(path)
        manifest["files"].append({"url": BASE+remote, "file": local, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        print("Downloaded", local)
    (destination / "download_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
