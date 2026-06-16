from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:
    raise SystemExit("psycopg is required to run this script")


def run_query(conn: Any, sql: str, params=()):
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    return rows


def main():
    database_url = os.environ.get("DATABASE_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not database_url:
        print("Usage: verify_import_v3.py <DATABASE_URL> or set DATABASE_URL env var")
        raise SystemExit(1)

    with psycopg.connect(database_url) as conn:
        print("-- dice_presets --")
        presets = run_query(
            conn, 
            "SELECT id, en_preset_name, pokemon_id, dice1, dice2, dice3 FROM dice_presets WHERE en_preset_name LIKE %s ORDER BY en_preset_name", 
            ("Plakoro Starter Set %",)
        )
        print(json.dumps([
            {
                "id": str(r[0]), 
                "name": r[1], 
                "pokemon_id": r[2],
                "dice1": r[3],
                "dice2": r[4],
                "dice3": r[5]
            } for r in presets
        ], ensure_ascii=False, indent=2))

        if presets:
            pokemon_id = presets[0][2]
            print(f"\n-- pokemon_fixed_faces for pokemon_id {pokemon_id} --")
            fixed = run_query(
                conn, 
                "SELECT face_type_id, quantity FROM pokemon_fixed_faces WHERE pokemon_id = %s ORDER BY face_type_id", 
                (pokemon_id,)
            )
            print(json.dumps([{"face_type_id": r[0], "quantity": r[1]} for r in fixed], ensure_ascii=False, indent=2))

            print(f"\n-- pokemon_available_faces for pokemon_id {pokemon_id} --")
            available = run_query(
                conn, 
                "SELECT face_type_id, quantity FROM pokemon_available_faces WHERE pokemon_id = %s ORDER BY face_type_id", 
                (pokemon_id,)
            )
            print(json.dumps([{"face_type_id": r[0], "quantity": r[1]} for r in available], ensure_ascii=False, indent=2))
        else:
            print("No Plakoro presets found.")


if __name__ == '__main__':
    main()
