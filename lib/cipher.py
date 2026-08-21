"""Cipher primitives over Z/29, the Gematria Primus alphabet.

Everything takes and returns rune indices (ints in 0..28), never runes or
Latin: convert at the edges with `c.gp`. Every primitive here decrypts the
solved sections rune-for-rune from the keys recorded in sections.csv --
tests/test_cipher.py holds those known-answer proofs.

## The interrupter, as measured on the solved sections

"Plaintext F is not encrypted" (sections 0.1, 0.4, 0.13) means exactly:

- where the PLAINTEXT rune is F (index 0), the ciphertext rune is F and the
  keystream does NOT advance;
- a ciphertext F elsewhere is an ordinary encryption (0.1 position 5 is
  plaintext M under key I; 0.13 has ciphertext F at 35, 47, 51 and 74 with
  only position 56 a true interrupter).

So during decryption a ciphertext F is AMBIGUOUS. The solved sections were
read by trying both; an attack on an unsolved section must treat the set of
interrupted positions as part of the key. `skips` below is that set:
ciphertext positions passed through unencrypted, holding the keystream.

Two more measured facts worth stealing for attacks:

- 0.1 is enciphered only for runes 0-514; 515-671 (the SOME WISDOM block,
  KNOW THIS, and the word list) are printed unencrypted. 0.4 likewise:
  enciphered 0-318, plaintext 319-407. Cicada mixes enciphered and plain
  stretches inside one section.
- 0.13's keystream is phi(q_i) for q_i the i-th prime, reduced mod 29 only
  at application time.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

N = 29


def _norm_key(key: Iterable[int]) -> list[int]:
    k = [i % N for i in key]
    if not k:
        raise ValueError("empty key")
    return k


# --------------------------------------------------------------------------
# Keystream application: the one loop every polyalphabetic variant shares
# --------------------------------------------------------------------------


def apply_stream(
    text: Iterable[int],
    stream: Iterator[int],
    op,
    skips: frozenset[int] | set[int] = frozenset(),
) -> list[int]:
    """Combine `text` with a keystream, position by position.

    `op(x, k) -> y` does the per-rune arithmetic. Positions in `skips` pass
    through untouched and do NOT consume a keystream element -- the measured
    interrupter behaviour. The stream may be any iterator (a repeated keyword,
    phi of the primes, another text).
    """
    out = []
    for i, x in enumerate(text):
        if i in skips:
            out.append(x)
            continue
        try:
            k = next(stream)
        except StopIteration:
            # A running key shorter than the ciphertext is the obvious mistake;
            # a bare StopIteration here reads as an empty iterator to the
            # caller (and becomes a RuntimeError inside a generator).
            raise ValueError(f"keystream exhausted at position {i}") from None
        out.append(op(x, k) % N)
    return out


def repeat(key: Iterable[int]) -> Iterator[int]:
    """keyword -> endless keystream."""
    k = _norm_key(key)
    while True:
        yield from k


def primes() -> Iterator[int]:
    """2, 3, 5, 7, ... (naive; fast enough for corpus-length streams)."""
    n = 2
    while True:
        if all(n % p for p in range(2, int(n**0.5) + 1)):
            yield n
        n += 1


def phi_primes() -> Iterator[int]:
    """phi(q_i) = q_i - 1 for the i-th prime: section 0.13's keystream."""
    return (p - 1 for p in primes())


# --------------------------------------------------------------------------
# Monoalphabetic
# --------------------------------------------------------------------------


def shift_decrypt(ct: Iterable[int], k: int) -> list[int]:
    return [(x - k) % N for x in ct]


def atbash(text: Iterable[int]) -> list[int]:
    """Alphabet inversion i -> 28-i. Self-inverse; section 0.0's cipher."""
    return [(N - 1 - x) % N for x in text]


def affine_decrypt(ct: Iterable[int], a: int, b: int) -> list[int]:
    """Invert c = a*p + b. 29 is prime, so any a in 1..28 works."""
    inv = pow(a, -1, N)
    return [((x - b) * inv) % N for x in ct]


# --------------------------------------------------------------------------
# Polyalphabetic, keyword-driven
# --------------------------------------------------------------------------


def vigenere_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """p = c - k. Sections 0.1 (DIVINITY) and 0.4 (FIRFUMFERENFE)."""
    return apply_stream(ct, repeat(key), lambda x, k: x - k, skips)


def vigenere_encrypt(pt, key, interrupter: int | None = 0) -> list[int]:
    """c = p + k, with the measured interrupter rule: a plaintext rune equal
    to `interrupter` passes through and the key holds. None disables."""
    stream = repeat(key)
    out = []
    for x in pt:
        if x == interrupter:
            out.append(x)
            continue
        out.append((x + next(stream)) % N)
    return out


def beaufort_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """p = k - c. Self-inverse."""
    return apply_stream(ct, repeat(key), lambda x, k: k - x, skips)


def variant_beaufort_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """p = c + k (encryption was c = p - k)."""
    return apply_stream(ct, repeat(key), lambda x, k: x + k, skips)


def running_key_decrypt(ct, stream: Iterable[int], skips=frozenset()) -> list[int]:
    """p = c - s for an arbitrary keystream (phi_primes(), another text...)."""
    return apply_stream(ct, iter(i % N for i in stream), lambda x, k: x - k, skips)


# --------------------------------------------------------------------------
# Autokey
# --------------------------------------------------------------------------


def autokey_pt_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """Plaintext autokey: keystream is key ++ recovered plaintext.

    Skipped positions neither consume nor extend the keystream, matching the
    interrupter rule everywhere else.
    """
    k = _norm_key(key)
    stream = list(k)
    out, used = [], 0
    for i, x in enumerate(ct):
        if i in skips:
            out.append(x)
            continue
        p = (x - stream[used]) % N
        out.append(p)
        stream.append(p)
        used += 1
    return out


def autokey_ct_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """Ciphertext autokey: keystream is key ++ ciphertext.

    `ct` is materialised because it is read twice -- once as the keystream,
    once as the text. Every primitive here takes an Iterable, so a generator
    or a map() must not come out as an empty decryption.
    """
    ct = list(ct)
    k = _norm_key(key)
    stream = iter(k + [x for i, x in enumerate(ct) if i not in skips])
    return apply_stream(ct, stream, lambda x, s: x - s, skips)


# --------------------------------------------------------------------------
# Section 0.13
# --------------------------------------------------------------------------


def phi_prime_decrypt(ct, skips=frozenset()) -> list[int]:
    """p_i = c_i - phi(q_i), q_i the i-th prime; section 0.13, exact 85/85
    with skips={56} (the one true interrupter on that page)."""
    return running_key_decrypt(ct, phi_primes(), skips)
