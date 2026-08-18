# Stock Analytics V3.2.1

한국 주식 데이터 수집, 재무·기술 분석, 기업행위 검증, 백테스트 및 ML 진단을 제공하는 V3.2.1 릴리스입니다.

## 현재 릴리스

- 버전: `V3.2.1`
- Python: 3.12
- 검증 기준: 전체 pytest 회귀 테스트
- 기업행위 원장: 399건
- 처리 가능한 미해결 큐: 0건

## 설치

```powershell
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
```

`.env.example`을 참고해 로컬 `.env`를 구성하세요. 비밀키와 토큰은 저장소에 커밋하지 않습니다.

## 실행

```powershell
python -m src.main --help
python -m src.main ml-diagnose-v321 --help
python -m pytest -q
```

## 구조

- `src/`: V3.2.1 애플리케이션 코드
- `tests/`: V3.2.1 자동 회귀 테스트
- `config/`: 안전한 템플릿과 예제 설정
- `database/`: 데이터베이스 연결 및 마이그레이션
- `scripts/`: 운영 스크립트
- `docs/V3_2_1_RELEASE.md`: 현재 릴리스 요약

과거 단계별 개발 문서와 이전 진단 실행기는 GitHub 최신 트리에서 제거했으며, 로컬 사전 정리 백업에 보존되어 있습니다.
