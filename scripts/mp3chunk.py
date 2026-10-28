"""Fetch and decode a slice from the middle of a remote MP3 without downloading it all."""

import io
import urllib.request
from urllib.parse import urlsplit

import numpy as np
import soundfile as sf

# Hosts that refuse audio requests without a Referer from their own site.
REFERERS = {"ccmixter.org": "https://ccmixter.org/"}


def request_headers(url):
    h = {"User-Agent": "canopy/0.1"}
    if ref := REFERERS.get(urlsplit(url).hostname):
        h["Referer"] = ref
    return h


# MPEG-1/2/2.5 Layer III bitrate (kbps) and sample-rate tables.
_BITRATES = {
    3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],  # MPEG-1
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],      # MPEG-2
    0: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],      # MPEG-2.5
}
_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _frame_len(b, i):
    """Length of the Layer III frame whose header starts at b[i], or 0 if invalid."""
    if i + 4 > len(b) or b[i] != 0xFF or (b[i + 1] & 0xE0) != 0xE0:
        return 0
    version, layer = (b[i + 1] >> 3) & 3, (b[i + 1] >> 1) & 3
    br_idx, sr_idx, pad = b[i + 2] >> 4, (b[i + 2] >> 2) & 3, (b[i + 2] >> 1) & 1
    if version == 1 or layer != 1 or br_idx in (0, 15) or sr_idx == 3:
        return 0
    coef = 144 if version == 3 else 72
    return coef * _BITRATES[version][br_idx] * 1000 // _RATES[version][sr_idx] + pad


def first_frame(b, start=0):
    """Offset of the first header followed by two consistent frames."""
    for i in range(start, len(b) - 4):
        n1 = _frame_len(b, i)
        if n1 and (n2 := _frame_len(b, i + n1)) and _frame_len(b, i + n1 + n2):
            return i
    return -1


def fetch_slice(url, size, seconds=30.0, at=0.35, duration=None, timeout=60):
    """Decode about `seconds` of mono audio starting `at` fraction into the file."""
    if not size:  # unknown length: a one-byte range request reports the total
        req = urllib.request.Request(url, headers={**request_headers(url), "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            size = int(r.headers["Content-Range"].rsplit("/", 1)[1])
    bytes_per_sec = size / duration if duration else 320_000 / 8
    start = int(size * at)
    length = int(bytes_per_sec * seconds) + 8192
    req = urllib.request.Request(url, headers={**request_headers(url),
                                               "Range": f"bytes={start}-{start + length}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    off = first_frame(data)
    if off < 0:
        raise ValueError("no MP3 frame found in slice")
    y, sr = sf.read(io.BytesIO(data[off:]), dtype="float32", always_2d=True)
    return y.mean(axis=1).astype(np.float32), sr
