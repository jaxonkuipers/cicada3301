"""The four consumerless 2048-bit blocks of the 2014 route stay byte-exact."""

import hashlib
import re
import unittest

from solver.paths import LP, RECORDS

ONION_BLOCKS = {
    "R14.2/artifacts/onion2-761.hex": (
        2047,
        "05acf0d8e2ba7d851e2b4bbc32b85e461a1bd41576a50504487f33d4c1522c56",
    ),
    "R14.3/artifacts/onion3-1033.hex": (
        2048,
        "d8c0f83cf91d0deda658035e3eb07712b12e72b36ed0e471a71a2fe07dd14ba6",
    ),
    "R14.4/artifacts/onion4-3301.hex": (
        2048,
        "4f1cef871153b8211472d6afd0acfa120eb331b8793e6eb7690484bcb1f89da2",
    ),
}
PAGE_49_51_PAIRS = 256
BASE59 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdeghijklmnopqrstuvwx"


class TestOnionPayloads(unittest.TestCase):
    def test_each_onion_block_is_256_uniform_bytes_with_pinned_digest(self):
        for rel, (bits, sha) in ONION_BLOCKS.items():
            text = (RECORDS / rel).read_text(encoding="utf-8")
            self.assertRegex(text, r"^[0-9a-f]{512}\n$", rel)
            block = bytes.fromhex(text.strip())
            self.assertEqual(len(block), 256, rel)
            self.assertEqual(int.from_bytes(block, "big").bit_length(), bits, rel)
            self.assertEqual(hashlib.sha256(block).hexdigest(), sha, rel)

    def test_page_49_51_code_is_256_pairs_over_59_symbols_decoding_to_bytes(self):
        pairs = []
        for page in (49, 50, 51):
            text = (LP / "transcription" / f"page-{page}.txt").read_text(encoding="utf-8")
            pairs += re.findall(r"\b([0-4][0-9A-Za-z])\b", text)
        self.assertEqual(len(pairs), PAGE_49_51_PAIRS)
        self.assertEqual(len(set("".join(pairs))), 59)
        values = [BASE59.index(a) * 59 + BASE59.index(b) for a, b in pairs]
        self.assertTrue(all(0 <= v <= 255 for v in values))


if __name__ == "__main__":
    unittest.main()
