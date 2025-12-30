import sqlite3
import sys
from pathlib import Path
from time import sleep, time
from threading import Thread
from concurrent.futures import ThreadPoolExecutor, as_completed

# Using CLIP for image embeddings
try:
    import numpy as np
    from PIL import Image
    import torch
    import clip
    import sqlite_vec
except ImportError:
    print("Please install required packages:")
    print("  uv sync --extra image")
    sys.exit(1)

from data_export import EXPORT_DIR

DB_FILE = "images.db"
BATCH_SIZE = 100
MAX_WORKERS = 4
EMBEDDING_DIM = 512  # CLIP ViT-B/32 embedding dimension

total = 0
running = False

# Load CLIP model (ViT-B/32 is a good balance of speed and quality)
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
print(f"Using device: {device}")


def total_counter():
    global total, running
    while running:
        print(f"\r{total} images to add...", end="", flush=True)
        sleep(1)


def read_and_embed_image(path: Path):
    """Read an image and compute its CLIP embedding"""
    try:
        image = Image.open(path).convert("RGB")
        image_input = preprocess(image).unsqueeze(0).to(device)

        with torch.no_grad():
            image_features = model.encode_image(image_input)
            # Normalize the features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        # Convert to numpy and flatten - explicitly use float32
        embedding = image_features.cpu().numpy().flatten().astype(np.float32)
        return str(path), embedding
    except Exception as e:
        print(f"\nError processing {path}: {e}")
        return None


def format_eta(seconds: float):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02}:{m:02}:{s:02}"


def file_generator(base_path):
    """Generator to yield PNG files one at a time"""
    for p in Path(base_path).rglob("*.png"):
        yield p


def create_index(base_path=EXPORT_DIR):
    global total, running

    with sqlite3.connect(DB_FILE) as conn:
        # Load sqlite-vec extension
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        # Drop existing tables
        conn.execute("DROP TABLE IF EXISTS images")
        conn.execute("DROP TABLE IF EXISTS vec_images")

        # Create main table for filepaths
        conn.execute("""
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL
            )
        """)

        # Create virtual table for vector search
        conn.execute(f"""
            CREATE VIRTUAL TABLE vec_images USING vec0(
                id INTEGER PRIMARY KEY,
                embedding FLOAT[{EMBEDDING_DIM}]
            )
        """)

        cursor = conn.cursor()
        # Optimized PRAGMA settings
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA cache_size=-50000;")

        count = 0
        batch_paths = []
        batch_embeddings = []

        print("Counting images...")

        running = True
        t = Thread(target=total_counter)
        t.start()
        for _ in Path(base_path).rglob("*.png"):
            total += 1

        running = False
        t.join()

        print()
        print(f"{total} images to add")

        if total == 0:
            print("No images found!")
            return

        start_time = time()

        # Process images in chunks
        chunk_size = MAX_WORKERS * 10
        file_iter = file_generator(base_path)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            done = False

            while not done:
                # Submit chunk_size files at a time
                futures = []
                for _ in range(chunk_size):
                    try:
                        path = next(file_iter)
                        futures.append(executor.submit(read_and_embed_image, path))
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

                    filepath, embedding = result
                    batch_paths.append((filepath,))
                    batch_embeddings.append(embedding)
                    count += 1

                    # Commit if batch is full
                    if len(batch_paths) >= BATCH_SIZE:
                        # Insert filepaths and get their IDs
                        for i, (filepath,) in enumerate(batch_paths):
                            cursor.execute(
                                "INSERT OR REPLACE INTO images (filepath) VALUES (?)",
                                (filepath,),
                            )
                            row_id = cursor.lastrowid

                            # Insert corresponding embedding
                            cursor.execute(
                                "INSERT OR REPLACE INTO vec_images (id, embedding) VALUES (?, ?)",
                                (row_id, batch_embeddings[i].tobytes()),
                            )

                        conn.commit()
                        batch_paths.clear()
                        batch_embeddings.clear()

                        now = time()
                        rate = count / (now - start_time)
                        eta = (total - count) / rate if rate > 0 else 0

                        print(
                            f"Progress: {count / total * 100:.2f}% | "
                            f"{rate:.2f} images/s | ETA: {format_eta(eta)}"
                        )

        # Flush remainder
        if batch_paths:
            for i, (filepath,) in enumerate(batch_paths):
                cursor.execute(
                    "INSERT OR REPLACE INTO images (filepath) VALUES (?)", (filepath,)
                )
                row_id = cursor.lastrowid

                # Insert corresponding embedding
                cursor.execute(
                    "INSERT OR REPLACE INTO vec_images (id, embedding) VALUES (?, ?)",
                    (row_id, batch_embeddings[i].tobytes()),
                )
            conn.commit()

        # Final checkpoint
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    print(f"Done! Indexed {count} images in {format_eta(time() - start_time)}")


def search(query: str, top_k: int = 20, image_path: str = None):
    """
    Search for images using natural language query or an input image.

    Args:
        query: Natural language description (e.g., "right arrow", "red circle")
        top_k: Number of top results to return
        image_path: Path to an image file for image-to-image search (optional)
    """
    if image_path:
        print(f"Searching for images similar to: '{image_path}'")

        # Encode the input image
        try:
            image = Image.open(image_path).convert("RGB")
            image_input = preprocess(image).unsqueeze(0).to(device)

            with torch.no_grad():
                image_features = model.encode_image(image_input)
                image_features = image_features / image_features.norm(
                    dim=-1, keepdim=True
                )

            query_embedding = image_features.cpu().numpy().flatten().astype(np.float32)
        except Exception as e:
            print(f"Error processing image: {e}")
            return
    else:
        print(f"Searching for: '{query}'")

        # Encode the text query
        with torch.no_grad():
            text_input = clip.tokenize([query]).to(device)
            text_features = model.encode_text(text_input)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        query_embedding = text_features.cpu().numpy().flatten().astype(np.float32)

    # Use sqlite-vec for efficient similarity search
    with sqlite3.connect(DB_FILE) as conn:
        # Load sqlite-vec extension
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)

        cursor = conn.cursor()

        # Perform vector similarity search
        # sqlite-vec uses distance (lower is better)
        # Must use 'k = ?' syntax for vec0 queries
        cursor.execute(
            """
            SELECT 
                images.filepath,
                distance
            FROM vec_images
            LEFT JOIN images ON vec_images.id = images.id
            WHERE embedding MATCH ?
              AND k = ?
            ORDER BY distance
        """,
            (query_embedding.tobytes(), top_k),
        )

        results = cursor.fetchall()

    if not results:
        print("No images in database")
        return

    # Display results
    print(f"\nTop {len(results)} matches:\n")

    for i, (filepath, distance) in enumerate(results, 1):
        # Convert distance to similarity for display
        # For normalized vectors with L2 distance: similarity ≈ 1 - (distance²/2)
        # Or we can just show distance (lower is better)

        # Color code by distance (lower is better)
        if distance < 0.8:
            color = "\033[92m"  # Green for low distance (high similarity)
        elif distance < 1.0:
            color = "\033[93m"  # Yellow for medium distance
        else:
            color = "\033[91m"  # Red for high distance (low similarity)

        print(f"{i:2d}. {color}{distance:.4f}\033[0m  \033[35m{filepath}\033[0m")


if __name__ == "__main__":
    import os

    if len(sys.argv) > 1:
        # Search mode
        args = sys.argv[1:]

        # Check for top-k flag
        top_k = 20
        if "-n" in args:
            idx = args.index("-n")
            if idx + 1 < len(args):
                try:
                    top_k = int(args[idx + 1])
                    args = args[:idx] + args[idx + 2 :]
                except ValueError:
                    print("Invalid number for -n flag")
                    sys.exit(1)

        # Check for image search flag
        image_path = None
        if "-i" in args or "--image" in args:
            flag = "-i" if "-i" in args else "--image"
            idx = args.index(flag)
            if idx + 1 < len(args):
                image_path = args[idx + 1]
                args = args[:idx] + args[idx + 2 :]
            else:
                print(f"No image path provided after {flag}")
                sys.exit(1)

        if image_path:
            # Image-to-image search
            if not os.path.exists(DB_FILE):
                print(f"Database {DB_FILE} not found. Please index images first.")
                sys.exit(1)
            if not os.path.exists(image_path):
                print(f"Image file '{image_path}' not found.")
                sys.exit(1)
            search("", top_k=top_k, image_path=image_path)
        elif args:
            # Text query search
            query = " ".join(args)
            if not os.path.exists(DB_FILE):
                print(f"Database {DB_FILE} not found. Please index images first.")
                sys.exit(1)
            search(query, top_k=top_k)
        else:
            print("Usage: python script.py [-n NUM_RESULTS] <search query>")
            print("       python script.py [-n NUM_RESULTS] -i <image_path>")
    elif not os.path.exists(DB_FILE):
        # Index mode - allow custom path
        base_path = input(f"Enter directory to index (default: {EXPORT_DIR}): ").strip()
        if not base_path:
            base_path = EXPORT_DIR

        if not Path(base_path).exists():
            print(f"Directory {base_path} does not exist!")
            sys.exit(1)

        create_index(base_path)
    else:
        print(f"Database {DB_FILE} already exists. Delete it to reindex.")
        print("\nUsage:")
        print("  Text search:  python script.py <query>")
        print("                python script.py right arrow")
        print("                python script.py red circle")
        print("  Image search: python script.py -i <image_path>")
        print("                python script.py -i my_image.png")
        print("                python script.py --image my_image.png")
        print("  Top-N:        python script.py -n 50 blue button")
        print("                python script.py -n 50 -i my_image.png")
        print("                (returns top 50 results instead of default 20)")
