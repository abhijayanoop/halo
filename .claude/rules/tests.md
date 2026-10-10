---
paths:
  - "tests/**/*.py"
  - "ui/**/*.test.{ts,tsx}"
---
# Test rules
- Test names describe behaviour: test_expired_item_never_returned.
- Mock only the edges (network, clock, filesystem), never the unit under test.
- Tests that call a real model are marked @pytest.mark.live.
- Use tests/fixtures/; never the real vault or ~/.halo.
- Cassettes must filter the Authorization header.
