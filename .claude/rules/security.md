---
paths:
  - "src/halo/security/**"
  - "src/halo/tools/**"
  - "src/halo/models/**"
---
# Security rules
- Any value derived from untrusted content is Tainted[T] until the Reader's schema has validated it,
  and it stays Tainted afterwards.
- Every tool declares its risk level and which arguments may accept tainted values.
- High-risk tools (delete files, send messages, spend money, git merge or push) always ask;
  they can never be set to "always allow".
- Every new tool gets a test in tests/security/.
