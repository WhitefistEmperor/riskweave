"""Install only pinned official age executables for Linux CI restore drills."""

import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path

URL = "https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz"
SHA256 = "cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10"


def main():
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(25_000_001)
    if len(data) > 25_000_000 or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("Official age release digest mismatch")
    root = Path("work/age-ci")
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for name in ("age/age", "age/age-keygen"):
            member = archive.getmember(name)
            if not member.isfile() or member.size > 25_000_000:
                raise ValueError("Invalid release executable")
            output = root / Path(name).name
            with archive.extractfile(member) as stream, output.open("xb") as target:
                target.write(stream.read())
            output.chmod(0o700)
    print("Pinned official age 1.3.2 installed for isolated CI drills")


if __name__ == "__main__":
    main()
