import os
import shutil


def kebab_case(item: str):
    return item.lower().replace(" ", "-")


def compress_dir(
    input_dir: str,
    output_file: str,
    level: int = -19,
    remove_after: bool = False,
):
    import tarfile

    import zstandard as zstd

    cctx = zstd.ZstdCompressor(level=level)

    with open(output_file, "wb") as f:
        with cctx.stream_writer(f) as compressor:
            with tarfile.open(fileobj=compressor, mode="w") as tar:
                tar.add(input_dir, arcname=".")

    if remove_after:
        shutil.rmtree(input_dir)


def decompress_file(zst_file: str, output_dir: str, delete_after: bool = False):
    import tarfile

    import zstandard as zstd

    dctx = zstd.ZstdDecompressor()

    with open(zst_file, "rb") as f:
        with dctx.stream_reader(f) as decompressor:
            with tarfile.open(fileobj=decompressor, mode="r") as tar:
                tar.extractall(path=output_dir)

    if delete_after:
        os.remove(zst_file)
