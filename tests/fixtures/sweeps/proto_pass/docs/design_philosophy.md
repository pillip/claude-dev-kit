# Design Philosophy — Ledger Counter

## Signature Move

Every primary surface carries an offset ledger rule: `.signature-ledger-rule`
applies `box-shadow: -6px 12px 0 var(--ink-navy)` (token `--ink-navy: #1F3A5F`).
It must appear at least once on every screen.

## Reference Anchors

- adopted: docs/references/ledger-01.png — hairline column rules at 1px
- adopted: docs/references/ledger-02.png — mono numerals for order ids
- literal_quote: "47.2-A" — sample order ID, shown in mono on the order detail screen
- avoided: generic fintech gradient — reads as template
- avoided: glassmorphism cards — fights the paper-ledger metaphor
