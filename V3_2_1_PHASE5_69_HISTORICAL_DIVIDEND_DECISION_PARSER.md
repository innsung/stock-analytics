# V3.2.1 Phase 5.69 Historical Dividend Decision Parser

OpenDART dividend-decision documents are decoded using their declared character encoding and parsed for common/preferred cash dividend per share, dividend record date, scheduled payment date, and board decision date.

Corrected filings can contain both old and corrected tables, so the parser retains the last populated value for each term. Parsed record dates remain audit evidence only: a record date is not automatically treated as the market ex-dividend date and therefore cannot be promoted into strict total-return evidence.

Run:

```text
python -m src.main parse-historical-dividend-decisions-v321
```
