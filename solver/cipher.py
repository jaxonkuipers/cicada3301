"""Cipher primitives over Z/29, the Gematria Primus alphabet.

Ciphertext and plaintext are rune indices, never runes or Latin: convert at
the edges with `c.gp`. Numeric key material is integral and reduced modulo 29.
Section keys and boundaries live in sections.csv.

PROVEN rune-exact against the solved sections, from the keys sections.csv
records (tests/test_cipher.py): `atbash` (0.0), `shift_decrypt` (0.2),
`vigenere_decrypt`/`vigenere_encrypt` (0.1, 0.4), `phi_prime_decrypt` (0.13).

NOT PROVEN, because no solved section uses them: `autokey_pt_decrypt`,
`autokey_ct_decrypt`, `beaufort_decrypt`, `variant_beaufort_decrypt`,
`affine_decrypt`. They round-trip against this module's own encryption model
and nothing else. Where one also has to model the interrupter, that model is
a CHOICE -- see `autokey_pt_decrypt` -- so a sweep covers the choice it made,
not the cipher. Record the exact behavior in the result coverage.

THE INTERRUPTER, measured on 0.1, 0.4 and 0.13: where the PLAINTEXT rune is F
(index 0) the ciphertext is F and the keystream does NOT advance. A ciphertext
F anywhere else is an ordinary encryption -- 0.13 prints five and only
position 56 is a true interrupter -- so a ciphertext F is ambiguous during
decryption, and the interrupted positions are part of the key an attack must
search. `skips` is that set. Nothing here searches it: see
solver/search.py.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Iterator
from numbers import Integral

from solver.stats import as_indices

N = 29


def _norm_key(key: Iterable[int]) -> list[int]:
    values = list(key)
    if any(isinstance(value, bool) or not isinstance(value, Integral)
           for value in values):
        raise TypeError("key values must be integral")
    k = [int(value) % N for value in values]
    if not k:
        raise ValueError("empty key")
    return k


def _checked_text_and_skips(
    text: Iterable[int], skips: Iterable[int],
) -> tuple[list[int], frozenset[int]]:
    values = list(text)
    as_indices(values)
    positions = list(skips)
    if any(isinstance(i, bool) or not isinstance(i, Integral) for i in positions):
        raise TypeError("skip positions must be integral values")
    checked = frozenset(int(i) for i in positions)
    stray = {i for i in checked if not 0 <= i < len(values)}
    if stray:
        raise ValueError(
            f"skips outside 0..{len(values) - 1}: {sorted(stray)[:5]}"
        )
    return values, checked


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
    text, skips = _checked_text_and_skips(text, skips)
    out = []
    operation_validated = False
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
        value = op(x, k)
        if not operation_validated:
            if isinstance(k, bool) or not isinstance(k, Integral):
                raise TypeError(f"keystream yielded non-integral {type(k).__name__}")
            if isinstance(value, bool) or not isinstance(value, Integral):
                raise TypeError(
                    f"cipher operation returned non-integral {type(value).__name__}"
                )
            operation_validated = True
        out.append(value % N)
    return out


def repeat(key: Iterable[int]) -> Iterator[int]:
    """keyword -> endless keystream."""
    k = _norm_key(key)

    def cycling() -> Iterator[int]:
        while True:
            yield from k

    return cycling()


_PRIMES: list[int] = []
# Guards the extension block only. Two threads there together both append the
# same prime, the list goes non-monotonic, every later index shifts, and the
# cache stays poisoned for the process -- yielding a plausible rune stream
# that scores as noise and gets logged as disproved.
_PRIMES_LOCK = threading.Lock()


def primes() -> Iterator[int]:
    """2, 3, 5, 7, ... endlessly, from a module-level cache.

    Recomputing cost ~22 minutes across a 10k-hypothesis sweep, regenerating
    the same 13,000 primes. 0.13's keystream is fixed; nothing varies.
    """
    i = 0
    while True:
        # Read the common case without the lock -- list indexing is atomic
        # under the GIL and _PRIMES only ever grows -- and take it only to
        # extend, re-checking the length once inside.
        while i >= len(_PRIMES):
            with _PRIMES_LOCK:
                if i < len(_PRIMES):
                    break
                n = _PRIMES[-1] + 1 if _PRIMES else 2
                while not _is_prime(n):
                    n += 1
                _PRIMES.append(n)
        yield _PRIMES[i]
        i += 1


def _is_prime(n: int) -> bool:
    """Trial division by the primes found so far, stopping at sqrt(n).

    The `all(... if p * p <= n)` spelling reads the same but walks the whole
    list to filter: O(k^2), 1.7s against 0.09s for 13k primes.
    """
    for p in _PRIMES:
        if p * p > n:
            return True
        if n % p == 0:
            return False
    return True


def phi_primes() -> Iterator[int]:
    """phi(q_i) = q_i - 1 for the i-th prime: section 0.13's keystream."""
    return (p - 1 for p in primes())


# --------------------------------------------------------------------------
# Monoalphabetic
# --------------------------------------------------------------------------


# These take `skips` too: there is no keystream to hold, but an interrupted
# stretch is still part of what an attack searches. 0.0 and 0.2 have no
# interrupter, so the default is what the known-answer tests prove.


def shift_decrypt(ct: Iterable[int], k: int, skips=frozenset()) -> list[int]:
    if isinstance(k, bool) or not isinstance(k, Integral):
        raise TypeError("shift must be an integral value")
    ct, skips = _checked_text_and_skips(ct, skips)
    return [x if i in skips else (x - int(k)) % N for i, x in enumerate(ct)]


def atbash(text: Iterable[int], skips=frozenset()) -> list[int]:
    """Alphabet inversion i -> 28-i. Self-inverse; section 0.0's cipher."""
    text, skips = _checked_text_and_skips(text, skips)
    return [x if i in skips else (N - 1 - x) % N for i, x in enumerate(text)]


def affine_decrypt(ct: Iterable[int], a: int, b: int, skips=frozenset()) -> list[int]:
    """Invert c = a*p + b. 29 is prime, so any a in 1..28 works."""
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in (a, b)):
        raise TypeError("affine parameters must be integral values")
    a, b = int(a), int(b)
    if a % N == 0:
        raise ValueError(f"affine multiplier a={a} is 0 mod {N}; use 1..{N - 1}")
    ct, skips = _checked_text_and_skips(ct, skips)
    inv = pow(a, -1, N)
    return [x if i in skips else ((x - b) * inv) % N for i, x in enumerate(ct)]


# --------------------------------------------------------------------------
# Polyalphabetic, keyword-driven
# --------------------------------------------------------------------------


def vigenere_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """p = c - k. Sections 0.1 (DIVINITY) and 0.4 (FIRFUMFERENFE)."""
    return apply_stream(ct, repeat(key), lambda x, k: x - k, skips)


def vigenere_encrypt(pt, key, interrupter: int | None = 0) -> list[int]:
    """c = p + k, with the measured interrupter rule: a plaintext rune equal
    to `interrupter` passes through and the key holds. None disables."""
    pt = list(as_indices(pt))
    if interrupter is not None:
        interrupter = as_indices([interrupter])[0]
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
    # apply_stream reduces the operation result modulo N after validating the
    # raw stream value. Reducing here first converts bool to int and bypasses
    # that validation.
    return apply_stream(ct, iter(stream), lambda x, k: x - k, skips)


# --------------------------------------------------------------------------
# Autokey
# --------------------------------------------------------------------------


def autokey_pt_decrypt(ct, key, skips=frozenset()) -> list[int]:
    """Plaintext autokey: keystream is key ++ recovered plaintext.

    OPEN QUESTION, not a measurement. Where the keystream IS the plaintext,
    "the keystream holds" splits in two: (a) the interrupted rune neither
    consumes nor extends it -- implemented here, and `autokey_ct_decrypt`'s
    choice too; (b) it extends without consuming, so a later position keys off
    it. Different plaintext, and no solved section decides between them. A
    sweep with non-empty `skips` has covered (a) only; say so in `coverage`.
    """
    ct, skips = _checked_text_and_skips(ct, skips)
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

    Skipped ciphertext runes are left out of the keystream -- reading (a) of
    the open question in `autokey_pt_decrypt`, and equally unmeasured.

    `ct` is materialised because it is read twice -- once as the keystream,
    once as the text. Every primitive here takes an Iterable, so a generator
    or a map() must not come out as an empty decryption.
    """
    ct, skips = _checked_text_and_skips(ct, skips)
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
