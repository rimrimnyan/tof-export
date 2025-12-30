import sqlite3
import sys
from pathlib import Path
from time import sleep, time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

from data_export import EXPORT_DIR

DB_FILE = "sqlite.db"
BATCH_SIZE = 1000
MAX_WORKERS = 4
MAX_BATCH_BYTES = 50 * 1024 * 1024  # 50MB - commit if batch exceeds this

total = 0
running = False


def total_counter():
    global total, running
    while running:
        print(f"\r{total} files to add...", end="", flush=True)
        sleep(1)


def read_file(path: Path):
    try:
        return str(path), path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None


def format_eta(seconds: float):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}"


def file_generator(base_path):
    """Generator to yield files one at a time instead of loading all paths"""
    for p in Path(base_path).rglob("*.json"):
        yield p


def create_index():
    global total, running

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DROP TABLE IF EXISTS files")
        conn.execute("CREATE VIRTUAL TABLE files USING fts5(filepath, content)")

        cursor = conn.cursor()
        # Optimized PRAGMA settings for write performance
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")  # Changed from OFF for safety
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA cache_size=-50000;")  # Reduced from 100MB to 50MB
        cursor.execute("PRAGMA mmap_size=268435456;")  # 256MB memory-mapped I/O

        count = 0
        batch = []
        batch_size_bytes = 0  # Track batch size in bytes

        print("Counting files...")

        running = True
        t = Thread(target=total_counter)
        t.start()
        for _ in Path(EXPORT_DIR).rglob("*.json"):
            total += 1

        running = False
        t.join()

        print()
        print(f"{total} files to add")

        if total == 0:
            print("No files found!")
            return

        start_time = time()

        # Process files in chunks to avoid loading all futures at once
        chunk_size = MAX_WORKERS * 10  # Process only 40 files at a time
        file_iter = file_generator(EXPORT_DIR)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            done = False

            while not done:
                # Submit only chunk_size files at a time
                futures = []
                for _ in range(chunk_size):
                    try:
                        path = next(file_iter)
                        futures.append(executor.submit(read_file, path))
                    except StopIteration:
                        done = True
                        break

                if not futures:
                    break

                # Process this chunk
                for future in as_completed(futures):
                    result = future.result()
                    if result is None:
                        continue

                    filepath, content = result
                    content_size = len(content.encode("utf-8"))

                    batch.append(result)
                    batch_size_bytes += content_size
                    count += 1

                    # Commit if batch is full OR batch size exceeds limit
                    if len(batch) >= BATCH_SIZE or batch_size_bytes >= MAX_BATCH_BYTES:
                        cursor.executemany(
                            "INSERT OR REPLACE INTO files VALUES (?, ?)", batch
                        )
                        conn.commit()  # Commit after every batch

                        if batch_size_bytes >= MAX_BATCH_BYTES:
                            print(
                                f"  [Large batch: {batch_size_bytes / 1024 / 1024:.1f}MB committed]"
                            )

                        batch.clear()
                        batch_size_bytes = 0

                        now = time()
                        rate = count / (now - start_time)
                        eta = (total - count) / rate if rate > 0 else 0

                        print(
                            f"Progress: {count / total * 100:.2f}% | "
                            f"{rate:.2f} files/s | ETA: {format_eta(eta)}"
                        )

        # Flush remainder
        if batch:
            cursor.executemany("INSERT OR REPLACE INTO files VALUES (?, ?)", batch)
            conn.commit()

        # Final checkpoint to merge WAL
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")

        # Optimize the database
        print("Optimizing database...")
        cursor.execute("INSERT INTO files(files) VALUES('optimize');")
        conn.commit()

    print(f"Done! Indexed {count} files in {format_eta(time() - start_time)}")


def search(query: str, mode: str = "exact"):
    """
    Search the database with different matching modes.

    Args:
        query: Search query string
        mode: Search mode - "exact" (default), "fuzzy" (OR), or "and" (AND)
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA query_only = ON;")

        # Escape special FTS5 characters by wrapping in quotes
        def escape_fts5(term):
            # If term contains special chars like dots, wrap in quotes
            if any(c in term for c in ".,-_@"):
                return f'"{term}"'
            return term

        # Build FTS5 query based on mode
        if mode == "exact":
            # For exact phrase search, wrap query in quotes for FTS5
            fts_query = f'"{query}"' if " " in query else escape_fts5(query)
        elif mode == "and":
            # For AND search, join terms with AND operator
            terms = query.strip('"').split()
            fts_query = " AND ".join(escape_fts5(term) for term in terms)
        else:  # fuzzy/OR mode
            terms = query.strip('"').split()
            fts_query = " OR ".join(escape_fts5(term) for term in terms)

        cursor.execute(
            "SELECT filepath, content FROM files WHERE content MATCH ? ORDER BY rank LIMIT 100",
            (fts_query,),
        )
        results = cursor.fetchall()

    if not results:
        print("No matches found")
        return

    print(f"Found {len(results)} matches ({mode} search):\n")

    if mode == "exact":
        # Exact mode: look for the complete phrase
        search_pattern = re.compile(re.escape(query), re.IGNORECASE)
    else:
        # Fuzzy or AND mode: highlight individual terms
        terms = query.strip('"').split()
        pattern_parts = [re.escape(term) for term in terms]
        search_pattern = re.compile("|".join(pattern_parts), re.IGNORECASE)

    for filepath, content in results:
        lines = content.split("\n")
        matching_lines = []

        for line_num, line in enumerate(lines, start=1):
            if search_pattern.search(line):
                matching_lines.append((line_num, line))

        if matching_lines:
            print(f"\033[35m{filepath}\033[0m")  # Magenta for filepath

            # Show only first 3 matches
            for line_num, line in matching_lines[:3]:
                # Highlight matches in the line
                highlighted = search_pattern.sub(
                    lambda m: f"\033[1;31m{m.group()}\033[0m",  # Bold red for matches
                    line,
                )
                print(
                    f"\033[32m{line_num}\033[0m:{highlighted}"
                )  # Green for line numbers

            # Show truncation message if there are more matches
            if len(matching_lines) > 3:
                remaining = len(matching_lines) - 3
                print(
                    f"\033[90m... and {remaining} more match{'es' if remaining > 1 else ''}\033[0m"
                )

            print()  # Empty line between files


if __name__ == "__main__":
    import os

    if len(sys.argv) > 1:
        # Check for mode flags
        mode = "exact"  # default
        args = sys.argv[1:]

        if "-f" in args or "--fuzzy" in args:
            mode = "fuzzy"
            args = [arg for arg in args if arg not in ("-f", "--fuzzy")]
        elif "-a" in args or "--and" in args:
            mode = "and"
            args = [arg for arg in args if arg not in ("-a", "--and")]

        if args:
            # Search mode
            search(" ".join(args), mode=mode)
        else:
            print(
                "Usage: python script.py [--exact|--fuzzy|-f|--and|-a] <search terms>"
            )
    elif not os.path.exists(DB_FILE):
        # Index mode
        create_index()
    else:
        print(f"Database {DB_FILE} already exists. Delete it to reindex.")
        print("Usage: python script.py [--exact|--fuzzy|-f|--and|-a] <search terms>")
        print("\nSearch modes:")
        print("  Exact (default): python script.py Alpha Energy")
        print("                   Finds the exact phrase 'Alpha Energy'")
        print("  Fuzzy (OR):      python script.py --fuzzy Alpha Energy")
        print("                   python script.py -f Alpha Energy")
        print("                   Finds lines with 'Alpha' OR 'Energy'")
        print("  AND:             python script.py --and Alpha Energy")
        print("                   python script.py -a Alpha Energy")
        print(
            "                   Finds documents with both 'Alpha' AND 'Energy' (anywhere)"
        )
