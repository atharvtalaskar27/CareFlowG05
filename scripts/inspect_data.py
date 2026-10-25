from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.careflow.io import load_archive_tables, read_source_tables
from src.careflow.inventory import create_inventory, write_inventory


def main() -> None:
    with load_archive_tables() as archive:
        tables = read_source_tables(archive)
        archive_path = archive.filename
    inventory = create_inventory(tables)

    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = docs_dir / "source_data_inventory.md"
    write_inventory(inventory, inventory_path)

    print(f"Archive: {archive_path}")
    print(f"Compressed CSV tables inspected: {len(inventory['tables'])}")
    print(f"Source inventory written: {inventory_path}")
    for table, details in inventory["tables"].items():
        print(f"  {table}: {details['row_count']} rows")


if __name__ == "__main__":
    main()
