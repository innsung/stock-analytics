# V3.2.1 Phase 5.70 Historical Dividend Ex-date Candidates

This phase removes duplicate corrective filings and maps each canonical dividend decision to the actual prior trading days present in the protected baseline price database.

The nearest prior trading day is only a search candidate. It is never promoted to a strict ex-date without an explicit official KRX/KIND market notice. Receipt dates are also checked against the candidate date so disclosures published after the candidate are separated as non-PIT observations.

Run:

```text
python -m src.main build-historical-dividend-exdate-candidates-v321
```
