"""Fetch public, original ESCI data. Raw files are excluded from the repository."""
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]


def main():
    raw=ROOT/"data/esci/raw"; raw.mkdir(parents=True,exist_ok=True)
    base="https://media.githubusercontent.com/media/amazon-science/esci-data/main/shopping_queries_dataset/"
    files=[(base+"shopping_queries_dataset_products.parquet",raw/"products.parquet"),
           (base+"shopping_queries_dataset_examples.parquet",raw/"examples.parquet")]
    for url,destination in files:
        temporary=destination.with_suffix(".download")
        print("Downloading",destination.name,flush=True)
        with urlopen(url,timeout=180) as response, temporary.open("wb") as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                output.write(chunk)
        temporary.replace(destination)
    print("Run python scripts/build_esci.py to regenerate shelves and observational analysis.")


if __name__=="__main__": main()
