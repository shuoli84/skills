#!/usr/bin/env python3
"""Inspect an Apple Pinyin lexicon and prepare a filtered copy for review."""

import argparse
import json
import os
from pathlib import Path
import sqlite3


def read_words(database):
    columns = {row[1] for row in database.execute('PRAGMA table_info("Words")')}
    if not {"Identifier", "Reading", "Surface"}.issubset(columns):
        raise ValueError("Unsupported Words schema. Inspect this macOS version before proceeding.")
    if database.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise ValueError("Source database failed integrity validation.")
    words = []
    for identifier, reading, surface in database.execute(
        "SELECT Identifier, Reading, Surface FROM Words ORDER BY Identifier"
    ):
        if not isinstance(reading, bytes) or not isinstance(surface, bytes):
            raise ValueError(f"Expected UTF-16LE BLOB fields in entry {identifier}.")
        words.append({
            "id": identifier,
            "reading": reading.decode("utf-16-le"),
            "word": surface.decode("utf-16-le"),
        })
    return words


def contains_latin(word):
    return any(character.isascii() and character.isalpha() for character in word)


def create_private_file(path):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Existing SQLite lexicon or snapshot")
    parser.add_argument("--list", action="store_true", help="Include candidate words in the preview")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--latin", action="store_true", help="Select entries containing ASCII letters")
    selection.add_argument("--ids", nargs="+", type=int, help="Select specific entry IDs")
    parser.add_argument("--output", type=Path, help="New filtered database, never the live database")
    parser.add_argument("--removed", type=Path, help="New JSON audit file for removed entries")
    args = parser.parse_args()
    source = args.source.expanduser().resolve(strict=True)
    if bool(args.output) != bool(args.removed):
        parser.error("--output and --removed must be supplied together.")
    if args.output and not (args.latin or args.ids):
        parser.error("Preparing a copy requires --latin or --ids.")

    connection = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=3)
    outputs_created = []
    candidate = None
    try:
        if args.output:
            output = args.output.expanduser().resolve()
            removed_path = args.removed.expanduser().resolve()
            live_database = (Path.home() / "Library/Dictionaries/DynamicPhraseLexicon_zh_Hans.db").resolve()
            if output in {source, live_database} or removed_path in {source, output, live_database}:
                raise ValueError("Choose distinct new paths for the candidate and audit file.")
            if output.exists() or removed_path.exists():
                raise FileExistsError("Output already exists. Choose new filenames.")
            create_private_file(output)
            outputs_created.append(output)
            candidate = sqlite3.connect(output)
            connection.backup(candidate)
            words = read_words(candidate)
        else:
            words = read_words(connection)

        wanted = set(args.ids or [])
        if wanted - {word["id"] for word in words}:
            raise ValueError("Some requested entry IDs are absent from the source snapshot.")
        if args.ids:
            selected = [word for word in words if word["id"] in wanted]
        else:
            selected = [word for word in words if contains_latin(word["word"])]

        summary = {
            "source": str(source),
            "total_entries": len(words),
            "selected_entries": len(selected),
            "selected_ids": [word["id"] for word in selected],
        }
        if args.list:
            summary["entries"] = selected

        if candidate is not None:
            selected_ids = {word["id"] for word in selected}
            with candidate:
                candidate.executemany(
                    "DELETE FROM Words WHERE Identifier = ?",
                    [(identifier,) for identifier in sorted(selected_ids)],
                )
            remaining = read_words(candidate)
            expected = [word for word in words if word["id"] not in selected_ids]
            if remaining != expected:
                raise ValueError("Filtered database does not match the requested removal set.")
            create_private_file(removed_path)
            outputs_created.append(removed_path)
            removed_path.write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summary.update({"output": str(output), "removed": str(removed_path), "retained_entries": len(remaining)})
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    except Exception:
        if candidate is not None:
            candidate.close()
            candidate = None
        for path in outputs_created:
            path.unlink(missing_ok=True)
        raise
    finally:
        if candidate is not None:
            candidate.close()
        connection.close()


if __name__ == "__main__":
    main()
