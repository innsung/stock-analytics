# V3.2.1 Phase 5.56 — Subsidiary Action Document Acquisition

## Outcome

The 27 recent subsidiary, affiliate, and related-party action rows were matched
against the original OpenDART disclosure inventory using listed code, receipt
date, and whitespace-normalized report name.

- 25 rows had exactly one disclosure and their official documents were acquired.
- 2 rows were ambiguous because two same-day LG Chem disclosures share the same
  normalized title; neither was guessed or downloaded as a terminal match.
- No row was promoted to VERIFIED or NOT_APPLICABLE during acquisition.

Outputs:

- `data/raw/v321/events/subsidiary_action_document_acquisition_phase556_v321.csv`
- `data/raw/v321/events/subsidiary_action_documents_phase556/`
