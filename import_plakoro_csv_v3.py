from __future__ import annotations  # Enable postponed evaluation of annotations for type hinting

import argparse  # Library to parse command line arguments and options
import csv  # Library to read and parse comma-separated values (CSV) files
import os  # Library to interact with operating system resources like environment variables
import re  # Library for regular expression matching and manipulation
from collections import Counter  # Helper to count hashable objects and track frequencies
from dataclasses import dataclass  # Decorator to automatically generate boilerplates for classes
from pathlib import Path  # Class to perform file system path operations cleanly
from typing import Iterable, Any  # Type hinting annotations for iterables and generic types


@dataclass(frozen=True)  # Define an immutable container representing a face configuration entry
class FaceEntry:
    faces: tuple[str, ...]  # A tuple holding the name of face types (e.g. ('Grass',) or ('Grass', 'Dark'))
    count: int  # The quantity of this specific face configuration in the dataset


@dataclass(frozen=True)  # Define an immutable container representing an imported Pokemon set
class SetImport:
    set_name: str  # The full name of the Pokemon starter set from the CSV
    pokemon_name: str  # The cleaned up, core English name of the Pokemon
    faces: list[FaceEntry]  # List of customizable dice face configurations parsed for this set
    fixed_faces: list[FaceEntry]  # List of fixed face configurations parsed for this set


@dataclass(frozen=True)  # Define an immutable container representing a parsed Pokemon detail row
class PokemonImport:
    set_name: str  # The starter set name of the Pokemon matching the main CSV
    th_name: str  # The Thai translation name of the Pokemon
    en_name: str  # The English translation name of the Pokemon
    url: str | None  # The image URL for the Pokemon character
    type_name: str  # The element type name in Thai
    weakness_type_name: str  # The weakness element type name in Thai
    hp: int  # The hit points count as an integer
    th_description: str | None  # Thai description card text
    en_description: str | None  # English description card text


@dataclass(frozen=True)  # Define an immutable container representing an energy cost requirement
class SkillCardCost:
    type_name: str  # The Thai type name required for this energy slot
    quantity: int  # The quantity count of this energy cost


@dataclass(frozen=True)  # Define an immutable container representing a skill card effect action
class SkillCardEffect:
    directions: list[str]  # The required die face directions list (Upright, FaceUp, etc.)
    th_effect: str  # The Thai description of the effect outcome
    en_effect: str  # The English description of the effect outcome


@dataclass  # Define a mutable container representing a parsed skill card card structure
class SkillCardImport:
    th_name: str  # The Thai name of the skill card
    en_name: str  # The English name of the skill card
    fighting_ability_th: str | None  # Custom combat logic text in Thai
    fighting_ability_en: str | None  # Custom combat logic text in English
    url: str | None  # Image URL mapping to this card asset
    skill_type: str  # Primary combat type name in Thai
    damage: int  # Base damage points as an integer
    costs: list[SkillCardCost]  # Accumulated energy slot cost requirements list
    effects: list[SkillCardEffect]  # Accumulated direction-based effect blocks list


def parse_plakoro_csv(csv_path: Path) -> list[SetImport]:  # Parse the CSV file into structured set models
    sets: list[SetImport] = []  # Initialize an empty list to accumulate all parsed Pokemon sets
    current_set_name: str | None = None  # Pointer to keep track of the current set name being processed
    current_faces: list[FaceEntry] = []  # Accumulator for customizable faces of the current set
    current_fixed_faces: list[FaceEntry] = []  # Accumulator for fixed faces of the current set

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:  # Open CSV with UTF-8 and BOM protection
        reader = csv.reader(handle)  # Instantiate the standard CSV reader
        next(reader, None)  # Skip the header row of the CSV file

        for raw_row in reader:  # Loop through each row in the CSV file
            row = [cell.strip() for cell in raw_row]  # Strip whitespace from each cell in the row
            if len(row) < 6:  # Check if the row has fewer cells than the minimum columns
                row.extend([""] * (6 - len(row)))  # Pad the row list with empty strings if too short

            (
                set_name,  # Column 1: The name of the starter set
                mix_1,  # Column 2: First element of a mixed face
                mix_2,  # Column 3: Second element of a mixed face
                mix_count,  # Column 4: Occurrence count of the mixed face
                single_face,  # Column 5: Element of a single face
                single_count,  # Column 6: Occurrence count of the single face
                fixed_face,  # Column 7: Element of a fixed face
                fixed_count,  # Column 8: Occurrence count of the fixed face
            ) = row[:8]  # Slice and unpack the first 8 columns of the row

            if set_name:  # If a new set name is found in the first column
                if current_set_name is not None:  # If a set was already being parsed previously
                    sets.append(  # Add the fully populated SetImport object to the sets list
                        SetImport(
                            set_name=current_set_name,  # Set name of the completed set
                            pokemon_name=extract_pokemon_name(current_set_name),  # Core name of the Pokemon
                            faces=current_faces,  # Collected customizable faces
                            fixed_faces=current_fixed_faces,  # Collected fixed faces
                        )
                    )
                current_set_name = set_name  # Update the current set name pointer to the new name
                current_faces = []  # Reset the customizable faces list for the new set
                current_fixed_faces = []  # Reset the fixed faces list for the new set

            if current_set_name is None:  # Skip processing if we haven't encountered a set name yet
                continue  # Go to the next row in the CSV loop

            if mix_1 and mix_2 and mix_count:  # If a mixed face configuration is present
                count = int(mix_count)  # Parse count to integer
                if count > 0:  # Only parse face types that have face count more than 0
                    current_faces.append(  # Append a FaceEntry for the mixed face
                        FaceEntry(
                            faces=(mix_1, mix_2),  # Store the two mixed face names as a tuple
                            count=count,  # Store the verified count > 0
                        )
                    )

            if single_face and single_count:  # If a single face configuration is present
                count = int(single_count)  # Parse count to integer
                if count > 0:  # Only parse face types that have face count more than 0
                    current_faces.append(  # Append a FaceEntry for the single face
                        FaceEntry(
                            faces=(single_face,),  # Store the single face name as a one-element tuple
                            count=count,  # Store the verified count > 0
                        )
                    )

            if fixed_face and fixed_count:  # If a fixed face configuration is present
                count = int(fixed_count)  # Parse count to integer
                if count > 0:  # Only parse face types that have face count more than 0
                    current_fixed_faces.append(  # Append a FaceEntry for the fixed face
                        FaceEntry(
                            faces=(fixed_face,),  # Store the fixed face name as a one-element tuple
                            count=count,  # Store the verified count > 0
                        )
                    )

    if current_set_name is not None:  # If the file ended and there is a trailing set in progress
        sets.append(  # Append the final set to the results list
            SetImport(
                set_name=current_set_name,  # Set name of the final set
                pokemon_name=extract_pokemon_name(current_set_name),  # Core name of the final Pokemon
                faces=current_faces,  # Collected customizable faces for the final set
                fixed_faces=current_fixed_faces,  # Collected fixed faces for the final set
            )
        )

    return sets  # Return the complete list of parsed SetImport objects


def parse_mapping_csv(csv_path: Path) -> dict[str, dict[str, dict[str, str]]]:  # Parse mapping CSV file
    mappings: dict[str, dict[str, dict[str, str]]] = {}  # Initialize empty dictionary for mappings
    if not csv_path.exists():  # If the mapping CSV file does not exist
        return mappings  # Return empty mappings dictionary

    current_table: str | None = None  # Pointer to keep track of current table context
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:  # Open file with UTF-8 and BOM protection
        reader = csv.DictReader(handle)  # Instantiate DictReader to read columns as dictionaries
        for row in reader:  # Loop through rows in the mapping CSV
            tbl = (row.get("table") or row.get("Table") or "").strip()  # Get and strip the table cell
            if tbl:  # If a table name is specified in this row
                current_table = tbl  # Update the current table context pointer

            if not current_table:  # Skip row if no active table context exists
                continue  # Go to the next mapping row

            thai = (row.get("Thai") or row.get("thai") or "").strip()  # Get and strip the Thai name
            eng = (row.get("Eng") or row.get("eng") or "").strip()  # Get and strip the English name
            image = (row.get("Image url") or row.get("image url") or row.get("Image URL") or "").strip()  # Get image URL

            if current_table not in mappings:  # If the table is not registered in mappings dictionary yet
                mappings[current_table] = {}  # Initialize dictionary for this table

            if thai:  # If Thai name is present
                mappings[current_table][thai] = {  # Map Thai name to English name and image URL
                    "eng": eng,  # Store English translation name
                    "image": image  # Store image URL string
                }
    return mappings  # Return parsed tables mapping dictionary


def parse_dice_face_ids(
    csv_path: Path,
    conn: Any,
    type_mappings: dict[str, dict[str, str]],
) -> dict[tuple[tuple[int, int], ...], int]:  # Parse Dice Face ID CSV and build face ID mappings
    face_id_map: dict[tuple[tuple[int, int], ...], int] = {}
    if not csv_path.exists():
        return face_id_map

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = [row for row in reader]

    if len(rows) < 2:
        return face_id_map

    header_row = [cell.strip() for cell in rows[1]]
    col_elements = header_row[3:]

    for r in rows[2:]:
        r = [cell.strip() for cell in r]
        if not r or not r[0]:
            continue

        row_element = r[0]
        # Single face ID is in column 1
        if len(r) > 1 and r[1]:
            single_id = int(r[1])
            type_id = fetch_or_create_type_id(conn, row_element, type_mappings)
            face_key = build_face_key(((type_id, 1),))
            face_id_map[face_key] = single_id

        # Duo face IDs start from column 3
        for col_idx, col_val in enumerate(r[3:]):
            if col_idx < len(col_elements) and col_val:
                duo_id = int(col_val)
                col_element = col_elements[col_idx]
                
                type_id1 = fetch_or_create_type_id(conn, row_element, type_mappings)
                type_id2 = fetch_or_create_type_id(conn, col_element, type_mappings)
                
                if type_id1 == type_id2:
                    type_counts = {type_id1: 2}
                else:
                    type_counts = {type_id1: 1, type_id2: 1}
                
                face_key = build_face_key(type_counts.items())
                face_id_map[face_key] = duo_id

    return face_id_map


def parse_pokemons_csv(csv_path: Path) -> dict[str, PokemonImport]:  # Parse detailed Pokemons CSV dataset
    pokemons: dict[str, PokemonImport] = {}  # Initialize output dictionary map
    if not csv_path.exists():  # Return early if pokemons file is missing
        return pokemons  # Return empty map

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:  # Open file handles with UTF-8 encoding
        reader = csv.reader(handle)  # Construct standard CSV reader
        next(reader, None)  # Skip columns header row

        for raw_row in reader:  # Loop over raw CSV rows
            row = [cell.strip() for cell in raw_row]  # Strip padding spacing from cells
            if len(row) < 10:  # Pad list if elements length is insufficient
                row.extend([""] * (10 - len(row)))  # Extend missing trailing cells with empty strings

            (
                set_name,  # Column 1: Starter set name
                jp_name,  # Column 2: Japanese name (ignored)
                th_name,  # Column 3: Thai name of Pokémon
                en_name,  # Column 4: English name of Pokémon
                url,  # Column 5: Optional URL to image resource
                type_name,  # Column 6: Thai element type
                weakness_type_name,  # Column 7: Thai weakness element type
                hp,  # Column 8: Hit points integer string
                th_desc,  # Column 9: Thai description card text
                en_desc,  # Column 10: English description card text
            ) = row[:10]  # Unpack sliced cells values list

            if not set_name:  # Skip line if set identity cell is empty
                continue  # Go to next line in loop

            pokemons[set_name] = PokemonImport(  # Register PokemonImport dataclass keyed by set_name
                set_name=set_name,  # Bind matching set name
                th_name=th_name,  # Bind Thai name
                en_name=en_name,  # Bind English name
                url=url if url else None,  # Save URL if populated else None
                type_name=type_name,  # Save Thai type
                weakness_type_name=weakness_type_name,  # Save Thai weakness type
                hp=int(hp) if hp else 10,  # Cast hp value to int defaulting to 10
                th_description=th_desc if th_desc else None,  # Save th description
                en_description=en_desc if en_desc else None,  # Save en description
            )

    return pokemons  # Return completed pokemons data map


def parse_skill_cards_csv(csv_path: Path) -> dict[str, list[SkillCardImport]]:  # Parse detailed skill cards CSV dataset
    skills_by_set: dict[str, list[SkillCardImport]] = {}  # Initialize output dictionary map
    if not csv_path.exists():  # Return early if skill cards file is missing
        return skills_by_set  # Return empty map

    current_set_name: str | None = None  # Track active set block pointer
    current_skill: SkillCardImport | None = None  # Track active skill card pointer for group accumulation

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:  # Open file handles with UTF-8 encoding
        reader = csv.reader(handle)  # Construct standard CSV reader
        next(reader, None)  # Skip columns header row

        for raw_row in reader:  # Loop over raw CSV rows
            row = [cell.strip() for cell in raw_row]  # Strip padding spacing from cells
            if len(row) < 14:  # Pad list if elements length is insufficient
                row.extend([""] * (14 - len(row)))  # Extend missing trailing cells with empty strings

            (
                set_name,  # Column 1: Starter set name
                jp_name,  # Column 2: Japanese skill name (ignored)
                th_name,  # Column 3: Thai name of the skill card
                en_name,  # Column 4: English name of the skill card
                th_ability,  # Column 5: Thai fighting ability combat text
                en_ability,  # Column 6: English fighting ability combat text
                url,  # Column 7: Optional card asset URL
                skill_type,  # Column 8: Primary combat type element name
                damage,  # Column 9: Base damage integer string
                cost_type,  # Column 10: Energy cost element name
                cost_quantity,  # Column 11: Energy cost requirement amount
                effect_dirs,  # Column 12: Direction enum triggers required
                effect_th,  # Column 13: Thai description of the effect outcome
                effect_en,  # Column 14: English description of the effect outcome
            ) = row[:14]  # Unpack sliced cells values list

            if set_name:  # If a new set name block is encountered
                current_set_name = set_name  # Update set context pointer

            if th_name or en_name:  # If the row defines a new skill card card
                current_skill = SkillCardImport(  # Instantiate new card accumulator
                    th_name=th_name,  # Bind Thai name
                    en_name=en_name,  # Bind English name
                    fighting_ability_th=th_ability if th_ability else None,  # Save combat ability text or None
                    fighting_ability_en=en_ability if en_ability else None,  # Save combat ability text or None
                    url=url if url else None,  # Save card URL or None
                    skill_type=skill_type,  # Save primary type
                    damage=int(damage) if damage else 0,  # Cast base damage to int defaulting to 0
                    costs=[],  # Initialize empty list for multiple costs
                    effects=[],  # Initialize empty list for multiple direction effects
                )
                if current_set_name:  # If set context is active
                    if current_set_name not in skills_by_set:  # Initialize list if missing
                        skills_by_set[current_set_name] = []  # Initialize empty list
                    skills_by_set[current_set_name].append(current_skill)  # Register skill in the set list

            if current_skill is None:  # Skip processing costs/effects if no active skill card is parsed yet
                continue  # Go to next row in CSV loop

            if cost_type and cost_quantity:  # If energy cost column details are present on row
                current_skill.costs.append(  # Add cost parameter block to active skill card
                    SkillCardCost(
                        type_name=cost_type,  # Cost element name
                        quantity=int(cost_quantity),  # Cast cost quantity to integer
                    )
                )

            if effect_dirs or effect_th or effect_en:  # If direction-based effect details are present on row
                dirs = [d.strip() for d in effect_dirs.split(",") if d.strip()] if effect_dirs else []  # Parse directions comma list
                current_skill.effects.append(  # Add effect parameter block to active skill card
                    SkillCardEffect(
                        directions=dirs,  # Directions trigger list
                        th_effect=effect_th,  # Thai effect text
                        en_effect=effect_en,  # English effect text
                    )
                )

    return skills_by_set  # Return maps dictionary containing skills grouped by starter set names


def extract_pokemon_name(set_name: str) -> str:  # Helper to isolate core Pokémon name from set title
    cleaned = re.sub(r"^Plakoro\s+Starter\s+Set\s+", "", set_name, flags=re.IGNORECASE)  # Strip starter set prefix
    cleaned = re.sub(r"\s+\d+$", "", cleaned).strip()  # Strip any trailing numbers and spaces
    return cleaned  # Return the cleaned, normalized English Pokémon name


def build_face_key(type_ids: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:  # Build sorting key
    return tuple(sorted(type_ids, key=lambda item: item[0]))  # Return sorted type-quantity pairs for caching consistency


def get_next_id_if_needed(conn: Any, table_name: str, column_name: str = "id") -> int | None:
    # Check if the column has a default value (like nextval)
    res = conn.execute(
        """
        select column_default 
        from information_schema.columns 
        where table_schema = 'public' and table_name = %s and column_name = %s
        """,
        (table_name, column_name)
    ).fetchone()
    if res is not None and res[0] is not None:
        # Column has a default value, let database handle identity/auto-increment
        return None
    # No default value found, query max value manually and increment
    row = conn.execute(f"select coalesce(max({column_name}), 0) + 1 from {table_name}").fetchone()
    return int(row[0])


def fetch_or_create_type_id(  # Resolve element name to types table ID with mapping support
    conn: Any,
    face_name: str,
    type_mappings: dict[str, dict[str, str]],
) -> int:
    mapping = type_mappings.get(face_name)  # Look up mapping by direct face name key
    if not mapping:  # If not found directly
        for th, m in type_mappings.items():  # Iterate through mapping records
            if m['eng'] == face_name:  # If the English translation matches the face name
                mapping = {'th': th, 'eng': m['eng'], 'image': m['image']}  # Build mapping dict
                break  # Exit loop when match is found
    else:  # If mapping found directly by Thai name
        mapping = {'th': face_name, 'eng': mapping['eng'], 'image': mapping['image']}  # Build mapping dict

    if mapping:  # If a mapping is successfully resolved
        existing = conn.execute(  # Query DB using both mapped Thai and English names
            """
            select id
            from types
            where th_name = %s or en_name = %s
            order by id
            limit 1
            """,
            (mapping['th'], mapping['eng']),  # Bind mapped Thai and English names
        ).fetchone()  # Fetch the matched record

        if existing is not None:  # If type already exists in the database
            type_id = int(existing[0])  # Cast ID to integer
            conn.execute(  # Update the type record to ensure translation and image URL are populated
                """
                update types
                set th_name = %s, en_name = %s, type_image = %s
                where id = %s
                """,
                (mapping['th'], mapping['eng'], mapping['image'], type_id),  # Bind all updated fields
            )
            return type_id  # Return resolved type ID

        next_id = get_next_id_if_needed(conn, "types")
        if next_id is not None:
            created = conn.execute(  # Insert a new record with manually provided ID
                """
                insert into types (id, th_name, en_name, type_image)
                values (%s, %s, %s, %s)
                returning id
                """,
                (next_id, mapping['th'], mapping['eng'], mapping['image']),
            ).fetchone()
        else:
            created = conn.execute(  # Insert a new record with all mapped fields
                """
                insert into types (th_name, en_name, type_image)
                values (%s, %s, %s)
                returning id
                """,
                (mapping['th'], mapping['eng'], mapping['image']),  # Bind mapped values
            ).fetchone()  # Fetch newly created ID
        assert created is not None  # Assert record creation was successful
        return int(created[0])  # Return new type ID

    existing = conn.execute(  # Query database for matching English or Thai names if no mapping exists
        """
        select id
        from types
        where th_name = %s or en_name = %s
        order by id
        limit 1
        """,
        (face_name, face_name),  # Bind parameter face_name to both th_name and en_name conditions
    ).fetchone()  # Fetch the first matched record if it exists

    if existing is not None:  # If an existing type is found in the database
        return int(existing[0])  # Return the casted integer ID of the existing type

    next_id = get_next_id_if_needed(conn, "types")
    if next_id is not None:
        created = conn.execute(  # Insert a new type with manual ID
            """
            insert into types (id, th_name)
            values (%s, %s)
            returning id
            """,
            (next_id, face_name),
        ).fetchone()
    else:
        created = conn.execute(  # Insert a new type using the face name if not found
            """
            insert into types (th_name)
            values (%s)
            returning id
            """,
            (face_name,),  # Bind parameter to input face_name as th_name
        ).fetchone()  # Fetch the returned new ID
    assert created is not None  # Assert that the returning statement returned a row
    return int(created[0])  # Return the casted integer ID of the newly created type


def load_existing_face_types(conn: Any) -> dict[tuple[tuple[int, int], ...], int]:  # Load face cache from DB
    rows = conn.execute("""
        select
            ft.id as face_type_id,
            fte.type_id,
            fte.quantity
        from face_types ft
        join face_type_elements fte on fte.face_type_id = ft.id
        order by ft.id, fte.type_id
        """).fetchall()  # Execute join query to get all face types and components ordered by IDs

    face_types: dict[tuple[tuple[int, int], ...], int] = {}  # Initialize empty dictionary for local cache
    current_face_type_id: int | None = None  # Pointer to track the current face type ID in iteration
    current_key: list[tuple[int, int]] = []  # List of type ID and quantity pairs for the active face type

    for row in rows:  # Iterate through each fetched database row
        face_type_id = int(row[0])  # Extract and cast the face_type_id
        type_id = int(row[1])  # Extract and cast the type_id constituent
        quantity = int(row[2])  # Extract and cast the quantity count

        if current_face_type_id is None:  # Initialize pointer on the very first row
            current_face_type_id = face_type_id  # Set pointer to first face type ID
        elif face_type_id != current_face_type_id:  # If starting a new face type ID block
            face_types[build_face_key(current_key)] = current_face_type_id  # Save previous face type to cache
            current_key = []  # Reset the constituent list for the new face type
            current_face_type_id = face_type_id  # Update active pointer to new ID

        current_key.append((type_id, quantity))  # Add type ID and quantity tuple to constituent list

    if current_face_type_id is not None:  # If iteration finished and there is an outstanding face type
        face_types[build_face_key(current_key)] = current_face_type_id  # Save the final face type to the cache

    return face_types  # Return the compiled face types dictionary map


def fetch_or_create_face_type_id(  # Resolve face combination to database ID
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: tuple[str, ...],
    type_mappings: dict[str, dict[str, str]],
    face_id_map: dict[tuple[tuple[int, int], ...], int] = None,
) -> int:
    type_counts = Counter(faces)  # Count frequencies of each element in the face tuple
    resolved_pairs = tuple(  # Resolve element names to type IDs and map to their quantities
        (fetch_or_create_type_id(conn, face_name, type_mappings), quantity)  # Call fetch_or_create_type_id for each component
        for face_name, quantity in type_counts.items()  # Loop over counted component names and quantities
    )
    face_key = build_face_key(resolved_pairs)  # Generate a sorted unique key for caching matching

    existing_face_type_id = face_type_cache.get(face_key)  # Check if the cache contains this key
    if existing_face_type_id is not None:  # If this face type was already cached
        return existing_face_type_id  # Return the cached face type database ID

    mapped_id = face_id_map.get(face_key) if face_id_map else None

    if mapped_id is not None:
        conn.execute("delete from face_types where id = %s", (mapped_id,))
        face_type_id = int(
            conn.execute("insert into face_types (id) values (%s) returning id", (mapped_id,)).fetchone()[0]
        )
    else:
        next_id = get_next_id_if_needed(conn, "face_types")
        if next_id is not None:
            face_type_id = int(
                conn.execute("insert into face_types (id) values (%s) returning id", (next_id,)).fetchone()[0]
            )
        else:
            face_type_id = int(  # Insert a new record into face_types to get a new ID
                conn.execute("insert into face_types default values returning id").fetchone()[0]  # Insert and fetch ID
            )

    for type_id, quantity in face_key:  # Loop through constituents of the new face type
        conn.execute(  # Link type ID components to the face type ID
            """
            insert into face_type_elements (face_type_id, type_id, quantity)
            values (%s, %s, %s)
            """,
            (face_type_id, type_id, quantity),  # Bind parameters face_type_id, type_id, and quantity
        )

    face_type_cache[face_key] = face_type_id  # Update cache with the new face type ID
    return face_type_id  # Return the new face type database ID


def resolve_pokemon_id(  # Find or update the matching pokemon_sets ID
    conn: Any,
    pokemon_name: str,
    create_if_missing: bool = False,
    default_type_id: int | None = None,
    pokemon_data: PokemonImport | None = None,
    type_mappings: dict[str, dict[str, str]] = None,
) -> int:
    aliases = {  # Map typical spelling mismatches in dataset
        "Evee": "Eevee",  # Standardize Evee to Eevee
    }
    lookup_name = aliases.get(pokemon_name, pokemon_name)  # Resolve pokemon name through spelling aliases

    row = conn.execute(  # Query pokemon_sets table by lowercased English/Thai names
        """
        select id
        from pokemon_sets
        where lower(en_pokemon_name) = lower(%s) or lower(th_pokemon_name) = lower(%s)
        order by id
        limit 1
        """,
        (lookup_name, lookup_name),  # Bind lookup_name to both name check parameters
    ).fetchone()  # Retrieve first matching record if found

    if pokemon_data is not None:  # If detailed PokemonImport configuration data was supplied
        type_id = fetch_or_create_type_id(conn, pokemon_data.type_name, type_mappings)  # Get/create type ID
        weakness_type_id = fetch_or_create_type_id(conn, pokemon_data.weakness_type_name, type_mappings)  # Get/create weakness ID

        if row is not None:  # If the Pokémon record already exists in database
            pokemon_id = int(row[0])  # Store resolved ID integer
            conn.execute(  # Update all detailed fields in the database table
                """
                update pokemon_sets
                set en_pokemon_name = %s,
                    th_pokemon_name = %s,
                    hp = %s,
                    type_id = %s,
                    weakness_type_id = %s,
                    en_description = %s,
                    th_description = %s,
                    pokemon_image = %s
                where id = %s
                """,
                (
                    pokemon_data.en_name,  # English name update
                    pokemon_data.th_name,  # Thai name update
                    pokemon_data.hp,  # HP update
                    type_id,  # Resolved type update
                    weakness_type_id,  # Resolved weakness update
                    pokemon_data.en_description,  # English description update
                    pokemon_data.th_description,  # Thai description update
                    pokemon_data.url,  # URL update
                    pokemon_id,  # Primary key condition ID
                ),
            )
            return pokemon_id  # Return updated record ID

        next_id = get_next_id_if_needed(conn, "pokemon_sets")
        if next_id is not None:
            created = conn.execute(
                """
                insert into pokemon_sets (id, en_pokemon_name, th_pokemon_name, hp, type_id, weakness_type_id, en_description, th_description, pokemon_image)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    next_id,
                    pokemon_data.en_name,
                    pokemon_data.th_name,
                    pokemon_data.hp,
                    type_id,
                    weakness_type_id,
                    pokemon_data.en_description,
                    pokemon_data.th_description,
                    pokemon_data.url,
                ),
            ).fetchone()
        else:
            created = conn.execute(  # Insert a new detailed Pokemon record in the table
                """
                insert into pokemon_sets (en_pokemon_name, th_pokemon_name, hp, type_id, weakness_type_id, en_description, th_description, pokemon_image)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                returning id
                """,
                (
                    pokemon_data.en_name,  # English name
                    pokemon_data.th_name,  # Thai name
                    pokemon_data.hp,  # HP
                    type_id,  # Resolved type ID
                    weakness_type_id,  # Resolved weakness ID
                    pokemon_data.en_description,  # English description text
                    pokemon_data.th_description,  # Thai description text
                    pokemon_data.url,  # Character URL image
                ),
            ).fetchone()  # Fetch returned ID
        assert created is not None  # Assert insert was successful
        return int(created[0])  # Return created type ID

    if row is not None:  # Fallback to simple lookup if no detailed pokemons CSV data is parsed
        return int(row[0])  # Return the casted integer ID of the Pokémon

    if not create_if_missing:  # If Pokémon is not found and auto-creation is disabled
        raise RuntimeError(  # Raise a helpful error describing missing seeds
            f"Could not find pokemon_sets row for '{lookup_name}'. "
            "Seed pokemon_sets first or adjust extract_pokemon_name() or pass --create-missing."
        )

    if default_type_id is not None:  # If a specific default type ID is provided
        type_id = default_type_id  # Use the provided default type ID
    else:  # If no default type ID is provided
        type_row = conn.execute("select id from types order by id limit 1").fetchone()  # Query first available type
        if type_row is None:  # If the types table is completely empty
            next_id = get_next_id_if_needed(conn, "types")
            if next_id is not None:
                created_type = conn.execute(
                    "insert into types (id, en_name) values (%s, %s) returning id",
                    (next_id, "Unknown"),
                ).fetchone()
            else:
                created_type = conn.execute(  # Insert a fallback Unknown type
                    "insert into types (en_name) values (%s) returning id",
                    ("Unknown",),  # Bind default name 'Unknown'
                ).fetchone()  # Fetch new type ID
            type_id = int(created_type[0])  # Cast ID of created fallback type
        else:  # If types exist in the table
            type_id = int(type_row[0])  # Cast ID of existing available type

    next_id = get_next_id_if_needed(conn, "pokemon_sets")
    if next_id is not None:
        created = conn.execute(
            """
            insert into pokemon_sets (id, en_pokemon_name, th_pokemon_name, hp, type_id, weakness_type_id)
            values (%s, %s, %s, %s, %s, %s)
            returning id
            """,
            (next_id, lookup_name, lookup_name, 10, type_id, type_id),
        ).fetchone()
    else:
        created = conn.execute(  # Insert a minimal pokemon_sets row using the resolved type ID
            """
            insert into pokemon_sets (en_pokemon_name, th_pokemon_name, hp, type_id, weakness_type_id)
            values (%s, %s, %s, %s, %s)
            returning id
            """,
            (lookup_name, lookup_name, 10, type_id, type_id),  # Bind name, placeholder HP=10, types to type_id
        ).fetchone()  # Verify insert operation was successful
    assert created is not None  # Verify that the returning statement returned a row
    return int(created[0])  # Return the casted integer ID of the created Pokémon


def upsert_dice_preset(  # Insert or update preset configurations
    conn: Any,
    pokemon_id: int,
    set_name: str,
    dice1: list[int],
    dice2: list[int],
    dice3: list[int],
) -> Any:
    row = conn.execute(  # Check if a preset already exists for the Pokemon and Name
        """
        select id
        from dice_presets
        where pokemon_id = %s
          and (en_preset_name = %s or th_preset_name = %s)
        order by id
        limit 1
        """,
        (pokemon_id, set_name, set_name),  # Bind parameters pokemon_id and set_name matching conditions
    ).fetchone()  # Fetch existing preset record

    if row is not None:  # If a matching preset record already exists
        preset_id = row[0]  # Store existing UUID primary key
        conn.execute(  # Update existing preset record with new dice arrays
            """
            update dice_presets
            set en_preset_name = %s,
                th_preset_name = %s,
                pokemon_id = %s,
                dice1 = %s,
                dice2 = %s,
                dice3 = %s
            where id = %s
            """,
            (set_name, set_name, pokemon_id, dice1, dice2, dice3, preset_id),  # Bind update parameters
        )
        return preset_id  # Return the UUID of the updated preset

    created = conn.execute(  # Insert a brand new preset record with dice arrays
        """
        insert into dice_presets (pokemon_id, en_preset_name, th_preset_name, dice1, dice2, dice3)
        values (%s, %s, %s, %s, %s, %s)
        returning id
        """,
        (pokemon_id, set_name, set_name, dice1, dice2, dice3),  # Bind values to insert statement
    ).fetchone()  # Fetch returning UUID primary key
    assert created is not None  # Verify insert operation was successful
    return created[0]  # Return the UUID of the newly created preset


def build_slot_face_types(  # Convert customizable face list to 18 flat IDs
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: list[FaceEntry],
    type_mappings: dict[str, dict[str, str]],
    face_id_map: dict[tuple[tuple[int, int], ...], int] = None,
) -> list[int]:
    slot_face_types: list[int] = []  # Initialize empty list to hold the flat face type IDs

    for entry in faces:  # Iterate through customizable face entries
        face_type_id = fetch_or_create_face_type_id(conn, face_type_cache, entry.faces, type_mappings, face_id_map)  # Resolve ID
        slot_face_types.extend([face_type_id] * entry.count)  # Replicate ID based on count value

    if len(slot_face_types) != 18:  # Validate that total customizable faces count is exactly 18 (3 dice * 6 faces)
        raise RuntimeError(  # Raise error if faces count deviates from game design
            f"Expected 18 faces per set, got {len(slot_face_types)}. "
            "Check the CSV counts for missing or extra rows."
        )

    return slot_face_types  # Return verified list of 18 face type IDs


def build_fixed_face_quantities(  # Consolidate fixed face configurations to IDs
    conn: Any,
    face_type_cache: dict[tuple[tuple[int, int], ...], int],
    faces: list[FaceEntry],
    type_mappings: dict[str, dict[str, str]],
    face_id_map: dict[tuple[tuple[int, int], ...], int] = None,
) -> dict[int, int]:
    fixed_face_quantities: dict[int, int] = {}  # Initialize dictionary for fixed faces mapping

    for entry in faces:  # Iterate through fixed face entries
        face_type_id = fetch_or_create_face_type_id(conn, face_type_cache, entry.faces, type_mappings, face_id_map)  # Resolve ID
        fixed_face_quantities[face_type_id] = (  # Add count to existing map or default to 0
            fixed_face_quantities.get(face_type_id, 0) + entry.count  # Sum current count with input count
        )

    return fixed_face_quantities  # Return quantities mapped by face type IDs


def replace_pokemon_fixed_faces(  # Refresh fixed faces records in database
    conn: Any,
    pokemon_id: int,
    fixed_face_quantities: dict[int, int],
) -> None:
    conn.execute("delete from pokemon_fixed_faces where pokemon_id = %s", (pokemon_id,))  # Clear existing records

    for face_type_id, quantity in fixed_face_quantities.items():  # Iterate over face type IDs and quantity mappings
        conn.execute(  # Insert new record into fixed faces table
            """
            insert into pokemon_fixed_faces (pokemon_id, face_type_id, quantity)
            values (%s, %s, %s)
            """,
            (pokemon_id, face_type_id, quantity),  # Bind primary keys and quantity values
        )


def replace_pokemon_available_faces(  # Refresh available custom faces in database
    conn: Any,
    pokemon_id: int,
    available_face_quantities: dict[int, int],
) -> None:
    conn.execute("delete from pokemon_available_faces where pokemon_id = %s", (pokemon_id,))  # Clear existing records

    for face_type_id, quantity in available_face_quantities.items():  # Iterate over custom face types and quantity mappings
        conn.execute(  # Insert new record into available faces table
            """
            insert into pokemon_available_faces (pokemon_id, face_type_id, quantity)
            values (%s, %s, %s)
            """,
            (pokemon_id, face_type_id, quantity),  # Bind primary keys and quantity values
        )


def fetch_or_create_effect_id(  # Resolve direction and text configurations to unique effect ID
    conn: Any,
    directions: list[str],
    th_effect: str | None,
    en_effect: str | None,
) -> int:
    th = th_effect if th_effect else None  # Normalize empty Thai effect text to None
    en = en_effect if en_effect else None  # Normalize empty English effect text to None
    sorted_dirs = sorted(directions)  # Sort directions list to guarantee consistent array order matching

    candidates = conn.execute(  # Query all existing candidate effects with the exact same directions
        """
        select id, th_effect, en_effect
        from effects
        where directions = %s
        """,
        (sorted_dirs,),  # Bind sorted directions array parameter
    ).fetchall()  # Fetch all matched candidate rows

    for row in candidates:  # Loop over candidate effects
        db_id = int(row[0])  # Store candidate row ID
        db_th = row[1]  # Store candidate row Thai text
        db_en = row[2]  # Store candidate row English text

        th_compatible = False  # Track Thai compatibility flag
        if db_th == th:  # If texts match exactly
            th_compatible = True  # Flag as compatible
        elif db_th is None or th is None:  # If one of the texts is None
            th_compatible = True  # Flag as compatible for merging

        en_compatible = False  # Track English compatibility flag
        if db_en == en:  # If texts match exactly
            en_compatible = True  # Flag as compatible
        elif db_en is None or en is None:  # If one of the texts is None
            en_compatible = True  # Flag as compatible for merging

        if th_compatible and en_compatible:  # If both translation components are compatible
            new_th = th if th is not None else db_th  # Resolve best non-null Thai translation
            new_en = en if en is not None else db_en  # Resolve best non-null English translation

            if new_th != db_th or new_en != db_en:  # If updates are needed to complete the record
                conn.execute(  # Update translations on database record
                    """
                    update effects
                    set th_effect = %s, en_effect = %s
                    where id = %s
                    """,
                    (new_th, new_en, db_id),  # Bind new translations and record ID
                )
            return db_id  # Return matching resolved database record ID

    next_id = get_next_id_if_needed(conn, "effects")
    if next_id is not None:
        created = conn.execute(
            """
            insert into effects (id, directions, th_effect, en_effect)
            values (%s, %s, %s, %s)
            returning id
            """,
            (next_id, sorted_dirs, th, en),
        ).fetchone()
    else:
        created = conn.execute(  # Insert a new distinct effect record if no compatible one exists
            """
            insert into effects (directions, th_effect, en_effect)
            values (%s, %s, %s)
            returning id
            """,
            (sorted_dirs, th, en),  # Bind directions array and normalized translations
        ).fetchone()  # Fetch newly generated primary key
    assert created is not None  # Assert record insert was successful
    return int(created[0])  # Return the new ID integer


def import_csv(  # Main CSV importer routine orchestrating database updates
    database_url: str,
    csv_path: Path,
    mapping_csv_path: Path,
    pokemons_csv_path: Path,
    skills_csv_path: Path,
    dice_face_id_csv_path: Path,
    dry_run: bool = False,
    create_missing: bool = False,
) -> None:
    if csv_path is None:
        csv_path = Path(__file__).with_name("plakoro sets - dice faces count.csv")
    if mapping_csv_path is None:
        mapping_csv_path = Path(__file__).with_name("plakoro sets - mapping.csv")
    if pokemons_csv_path is None:
        pokemons_csv_path = Path(__file__).with_name("plakoro sets - pokemons.csv")
    if skills_csv_path is None:
        skills_csv_path = Path(__file__).with_name("plakoro sets - skill cards.csv")
    if dice_face_id_csv_path is None:
        dice_face_id_csv_path = Path(__file__).with_name("plakoro sets - Dice Face ID.csv")

    imports = parse_plakoro_csv(csv_path)  # Parse CSV path parameter into list of SetImport models
    mappings = parse_mapping_csv(mapping_csv_path)  # Parse mapping CSV file path into nested dictionaries
    type_mappings = mappings.get("type", {})  # Retrieve mappings registered specifically for the types table
    
    pokemons_data = parse_pokemons_csv(pokemons_csv_path)  # Parse Pokemons CSV detailed configurations dictionary
    skills_data = parse_skill_cards_csv(skills_csv_path)  # Parse skill cards CSV detailed configurations dictionary

    try:
        import psycopg  # Attempt to import psycopg driver library dynamically
    except ImportError as exc:  # Catch error if driver is not installed
        raise SystemExit(  # Terminate execution with instruction to user
            "Missing dependency: install psycopg with `pip install 'psycopg[binary]'`."
        ) from exc  # Link original exception context

    with psycopg.connect(database_url) as conn:  # Open transactional connection context using connection string
        face_id_map = parse_dice_face_ids(dice_face_id_csv_path, conn, type_mappings)
        face_type_cache = load_existing_face_types(conn)  # Pre-populate local cache with all database face configurations

        for set_import in imports:  # Iterate over each parsed set in CSV imports
            pokemon_data = pokemons_data.get(set_import.set_name)  # Look up detailed Pokémon data matching set name

            # Collect and insert all types present in customizable faces of this set first
            for entry in set_import.faces:  # Loop over customizable face configurations
                for face_name in entry.faces:  # Loop over individual face names in the configuration
                    fetch_or_create_type_id(conn, face_name, type_mappings)  # Resolve or insert the face type into the database

            # Collect and insert all types present in fixed faces of this set first
            for entry in set_import.fixed_faces:  # Loop over fixed face configurations
                for face_name in entry.faces:  # Loop over individual face names in the configuration
                    fetch_or_create_type_id(conn, face_name, type_mappings)  # Resolve or insert the face type into the database

            # Determine the primary type ID for the Pokémon from the first element of its first customizable face configuration
            default_type_id = None  # Initialize default type ID to None
            if set_import.faces and set_import.faces[0].faces:  # If the set contains any customizable faces
                primary_type_name = set_import.faces[0].faces[0]  # Get the first face element name
                default_type_id = fetch_or_create_type_id(conn, primary_type_name, type_mappings)  # Get/create type ID for this name

            pokemon_id = resolve_pokemon_id(  # Resolve Pokémon name to database record ID (creates/updates set details)
                conn, 
                set_import.pokemon_name, 
                create_if_missing=create_missing, 
                default_type_id=default_type_id, 
                pokemon_data=pokemon_data, 
                type_mappings=type_mappings
            )
            
            slot_face_types = build_slot_face_types(  # Extract customizable face IDs array
                conn, face_type_cache, set_import.faces, type_mappings, face_id_map  # Map and expand counts to list
            )
            
            dice1 = slot_face_types[0:6]  # Slice first 6 elements as Die 1 layout
            dice2 = slot_face_types[6:12]  # Slice next 6 elements as Die 2 layout
            dice3 = slot_face_types[12:18]  # Slice last 6 elements as Die 3 layout

            fixed_face_quantities = build_fixed_face_quantities(  # Extract fixed face IDs map
                conn, face_type_cache, set_import.fixed_faces, type_mappings, face_id_map  # Resolve and summarize quantities
            )
            
            available_face_quantities = Counter(slot_face_types)  # Extract available face pool totals from custom faces

            # Execute transactional changes against PostgreSQL (rolled back automatically if dry run)
            preset_id = upsert_dice_preset(  # Upsert preset and acquire UUID key
                conn, pokemon_id, set_import.set_name, dice1, dice2, dice3  # Pass parameters
            )
            replace_pokemon_fixed_faces(conn, pokemon_id, fixed_face_quantities)  # Update fixed faces
            replace_pokemon_available_faces(conn, pokemon_id, available_face_quantities)  # Update available faces pool

            # Import skill cards dataset details for the active Pokémon set
            skill_cards = skills_data.get(set_import.set_name, [])  # Look up skill cards belonging to set name
            skill_ids = []  # List accumulator to store IDs of inserted cards
            if skill_cards:  # If skill cards are present for this Pokémon in dataset
                conn.execute("delete from skill_cards where pokemon_id = %s", (pokemon_id,))  # Clear existing linked skill cards
                for skill in skill_cards:  # Loop through each skill card card
                    skill_type_id = fetch_or_create_type_id(conn, skill.skill_type, type_mappings)  # Resolve type ID of combat element
                    
                    next_id = get_next_id_if_needed(conn, "skill_cards")
                    if next_id is not None:
                        skill_id = int(conn.execute(
                            """
                            insert into skill_cards (id, pokemon_id, en_skill_name, th_skill_name, type_id, damage, en_fighting_ability, th_fighting_ability, image_url)
                            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            returning id
                            """,
                            (
                                next_id,
                                pokemon_id,
                                skill.en_name,
                                skill.th_name,
                                skill_type_id,
                                skill.damage,
                                skill.fighting_ability_en,
                                skill.fighting_ability_th,
                                skill.url,
                            )
                        ).fetchone()[0])
                    else:
                        skill_id = int(conn.execute(  # Insert skill card record details
                            """
                            insert into skill_cards (pokemon_id, en_skill_name, th_skill_name, type_id, damage, en_fighting_ability, th_fighting_ability, image_url)
                            values (%s, %s, %s, %s, %s, %s, %s, %s)
                            returning id
                            """,
                            (
                                pokemon_id,
                                skill.en_name,
                                skill.th_name,
                                skill_type_id,
                                skill.damage,
                                skill.fighting_ability_en,
                                skill.fighting_ability_th,
                                skill.url,
                            )
                        ).fetchone()[0])
                    skill_ids.append(skill_id)  # Add generated ID to list

                    # Insert energy cost components for this skill card
                    for cost in skill.costs:  # Loop over cost items
                        cost_type_id = fetch_or_create_type_id(conn, cost.type_name, type_mappings)  # Resolve element ID
                        conn.execute(  # Insert energy requirements record
                            """
                            insert into skill_card_energy_costs (skill_card_id, type_id, quantity)
                            values (%s, %s, %s)
                            """,
                            (skill_id, cost_type_id, cost.quantity),  # Bind skill card ID, element, and required quantity
                        )

                    # Link or create direction-based effects for this skill card
                    for eff in skill.effects:  # Loop over effect items
                        effect_id = fetch_or_create_effect_id(conn, eff.directions, eff.th_effect, eff.en_effect)  # Get unique ID
                        existing_link = conn.execute(  # Query to check if link already exists
                            "select 1 from skill_card_effects where skill_card_id = %s and effect_id = %s",
                            (skill_id, effect_id),  # Bind IDs
                        ).fetchone()  # Fetch link if exists
                        if not existing_link:  # If link is not registered yet
                            conn.execute(  # Link effect to skill card
                                """
                                insert into skill_card_effects (skill_card_id, effect_id)
                                values (%s, %s)
                                """,
                                (skill_id, effect_id),  # Bind IDs
                            )

                # Link exactly 5 of the newly generated skill card IDs to the preset record in the presets table
                conn.execute(
                    "update dice_presets set skills = %s where id = %s",
                    (skill_ids[:5], preset_id),  # Bind sliced integer array parameter of exactly 5 elements and preset UUID
                )

            print(  # Print human readable import summary to stdout
                f"{set_import.set_name}: preset_id={preset_id}, pokemon_id={pokemon_id}, "
                f"faces={len(slot_face_types)}, fixed_faces={sum(fixed_face_quantities.values())}, "
                f"skills={len(skill_cards)}"
            )

        # Remove orphaned effects rows that are no longer linked to any skill card cards
        conn.execute("delete from effects where id not in (select effect_id from skill_card_effects)")

        if dry_run:  # If dry run flag was supplied
            print("Dry run requested: rolling back transaction.")  # Print transaction notice to stdout
            conn.rollback()  # Rollback all executed transaction commands from connection
        else:  # If standard execution mode
            conn.commit()  # Permanently commit database changes to disk


def main() -> None:  # Entrypoint parser configuration
    parser = argparse.ArgumentParser(  # Set up arguments parser
        description="Import Plakoro CSV data into PostgreSQL (v3 Schema compatible)."
    )
    parser.add_argument(  # Add positional argument for CSV file location
        "csv_path",
        nargs="?",  # Make argument optional
        default=Path(__file__).with_name("plakoro sets - dice faces count.csv"),  # Set default file path in script directory
        type=Path,  # Automatically convert input to Path object
        help="Path to the CSV file to import.",
    )
    parser.add_argument(  # Add database URL argument
        "--database-url",
        default=os.environ.get("DATABASE_URL"),  # Default to env variable DATABASE_URL
        help="PostgreSQL connection string. Defaults to DATABASE_URL.",
    )
    parser.add_argument(  # Add mapping CSV file argument
        "--mapping-csv",
        nargs="?",  # Make mapping CSV argument optional
        default=Path(__file__).with_name("plakoro sets - mapping.csv"),  # Default file name in the script directory
        type=Path,  # Automatically convert input to Path object
        help="Path to the mapping CSV file containing translation and images configuration.",
    )
    parser.add_argument(  # Add pokemons CSV file argument
        "--pokemons-csv",
        nargs="?",  # Make argument optional
        default=Path(__file__).with_name("plakoro sets - pokemons.csv"),  # Default file name in the script directory
        type=Path,  # Automatically convert input to Path object
        help="Path to the detailed Pokemons CSV file containing HP, descriptions and weakness mappings.",
    )
    parser.add_argument(  # Add skill cards CSV file argument
        "--skills-csv",
        nargs="?",  # Make argument optional
        default=Path(__file__).with_name("plakoro sets - skill cards.csv"),  # Default file name in the script directory
        type=Path,  # Automatically convert input to Path object
        help="Path to the detailed skill cards CSV file containing abilities, energy costs and side effects.",
    )
    parser.add_argument(  # Add dice face ID CSV file argument
        "--dice-face-id-csv",
        nargs="?",  # Make argument optional
        default=Path(__file__).with_name("plakoro sets - Dice Face ID.csv"),  # Default file name in the script directory
        type=Path,  # Automatically convert input to Path object
        help="Path to the CSV file containing Dice Face IDs mapping.",
    )
    parser.add_argument(  # Add dry run boolean flag
        "--dry-run",
        action="store_true",  # Store True if flag is specified
        help="Parse and resolve rows without writing changes permanently.",
    )
    parser.add_argument(  # Add auto create missing Pokemon boolean flag
        "--create-missing",
        action="store_true",  # Store True if flag is specified
        help="Automatically create minimal pokemon_sets rows when missing.",
    )

    args = parser.parse_args()  # Run parser and unpack values to args namespace

    if not args.database_url:  # Verify connection string is present
        raise SystemExit("DATABASE_URL is required.")  # Terminate if database URL is missing

    import_csv(  # Trigger main CSV importer block
        args.database_url,  # Pass parsed connection string
        args.csv_path,  # Pass parsed main CSV file path
        args.mapping_csv,  # Pass parsed mapping CSV file path
        args.pokemons_csv,  # Pass parsed detailed pokemons CSV file path
        args.skills_csv,  # Pass parsed detailed skill cards CSV file path
        args.dice_face_id_csv,  # Pass parsed dice face ID CSV file path
        dry_run=args.dry_run,  # Pass parsed dry run flag
        create_missing=args.create_missing,  # Pass parsed auto-create missing flag
    )


if __name__ == "__main__":  # Check if script is run directly from shell
    main()  # Invoke entrypoint routine
