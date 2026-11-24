"""--ignore-format statement-join test on a real reformatting sweep.

Django's auth 0001_initial.py between 3.2 and 5.0 is a black reformat of
every line plus exactly one real change (to_field='id' removed from the
Permission.content_type foreign key). With --code --ignore-format the
script joins lines into balanced statements before comparing, so the
rewrapped statements should no longer appear as Added/Removed, and the
report should get close to that single real change. Residual Changed
rows (implicit string concatenation, trailing commas) are printed, not
tuned away.

Run from the what-changed directory:

    python tests/test_ignore_format_join.py
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from what_changed import (DEFAULT_FLOOR, DEFAULT_THRESHOLD, MODEL_ID,
                          MODEL_REVISION, compare)


def bare(text):
    """Text without punctuation, for telling formatting residue from real change."""
    return re.sub(r"[\"',;:()\[\]\s]", "", text)


def main():
    here = pathlib.Path(__file__).parent / "fixtures"
    old_text = (here / "django_auth_0001_32.py").read_text(encoding="utf-8")
    new_text = (here / "django_auth_0001_50.py").read_text(encoding="utf-8")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION,
                                trust_remote_code=True)

    pairs = compare(old_text, new_text, model, DEFAULT_THRESHOLD,
                    DEFAULT_FLOOR, code_mode=True, ignore_format=True)

    from collections import Counter
    counts = Counter(p.label for p in pairs)
    changed = [p for p in pairs if p.label == "changed"]
    residue = [p for p in changed if bare(p.old) == bare(p.new)]
    real = [p for p in changed if bare(p.old) != bare(p.new)]
    print(f"counts: {dict(counts)}")
    print(f"Changed rows: {len(changed)} | real: {len(real)} | formatting residue: {len(residue)}")
    for p in real:
        print(f"  real [{p.reason}]")
        print(f"    old: {p.old[:110]}")
        print(f"    new: {p.new[:110]}")

    failures = []
    if counts["added"] or counts["removed"]:
        failures.append(f"rewrapped lines leaked: added {counts['added']}, removed {counts['removed']}")
    if len(real) != 1 or "to_field" not in (real[0].old + real[0].new):
        failures.append(f"expected exactly 1 real Changed row (to_field), got {len(real)}")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASS: no added/removed rows; the single real change is Caught, "
          f"{len(residue)} reformatting rows remain visible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
