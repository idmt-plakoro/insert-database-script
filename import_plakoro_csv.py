from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any


@dataclass(frozen=True)
class FaceEntry:
    faces: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class SetImport:
    set_name: str
    pokemon_name: str
    faces: list[FaceEntry]
    fixed_faces: list[FaceEntry]


def parse_plakoro_csv(csv_path: Path) -> list[SetImport]:
    sets: list[SetImport] = []
    current_set_name: str | None = None
    current_faces: list[FaceEntry] = []
    current_fixed_faces: list[FaceEntry] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)

        for raw_row in reader:
            row = [cell.strip() for cell in raw_row]
            if len(row) < 6:
                row.extend([""] * (6 - len(row)))

            (
                set_name,
                mix_1,
                mix_2,
                mix_count,
                single_face,
                single_count,
                fixed_face,
                fixed_count,
            ) = row[:8]

            if set_name:
                if current_set_name is not None:
                    sets.append(
                        SetImport(
                            set_name=current_set_name,
                            pokemon_name=extract_pokemon_name(current_set_name),
                            faces=current_faces,
                            fixed_faces=current_fixed_faces,
                        )
                    )
                current_set_name = set_name
                current_faces = []
                current_fixed_faces = []

            if current_set_name is None:
                continue

            if mix_1 and mix_2 and mix_count:
                current_faces.append(
                    FaceEntry(
                        faces=(mix_1, mix_2),
                        count=int(mix_count),
                    )
                )

            if single_face and single_count:
                current_faces.append(
                    FaceEntry(
                        faces=(single_face,),
                        count=int(single_count),
                    )
                )

            if fixed_face and fixed_count:
                current_fixed_faces.append(
                    FaceEntry(
                        faces=(fixed_face,),
                        count=int(fixed_count),
                    )
                )

    if current_set_name is not None:
        sets.append(
            SetImport(
                set_name=current_set_name,
                pokemon_name=extract_pokemon_name(current_set_name),
                faces=current_faces,
                fixed_faces=current_fixed_faces,
            )
        )

    return sets


def extract_pokemon_name(set_name: str) -> str:
    cleaned = re.sub(r"^Plakoro\s+Starter\s+Set\s+", "", set_name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\d+$", "", cleaned).strip()
    return cleaned


def build_face_key(type_ids: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(type_ids, key=lambda item: item[0]))


def fetch_or_create_type_id(conn: Any, face_name: str) -> int:
    existing = conn.execute(
        """
				select id
				from types
				where th_name = %s or en_name = %s
				order by id
				limit 1
				""",
        (face_name, face_name),
    ).fetchone()

    if existing is not None:
        return int(existing[0])

    created = conn.execute(
        """
				insert into types (th_name)
				values (%s)
				returning id
				""",
        (face_name,),
    ).fetchone()
    assert created is not None
    return int(created[0])


def load_existing_face_types(conn: Any) -> dict[tuple[tuple[int, int], ...], int]:
    rows = conn.execute("""
				select
						ft.id as face_type_id,
						fte.type_id,
						fte.quantity
				from face_types ft
				join face_type_elements fte on fte.face_type_id = ft.id
				order by ft.id, fte.type_id
				""").fetchall()

    face_types: dict[tuple[tuple[int, int], ...], int] = {}
    current_face_type_id: int | None = None
    current_key: list[tuple[int, int]] = []

    for row in rows:
        face_type_id = int(row[0])
        type_id = int(row[1])
        quantity = int(row[2])

        if current_face_type_id is None:
            current_face_type_id = face_type_id
        elif face_type_id != current_face_type_id:
            face_types[build_face_key(current_key)] = current_face_type_id
            current_key = []
            current_face_type_id = face_type_id

        current_key.append((type_id, quantity))

    if current_face_type_id is not None:
        face_types[build_face_key(current_key)] = current_face_type_id

    return face_types


def fetch_or_create_face_type_id(
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: tuple[str, ...],
) -> int:
    type_counts = Counter(faces)
    resolved_pairs = tuple(
        (fetch_or_create_type_id(conn, face_name), quantity)
        for face_name, quantity in type_counts.items()
    )
    face_key = build_face_key(resolved_pairs)

    existing_face_type_id = face_type_cache.get(face_key)
    if existing_face_type_id is not None:
        return existing_face_type_id

    face_type_id = int(
        conn.execute("insert into face_types default values returning id").fetchone()[0]
    )

    for type_id, quantity in face_key:
        conn.execute(
            """
						insert into face_type_elements (face_type_id, type_id, quantity)
						values (%s, %s, %s)
						""",
            (face_type_id, type_id, quantity),
        )

    face_type_cache[face_key] = face_type_id
    return face_type_id


def resolve_pokemon_id(
    conn: Any, pokemon_name: str, create_if_missing: bool = False
) -> int:
    aliases = {
        "Evee": "Eevee",
    }
    lookup_name = aliases.get(pokemon_name, pokemon_name)

    row = conn.execute(
        """
				select id
				from pokemon_sets
				where lower(en_pokemon_name) = lower(%s) or lower(th_pokemon_name) = lower(%s)
				order by id
				limit 1
				""",
        (lookup_name, lookup_name),
    ).fetchone()

    if row is not None:
        return int(row[0])

    if not create_if_missing:
        raise RuntimeError(
            f"Could not find pokemon_sets row for '{lookup_name}'. "
            "Seed pokemon_sets first or adjust extract_pokemon_name() or pass --create-missing."
        )

    # create a minimal pokemon_sets row using any existing type or creating an 'Unknown' type
    type_row = conn.execute("select id from types order by id limit 1").fetchone()
    if type_row is None:
        created_type = conn.execute(
            "insert into types (en_name) values (%s) returning id",
            ("Unknown",),
        ).fetchone()
        type_id = int(created_type[0])
    else:
        type_id = int(type_row[0])

    created = conn.execute(
        """
				insert into pokemon_sets (en_pokemon_name, th_pokemon_name, hp, type_id, weakness_type_id)
				values (%s, %s, %s, %s, %s)
				returning id
				""",
        (lookup_name, lookup_name, 10, type_id, type_id),
    ).fetchone()
    assert created is not None
    return int(created[0])


def upsert_dice_preset(conn: Any, pokemon_id: int, set_name: str) -> Any:
    row = conn.execute(
        """
				select id
				from dice_presets
				where pokemon_id = %s
					and (en_preset_name = %s or th_preset_name = %s)
				order by id
				limit 1
				""",
        (pokemon_id, set_name, set_name),
    ).fetchone()

    if row is not None:
        preset_id = row[0]
        conn.execute(
            """
						update dice_presets
						set en_preset_name = %s,
								th_preset_name = %s,
								pokemon_id = %s
						where id = %s
						""",
            (set_name, set_name, pokemon_id, preset_id),
        )
        return preset_id

    created = conn.execute(
        """
				insert into dice_presets (pokemon_id, en_preset_name, th_preset_name)
				values (%s, %s, %s)
				returning id
				""",
        (pokemon_id, set_name, set_name),
    ).fetchone()
    assert created is not None
    return created[0]


def build_slot_face_types(
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: list[FaceEntry],
) -> list[int]:
    slot_face_types: list[int] = []

    for entry in faces:
        face_type_id = fetch_or_create_face_type_id(conn, face_type_cache, entry.faces)
        slot_face_types.extend([face_type_id] * entry.count)

    if len(slot_face_types) != 18:
        raise RuntimeError(
            f"Expected 18 faces per set, got {len(slot_face_types)}. "
            "Check the CSV counts for missing or extra rows."
        )

    return slot_face_types


def build_fixed_face_quantities(
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: list[FaceEntry],
) -> dict[int, int]:
    fixed_face_quantities: dict[int, int] = {}

    for entry in faces:
        face_type_id = fetch_or_create_face_type_id(conn, face_type_cache, entry.faces)
        fixed_face_quantities[face_type_id] = (
            fixed_face_quantities.get(face_type_id, 0) + entry.count
        )

    return fixed_face_quantities


def replace_dice_preset_faces(
    conn: Any,
    preset_id: int,
    slot_face_types: list[int],
) -> None:
    conn.execute("delete from dice_preset_faces where preset_id = %s", (preset_id,))

    for index, face_type_id in enumerate(slot_face_types):
        die_number = (index // 6) + 1
        face_number = (index % 6) + 1
        conn.execute(
            """
						insert into dice_preset_faces (preset_id, face_type_id, die_number, face_number)
						values (%s, %s, %s, %s)
						""",
            (preset_id, face_type_id, die_number, face_number),
        )


def replace_pokemon_fixed_faces(
    conn: Any,
    pokemon_id: int,
    fixed_face_quantities: dict[int, int],
) -> None:
    conn.execute("delete from pokemon_fixed_faces where pokemon_id = %s", (pokemon_id,))

    for face_type_id, quantity in fixed_face_quantities.items():
        conn.execute(
            """
						insert into pokemon_fixed_faces (pokemon_id, face_type_id, quantity)
						values (%s, %s, %s)
						""",
            (pokemon_id, face_type_id, quantity),
        )


def import_csv(
    database_url: str,
    csv_path: Path,
    dry_run: bool = False,
    create_missing: bool = False,
) -> None:
    imports = parse_plakoro_csv(csv_path)
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - runtime dependency guard
        raise SystemExit(
            "Missing dependency: install psycopg with `pip install 'psycopg[binary]'`."
        ) from exc

    with psycopg.connect(database_url) as conn:
        face_type_cache = load_existing_face_types(conn)

        for set_import in imports:
            pokemon_id = resolve_pokemon_id(
                conn, set_import.pokemon_name, create_if_missing=create_missing
            )
            preset_id = upsert_dice_preset(conn, pokemon_id, set_import.set_name)
            slot_face_types = build_slot_face_types(
                conn, face_type_cache, set_import.faces
            )
            fixed_face_quantities = build_fixed_face_quantities(
                conn, face_type_cache, set_import.fixed_faces
            )

            if not dry_run:
                replace_dice_preset_faces(conn, preset_id, slot_face_types)
                replace_pokemon_fixed_faces(conn, pokemon_id, fixed_face_quantities)

            print(
                f"{set_import.set_name}: preset_id={preset_id}, pokemon_id={pokemon_id}, "
                f"faces={len(slot_face_types)}, fixed_faces={sum(fixed_face_quantities.values())}"
            )

        if dry_run:
            conn.rollback()
        else:
            conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Plakoro CSV data into PostgreSQL."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=Path(__file__).with_name("plakoro sets - dice faces count.csv"),
        type=Path,
        help="Path to the CSV file to import.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL connection string. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and resolve rows without writing changes.",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Automatically create minimal pokemon_sets rows when missing.",
    )

    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")

    import_csv(
        args.database_url,
        args.csv_path,
        dry_run=args.dry_run,
        create_missing=args.create_missing,
    )


if __name__ == "__main__":
    main()
