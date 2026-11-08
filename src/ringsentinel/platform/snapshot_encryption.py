"""Offline standard age envelopes; never restores or alters a live database."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from ringsentinel.platform.backup import validate_snapshot

MAX_BYTES = 10_000_000_000
MAX_FILES = 1_000_000
MAX_MANIFEST_BYTES = 64_000_000
PATH_PATTERN = r"manifest\.json|database\.(sqlite3|dump)|objects/[a-f0-9]{32}\.json"
BECH32 = "023456789acdefghjklmnpqrstuvwxyz"


def run_age(binary, arguments, *, stdin, stdout):
    try:
        subprocess.run(
            [str(binary), *arguments],
            stdin=stdin,
            stdout=stdout,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        raise ValueError("Encryption tool failed") from None


def seal(source: Path, output: Path, recipient: str, *, binary="age"):
    source, output = source.resolve(), output.absolute()
    if output.resolve().is_relative_to(source) or output.exists():
        raise ValueError("New output outside snapshot required")
    if not re.fullmatch(r"age1[" + BECH32 + r"]{58}", recipient):
        raise ValueError("Native X25519 recipient required")
    if (source / "manifest.json").stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest byte limit")
    manifest = validate_snapshot(source)
    if len(manifest["files"]) >= MAX_FILES:
        raise ValueError("Snapshot file limit")
    created = False
    try:
        # Temporary plaintext is removed on close; no shell pipeline handles binary bytes.
        with tempfile.TemporaryFile() as archive:
            with tarfile.open(fileobj=archive, mode="w", format=tarfile.USTAR_FORMAT) as tar:
                for name in ["manifest.json", *sorted(manifest["files"])]:
                    path = source / name
                    if path.is_symlink() or not path.is_file():
                        raise ValueError("Regular snapshot files required")
                    info = tar.gettarinfo(str(path), arcname=name)
                    info.mode, info.uid, info.gid, info.mtime = 0o600, 0, 0, 0
                    info.uname = info.gname = ""
                    if archive.tell() + info.size + 10240 > MAX_BYTES:
                        raise ValueError("Snapshot byte limit")
                    with path.open("rb") as stream:
                        tar.addfile(info, stream)
            if archive.tell() > MAX_BYTES:
                raise ValueError("Snapshot byte limit")
            archive.seek(0)
            with output.open("xb") as encrypted:
                created = True
                run_age(
                    binary, ["--encrypt", "--recipient", recipient], stdin=archive, stdout=encrypted
                )
        with output.open("rb") as stream:
            if stream.read(22) != b"age-encryption.org/v1\n":
                raise ValueError("Encrypted envelope missing")
            stream.seek(0)
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        return dict(status="encrypted", size_bytes=output.stat().st_size, sha256=checksum)
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise


def native_identity(path):
    with path.open("rb") as stream:
        content = stream.read(65_537)
    if len(content) > 65_536:
        raise ValueError("Identity limit")
    keys = [
        line.strip()
        for line in content.decode("utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not 1 <= len(keys) <= 8 or any(
        not re.fullmatch(r"AGE-SECRET-KEY-1[" + BECH32.upper() + r"]{58}", key) for key in keys
    ):
        raise ValueError("Native identities required")
    return content


def unseal(source: Path, destination: Path, identity: Path, *, binary="age"):
    if destination.exists() or not source.is_file() or source.stat().st_size > MAX_BYTES * 1.01:
        raise ValueError("New destination and bounded ciphertext required")
    key = native_identity(identity)
    # Authenticate the complete age payload before any archive member is extracted.
    with tempfile.TemporaryFile() as archive, tempfile.TemporaryFile() as secret:
        secret.write(key)
        secret.seek(0)
        run_age(
            binary,
            ["--decrypt", "--identity", "-", str(source.resolve())],
            stdin=secret,
            stdout=archive,
        )
        if archive.tell() > MAX_BYTES:
            raise ValueError("Archive byte limit")
        archive.seek(0)
        destination.mkdir(mode=0o700)
        (destination / "objects").mkdir(mode=0o700)
        staging = destination / ".unseal-staging"
        staging.mkdir(mode=0o700)
        (staging / "objects").mkdir(mode=0o700)
        names, total = set(), 0
        with tarfile.open(fileobj=archive, mode="r|") as tar:
            for member in tar:
                if (
                    not member.isfile()
                    or not re.fullmatch(PATH_PATTERN, member.name)
                    or member.name in names
                    or len(names) >= MAX_FILES
                    or (member.name == "manifest.json" and member.size > MAX_MANIFEST_BYTES)
                    or member.size < 0
                    or total + member.size > MAX_BYTES
                ):
                    raise ValueError("Unsafe or oversized snapshot archive")
                names.add(member.name)
                total += member.size
                with (
                    tar.extractfile(member) as stream,
                    (staging / member.name).open("xb") as out,
                ):
                    shutil.copyfileobj(stream, out, length=65536)
        manifest = validate_snapshot(staging)
        if names != {"manifest.json", *manifest["files"]}:
            raise ValueError("Archive and manifest disagree")
        # Publish the restore marker only after authenticating and validating every file.
        for name in sorted(manifest["files"]):
            (staging / name).rename(destination / name)
        (staging / "objects").rmdir()
        (staging / "manifest.json").rename(destination / "manifest.json")
        staging.rmdir()
    return dict(status="snapshot_unsealed", files=len(manifest["files"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seal", "unseal"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--age-binary", default="age")
    parser.add_argument("--recipient")
    parser.add_argument("--identity", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "seal":
            result = seal(args.source, args.output, args.recipient or "", binary=args.age_binary)
        else:
            if args.identity is None:
                raise ValueError("Private identity required")
            result = unseal(args.source, args.output, args.identity, binary=args.age_binary)
        print(json.dumps(result))
    except Exception:
        # Never echo paths, private identity contents, recipient keys or tool errors.
        print(json.dumps(dict(status="unavailable", code="SNAPSHOT_ENVELOPE_FAILED")))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
