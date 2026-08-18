PHASE 5.18 — KIND SERVICE STATUS / RETRY QUEUE BRIDGE

새 파일
- src/ml/phase518_kind_retry_v321.py
- tests/test_phase518_kind_retry_v321.py

1) 압축을 C:\dev\stock-analytics 루트에 풉니다.

2) 회귀 테스트
python -m pytest -q

현재 130 passed 기준이면 새 테스트 3개가 추가되어 보통 133 passed가 예상됩니다.

3) DRY RUN
외부 KIND 요청 없이 현재 Phase 5.16 crosscheck CSV에서 acptNo/docNo가 얼마나 남아 있는지 확인합니다.

python -c "from src.ml.phase518_kind_retry_v321 import build_kind_retry_queue_v321; r=build_kind_retry_queue_v321(crosscheck_csv=r'data\raw\v321\events\kind_dividend_crosscheck_v321.csv',audit_csv=r'data\raw\v321\events\kind_dividend_fetch_audit_v321.csv',retry_queue_csv=r'data\raw\v321\events\kind_dividend_retry_queue_v321.csv',output_csv=r'data\raw\v321\events\kind_dividend_crosscheck_status_v321.csv',live_fetch=False); print(r)"

핵심 판정:
- NOT_FETCHED: docNo 식별 성공, 아직 네트워크 호출 안 함
- KIND_ID_UNAVAILABLE: Phase 5.16 결과에 docNo가 영속화되지 않음

4) LIVE FETCH
DRY RUN에서 NOT_FETCHED가 존재하면:

python -c "from src.ml.phase518_kind_retry_v321 import build_kind_retry_queue_v321; r=build_kind_retry_queue_v321(crosscheck_csv=r'data\raw\v321\events\kind_dividend_crosscheck_v321.csv',audit_csv=r'data\raw\v321\events\kind_dividend_fetch_audit_v321.csv',retry_queue_csv=r'data\raw\v321\events\kind_dividend_retry_queue_v321.csv',output_csv=r'data\raw\v321\events\kind_dividend_crosscheck_status_v321.csv',live_fetch=True); print(r)"

KRX 점검 중이면 KRX_SERVICE_UNAVAILABLE + retryable=True로 audit/retry queue에 분리됩니다.

5) 다음 단계
DRY RUN 결과가 대부분 KIND_ID_UNAVAILABLE이면 Phase 5.19에서
src/ml/phase516_kind_crosscheck_v321.py에 acptNo/docNo 영속화 컬럼을 직접 추가해야 합니다.
