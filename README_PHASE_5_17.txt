# Phase 5.17 - KIND Failover Safe Handling

포함 파일:
- src/kind_service.py
- tests/test_kind_service.py

적용:
ZIP을 `C:\dev\stock-analytics` 루트에 풀어서 동일 경로에 파일을 추가합니다.

테스트:
python -m pytest -q

실제 KIND 상태 확인:
python -c "from src.kind_service import fetch_kind_print_document; r=fetch_kind_print_document('20260527001263',acpt_no='20260527000541'); print('STATUS:',r.status.value); print('HTTP:',r.status_code); print('RETRYABLE:',r.retryable); print('FINAL_URL:',r.final_url); print('ERROR:',r.error)"

KRX 점검 중 예상:
STATUS: KRX_SERVICE_UNAVAILABLE
HTTP: 200
RETRYABLE: True
