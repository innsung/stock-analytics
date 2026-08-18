# V3.2.1 Phase 5.75 Ambiguous KIND Notice Resolution

Ambiguous KIND notices are disambiguated using the explicit `회사명` field rather than substring membership. The company name, application date, and common-share notice title must all match before the selected notice is passed through the strict DART amount/record-date and KIND ex-date validator.

If KIND temporarily blocks a source document, all previously discovered official identifiers and the HTTP errors are retained in the candidate audit. The resolver fails closed until the exact company field can be read again.
