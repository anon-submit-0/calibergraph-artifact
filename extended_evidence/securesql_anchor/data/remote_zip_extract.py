#!/usr/bin/env python3
"""Extract a single member from a remote ZIP via HTTP Range requests.

Used to obtain BIRD train_tables.json / dev_tables.json from the official
bird-bench OSS zips without downloading multi-GB archives.
No mock: bytes come straight from the official host; SHA256 of the extracted
member is printed for provenance.
"""
import io
import json
import struct
import sys
import urllib.request
import zlib
import hashlib

UA = {"User-Agent": "curl/8.4.0"}


def fetch_range(url, start, end):
    req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def content_length(url):
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers["Content-Length"])


def find_central_directory(url, size):
    # read last 128KB to find EOCD (and zip64 EOCD locator)
    tail_len = min(131072, size)
    tail = fetch_range(url, size - tail_len, size - 1)
    eocd_off = tail.rfind(b"PK\x05\x06")
    if eocd_off < 0:
        raise SystemExit("EOCD not found")
    eocd = tail[eocd_off:eocd_off + 22]
    cd_size, cd_offset = struct.unpack("<II", eocd[12:20])
    if cd_offset == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:
        loc_off = tail.rfind(b"PK\x06\x07", 0, eocd_off)
        if loc_off < 0:
            raise SystemExit("zip64 locator not found")
        z64_eocd_offset = struct.unpack("<Q", tail[loc_off + 8:loc_off + 16])[0]
        z64 = fetch_range(url, z64_eocd_offset, z64_eocd_offset + 56 - 1)
        assert z64[:4] == b"PK\x06\x06"
        cd_size = struct.unpack("<Q", z64[40:48])[0]
        cd_offset = struct.unpack("<Q", z64[48:56])[0]
    return cd_offset, cd_size


def iter_central_entries(cd_bytes):
    i = 0
    while i < len(cd_bytes):
        if cd_bytes[i:i + 4] != b"PK\x01\x02":
            break
        (nlen, elen, clen) = struct.unpack("<HHH", cd_bytes[i + 28:i + 34])
        comp_method = struct.unpack("<H", cd_bytes[i + 10:i + 12])[0]
        comp_size = struct.unpack("<I", cd_bytes[i + 20:i + 24])[0]
        uncomp_size = struct.unpack("<I", cd_bytes[i + 24:i + 28])[0]
        lho = struct.unpack("<I", cd_bytes[i + 42:i + 46])[0]
        name = cd_bytes[i + 46:i + 46 + nlen].decode("utf-8", "replace")
        extra = cd_bytes[i + 46 + nlen:i + 46 + nlen + elen]
        # zip64 extra field
        if 0xFFFFFFFF in (comp_size, uncomp_size, lho):
            j = 0
            while j + 4 <= len(extra):
                hid, hsz = struct.unpack("<HH", extra[j:j + 4])
                if hid == 0x0001:
                    vals = extra[j + 4:j + 4 + hsz]
                    k = 0
                    if uncomp_size == 0xFFFFFFFF:
                        uncomp_size = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                    if comp_size == 0xFFFFFFFF:
                        comp_size = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                    if lho == 0xFFFFFFFF:
                        lho = struct.unpack("<Q", vals[k:k + 8])[0]; k += 8
                    break
                j += 4 + hsz
        yield name, comp_method, comp_size, uncomp_size, lho
        i += 46 + nlen + elen + clen


def extract(url, suffix, out_path):
    size = content_length(url)
    cd_offset, cd_size = find_central_directory(url, size)
    cd = fetch_range(url, cd_offset, cd_offset + cd_size - 1)
    match = None
    names = []
    for entry in iter_central_entries(cd):
        names.append(entry[0])
        if entry[0].endswith(suffix):
            match = entry
            break
    if not match:
        print(f"member *{suffix} not found; sample entries: {names[:40]}", file=sys.stderr)
        raise SystemExit(2)
    name, method, csize, usize, lho = match
    print(f"found {name} method={method} csize={csize} usize={usize} offset={lho}")
    lh = fetch_range(url, lho, lho + 30 - 1)
    assert lh[:4] == b"PK\x03\x04"
    nlen, elen = struct.unpack("<HH", lh[26:30])
    data_start = lho + 30 + nlen + elen
    blob = fetch_range(url, data_start, data_start + csize - 1)
    if method == 8:
        raw = zlib.decompress(blob, -15)
    elif method == 0:
        raw = blob
    else:
        raise SystemExit(f"unsupported compression method {method}")
    assert len(raw) == usize, f"size mismatch {len(raw)} != {usize}"
    with open(out_path, "wb") as f:
        f.write(raw)
    print(f"wrote {out_path} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")


if __name__ == "__main__":
    url, suffix, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    extract(url, suffix, out_path)
