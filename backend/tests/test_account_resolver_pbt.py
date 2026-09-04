"""Property test — resolver header format (Task 1.7, Property 1).

Feature: account-scoped-chat-and-isolation.
Property 1: Account header format resolution.
Validates: Requirements R2.1, R2.3.

For all strings s, resolve_account(s) returns s if and only if s matches
^acct-[0-9a-f]+$, and otherwise rejects with 401 without touching any data
(the resolver performs no data access on any path).
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from fastapi import HTTPException

from account import ACCOUNT_RE, resolve_account


def _matches(s: str | None) -> bool:
    return bool(s) and bool(ACCOUNT_RE.match(s))


# Arbitrary text: covers valid ids, near-misses, unicode, whitespace, empties.
_arbitrary = st.text()

# Constrained generator that produces exactly-valid ids so the "accept" branch
# is exercised densely, not just by luck.
_valid = st.builds(lambda body: f"acct-{body}", st.text(alphabet="0123456789abcdef", min_size=1))


@settings(max_examples=150)
@given(st.one_of(_arbitrary, _valid, st.none()))
def test_resolve_account_matches_regex_iff_accepted(s):
    if _matches(s):
        assert resolve_account(s) == s
    else:
        try:
            resolve_account(s)
            raised = False
        except HTTPException as exc:
            raised = True
            assert exc.status_code == 401
        assert raised, f"expected 401 for non-matching value: {s!r}"


@settings(max_examples=150)
@given(_valid)
def test_valid_ids_returned_unchanged(s):
    assert resolve_account(s) == s
