# stock-analytics

한국투자증권(KIS) 시세와 OpenDART 재무제표를 수집하여 기술·재무 종합점수를 계산하고, 검증 가능한 백테스트를 수행하는 2차 분석 플랫폼입니다.

## V3.2 중첩검증·위험 오버레이

V3.1은 Champion으로 동결되며 V3.2가 이를 자동으로 덮어쓰지 않습니다. 모델 선택은
검증기간 이전의 purge/embargo 내부 폴드에서만 수행하고, 외부 검증기간은 선택 후 한 번만
평가합니다. 상세 내용은 `V3_2_UPGRADE.md`를 참조하세요.

```bat
python -m src.main ml-diagnose-v32 --horizon 20 --benchmark-code 069500 --validation-days 252 --test-days 126 --min-train-days 504 --fold-days 126 --embargo-days 20 --commission 0.015 --tax 0.18 --slippage 0.05 --stock-cap 0.15 --industry-cap 0.40 --rank-scope market --output-prefix ml_v32_h20
```

## V3.1 독립평가·앙상블

V3.1은 V3의 연구 컷오프와 봉인 레지스트리를 계승하면서 재무 신호와 가격·모멘텀
신호를 별도로 학습해 결합합니다. 겹치지 않는 20거래일 IC와 95% 신뢰구간, 폴드별
이중 벤치마크 성과, 포트폴리오 고정·반복 손실을 함께 검사합니다.

```bat
python -m src.main ml-diagnose-v31 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --rank-scope market --output-prefix ml_v31_h20
```

출처가 확인된 시점별 유니버스와 총수익지수가 있으면
`--universe-history-csv`, `--total-return-csv`, `--security-master-csv`를 추가합니다.
총수익지수의 전체 라벨 구간이 100% 채워진 경우에만 분할·배당·ETF 분배금을 반영한
총수익률로 학습·평가하며, 일부 자료는 원시 종가 라벨과 섞지 않습니다. 세부 입력
형식과 강화된 승인 기준은 `V3_1_UPGRADE.md`를 참고하세요.

## 범위

- 포함: 요청 기간 전체 일봉 수집, DART 재무제표 수집, 지표 계산, 재무·기술 종합점수, MA/RSI 전략 백테스트, SQLite 저장
- 제외: 실주문·자동매매·계좌 잔고 조회

## 빠른 시작

```bash
git clone <YOUR_GITHUB_URL> stock-analytics
cd stock-analytics
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에 KIS 및 DART 키를 입력한 뒤 아래 명령을 실행합니다.

```bash
python -m src.main collect-price 005930 --days 365
python -m src.main collect-financial 005930 --year 2025 --report-code 11011
# 매출 성장률까지 계산하려면 전년도 사업보고서도 한 번 수집합니다.
python -m src.main collect-financial 005930 --year 2024 --report-code 11011
python -m src.main analyze 005930
python -m src.main backtest 005930
python -m pytest -q
```

`--days 365`는 달력 기준 최근 365일입니다. KIS의 회당 조회 제한을 넘으면
가장 오래된 조회일을 이동하며 자동으로 추가 요청하고, 중복 일자는 한 번만 저장합니다.

종합점수는 기술 점수 40%, 재무 점수 60%로 계산합니다. 재무 점수에는 매출 성장률,
영업이익률, ROE, 부채비율, 영업현금흐름이 사용되며 결측 항목은 중립값으로 처리합니다.

## 재무 데이터 구조 업데이트

재무계정은 `account_id`, `fs_div`, `sj_div`를 함께 저장합니다. 구버전 데이터베이스가
발견되면 기존 표는 `financial_statements_legacy`로 보존되고 새 표가 자동 생성됩니다.
업데이트 직후에는 2024년과 2025년 사업보고서를 다시 수집해야 합니다. ROE는 기초·기말
평균자본을 사용하며, 핵심 계정 누락이나 비정상 비율은 분석 결과에 검증 경고로 표시됩니다.

## 3~5년 현실화 백테스트

```bash
# 최근 3년(달력 기준) 수집
python -m src.main collect-price 005930 --days 1095

# 최근 5년(달력 기준) 수집
python -m src.main collect-price 005930 --days 1825

# 기본 비용: 편도 수수료 0.015%, 매도 비용 0.18%, 편도 슬리피지 0.05%
python -m src.main backtest 005930 --capital 10000000

# 비용을 직접 지정하고 거래내역 저장
python -m src.main backtest 005930 --commission 0.015 --tax 0.18 --slippage 0.05 --export-csv backtest_005930.csv
```

전일 종가로 신호를 확정하고 다음 거래일 시가에 주문이 체결됩니다. 매매비용과
정수 주식 수, 잔여 현금, 매일의 평가자산을 반영합니다. 같은 기간의 비용 반영
매수 후 보유 전략을 벤치마크로 계산해 누적수익률·CAGR·초과수익률을 비교합니다.
세금과 수수료는 시장 및 증권사 조건에 맞게 명령행 옵션으로 조정할 수 있습니다.

## 개선 전략과 과최적화 방지

기본 전략은 MA20/MA120, 장기 이동평균 상승, 종가의 단기선 상회, RSI 45~68을
동시에 요구합니다. 기본 손절은 -7%, 익절은 +20%, 최소 보유기간은 5거래일이며
청산 이유가 거래 CSV에 기록됩니다.

```bash
python -m src.main backtest 005930 --capital 10000000 --export-csv improved_trades.csv
python -m src.main walk-forward 005930 --train-years 2 --test-months 12 --export-csv walk_forward_results.csv
```

워크포워드는 각 2년 학습구간에서 여러 MA·RSI·손절·익절 조합을 선택한 뒤,
바로 다음 12개월의 미사용 데이터에서만 평가합니다. 이후 학습·검증 창을 12개월씩
이동합니다. 선택 점수에는 CAGR뿐 아니라 샤프지수, MDD, 거래비용이 함께 반영됩니다.
미사용 구간 수익률, 성과 저하, 수익 구간 비율과 파라미터 안정성을 종합해
`통과` 또는 `보류`를 출력합니다. `통과`도 미래 수익을 의미하지 않으며 다른 종목과
더 긴 기간에서 반복 검증해야 합니다.

## 강건성 검증

```bash
python -m src.main robustness 005930 --simulations 5000 --output-prefix robustness_005930
```

다음 파일이 생성됩니다.

- `robustness_005930_sensitivity.csv`: 기준값 주변의 MA·RSI·손절·익절 민감도
- `robustness_005930_monte_carlo.csv`: 거래수익률 부트스트랩 결과
- `robustness_005930_yearly.csv`: 연도별 전략·벤치마크 수익률
- `robustness_005930_regime.csv`: 상승·하락·횡보 국면별 성과

몬테카를로는 완료 거래를 복원추출해 5,000개의 가능한 거래 경로를 만들고 수익률
5%·50%·95% 분위수, 손실 확률과 하위 5% MDD를 계산합니다. 민감도 검증은 기준
파라미터의 인접값 대부분에서도 수익과 초과수익이 유지되는지 확인합니다.

## 다종목 외부검증

```bash
python -m src.main external-verify 005930 000660 035420 005380 051910 105560 --days 1825 --export-csv multi_asset_results.csv
```

더 엄격한 종목별 워크포워드까지 실행하려면 다음 옵션을 추가합니다. 계산시간이
상당히 늘어날 수 있습니다.

```bash
python -m src.main external-verify 005930 000660 035420 005380 051910 105560 --days 1825 --with-walk-forward --export-csv multi_asset_walk_forward.csv
```

각 종목에 완전히 동일한 고정 전략과 거래비용을 적용해 전략·벤치마크 수익률,
MDD, 샤프지수, Profit Factor와 거래 횟수를 비교합니다. 워크포워드 판정은
절대수익, 벤치마크 초과, 위험조정 성과, 파라미터 안정성을 각각 분리하며 네 조건을
모두 충족해야 최종 `통과`가 됩니다.

## API 운영 안정화와 증분 수집

접근토큰은 `data/.kis_token_cache.json`에 만료시각과 함께 저장되고 앱키·서버가
같을 때만 재사용됩니다. 파일은 Git에서 제외됩니다. 403·429는 자동 반복하지 않고
한글 제한 메시지로 즉시 중단합니다.

```bash
# 한 종목: 저장 범위를 확인하고 부족한 앞·뒤 기간만 수집
python -m src.main collect-price 005930 --days 1825

# 수집 전용 다종목 명령
python -m src.main collect-multi 005930 000660 035420 005380 051910 105560 --days 1825

# API를 전혀 호출하지 않고 저장 자료만 검증
python -m src.main external-verify 005930 000660 035420 005380 051910 105560 --skip-collect --export-csv multi_asset_results.csv
```

기존 최소일이 요청 시작일 이전이고 최신일이 최근 4일 안이면 API를 자동 생략합니다.
부족하면 과거 앞부분과 최신 뒷부분만 요청합니다.

## 코어·전술 이중 전략

기본 자금의 35%는 상승장에서 장기 보유하는 코어, 65%는 추세 신호에 따라 움직이는
전술 자금입니다. 전술 포지션의 손절폭은 ATR 변동성에 따라 5~15% 범위에서 조정됩니다.
강한 상승 추세에서는 고정 익절을 사용하지 않고 ATR 기반 추적손절로 수익을 따라갑니다.
코어와 전술 거래비용은 모두 전체 자산곡선에 반영됩니다.

## 다종목 공통 파라미터와 통합 포트폴리오

종목별로 별도의 최적 파라미터를 선택하지 않습니다. 각 학습구간에서 모든 종목의
평균 위험조정 점수가 가장 높은 공통 파라미터 한 세트를 선택하고 다음 미사용구간의
모든 종목에 동일하게 적용합니다.

```bash
python -m src.main common-verify 005930 000660 035420 005380 051910 105560 \
  --industry 005930=반도체 --industry 000660=반도체 --industry 035420=인터넷 \
  --industry 005380=자동차 --industry 051910=화학 --industry 105560=금융 \
  --output-prefix common_multi_asset
```

Windows 한 줄 명령:

```bash
python -m src.main common-verify 005930 000660 035420 005380 051910 105560 --industry 005930=반도체 --industry 000660=반도체 --industry 035420=인터넷 --industry 005380=자동차 --industry 051910=화학 --industry 105560=금융 --output-prefix common_multi_asset
```

생성 파일:

- `common_multi_asset_folds.csv`: 종목별·구간별 공통 파라미터 OOS 성과
- `common_multi_asset_stocks.csv`: 종목별 워크포워드 누적 결과
- `common_multi_asset_industries.csv`: 업종별 성과
- `common_multi_asset_portfolio.csv`: 동일가중 통합 포트폴리오와 벤치마크 일별 곡선

통합 결과는 포트폴리오·벤치마크의 누적수익률, MDD와 샤프지수를 동일한 일별
동일가중 방식으로 비교합니다.

## 현실 포트폴리오와 최종 봉인평가

시장 ETF를 먼저 한 번 수집합니다. `069500`은 기본 벤치마크 코드이며 다른 ETF로
변경할 수 있습니다.

```bash
python -m src.main collect-multi 069500 --days 1825
```

6종목 월간 리밸런싱 예시:

```bash
python -m src.main portfolio-verify 005930 000660 035420 005380 051910 105560 --benchmark-code 069500 --industry 005930=반도체 --industry 000660=반도체 --industry 035420=인터넷 --industry 005380=자동차 --industry 051910=화학 --industry 105560=금융 --capital 100000000 --rebalance monthly --stock-cap 0.20 --sector-cap 0.35 --lockbox-months 12 --output-prefix realistic_portfolio
```

포트폴리오 규칙:

- 시장 ETF 강한 상승: 총 투자 95%, 코어 70%
- 일반 상승: 총 투자 75%, 코어 50%
- 횡보: 총 투자 45%, 코어 25%
- 하락: 총 투자 15%, 코어 5%
- 나머지는 현금
- ATR와 60일 변동성을 함께 사용한 역위험 비중
- 종목당 최대 20%, 업종당 최대 35%
- 정수 주식 수, 잔여 현금, 수수료·세금·슬리피지 반영
- 전술 물량은 ATR 추적손절 적용
- 월간 또는 분기 리밸런싱

마지막 12개월은 개발구간과 분리해 동일한 규칙으로 한 번만 평가합니다. 봉인구간에서
시장 ETF보다 수익률, MDD, 샤프지수가 모두 우수해야 `통과`가 됩니다.

생성 파일:

- `realistic_portfolio_development_equity.csv`
- `realistic_portfolio_development_trades.csv`
- `realistic_portfolio_development_allocations.csv`
- `realistic_portfolio_development_yearly.csv`
- `realistic_portfolio_lockbox_equity.csv`
- `realistic_portfolio_lockbox_trades.csv`
- `realistic_portfolio_lockbox_allocations.csv`
- `realistic_portfolio_lockbox_yearly.csv`

20~30종목도 같은 명령의 종목코드와 `--industry 코드=업종`을 추가해 확장합니다.

## 가치·품질·모멘텀 공통순위

현재 날짜의 PER·PBR·EPS·BPS·시가총액 스냅샷을 수집합니다.

```bash
python -m src.main collect-valuation 005930 000660 035420 005380 051910 105560
```

분기·반기·연간 재무제표와 실제 공시일을 수집합니다.

```bash
python -m src.main collect-financial-series 005930 000660 035420 005380 051910 105560 --start-year 2024 --end-year 2025
```

공통 종목점수:

- 품질 30%: ROE, 영업이익률, 매출성장률, 부채비율, 영업현금흐름
- 가치 25%: 업종 내 PER·PBR 순위, 배당수익률
- 모멘텀 25%: 3·6개월 수익률, 시장 ETF 대비 상대수익률
- 위험 20%: 60일 변동성, 6개월 낙폭

평가 보완 규칙:

- PER가 0 이하이면 적자기업으로 표시하고 저PER 순위에서 제외
- PER·PBR·부채비율·변동성은 낮을수록 높은 점수를 받도록 단조성 테스트로 검증
- 금융·은행·증권·보험은 제조업식 부채비율 대신 ROE·성장성·순이익 중심 평가
- 업종 표본이 3개 미만이면 업종 내 상대평가를 하지 않고 전체 유니버스 사용
- 가치지표가 7일을 초과하면 오래된 데이터 경고 표시
- 가치지표 상태와 전체 재무 데이터 신뢰도를 별도 열로 출력
- 업종 내 유효 양수 PER·PBR이 각각 3개 미만이면 해당 지표만 전체 유니버스로 전환
- 적자·ROE 0% 이하·신뢰도 80 미만·20일 평균 거래대금 10억원 미만은 매수 제외

공시일 이후에만 해당 재무자료를 사용하므로 미래 공시가 과거 스냅샷 점수에 섞이지
않습니다. 적자 또는 결측 PER은 중립값으로 처리합니다.

```bash
python -m src.main rank-universe 005930 000660 035420 005380 051910 105560 --benchmark-code 069500 --industry 005930=반도체 --industry 000660=반도체 --industry 035420=인터넷 --industry 005380=자동차 --industry 051910=화학 --industry 105560=금융 --export-csv daily_ranking.csv
```

## 주문 없는 일일 그림자 포트폴리오

```bash
python -m src.main shadow-run 005930 000660 035420 005380 051910 105560 --benchmark-code 069500 --industry 005930=반도체 --industry 000660=반도체 --industry 035420=인터넷 --industry 005380=자동차 --industry 051910=화학 --industry 105560=금융 --capital 100000000 --top-n 6 --rebalance-band 0.02 --min-order 500000 --stock-cap 0.20 --sector-cap 0.35 --output-prefix shadow
```

그림자 포트폴리오는 실제 주문 API를 호출하지 않습니다. 제안 수량을 내부 가상계좌에만
`SIMULATED_NO_ORDER`로 체결하고 다음 실행부터 평가손익을 누적합니다.

- 목표비중 차이가 2% 미만이면 거래 생략
- 주문금액 50만원 미만이면 거래 생략
- 매도 후 매수 순서로 현금 부족 방지
- 수수료·세금·슬리피지 개별 기록
- 종목·업종 제한 전후 목표비중 저장
- 전일 보유수량의 종목별 손익기여도
- 시장 상승 시 현금 기회비용, 시장 하락 시 현금 방어기여를 분리
- 제한 전후 비중과 다음 가격변화로 제약 기회비용 추정

운영 안정화:

- 최초 저장 거래일 직전의 공백이 주말뿐이면 KIS 조회를 생략
- KIS 5xx는 최대 3회만 재시도하고 403·429는 즉시 중단
- `collect-multi`는 한 종목의 5xx가 발생해도 다음 종목을 계속 처리
- 순위 CSV에 가치지표 날짜·상태·데이터 신뢰도 표시
- 같은 날짜 재실행 시 목표 편차가 리밸런싱 밴드 안이면 제안 0건

`--rebalance-band`는 독립 명령이 아니며 반드시 `shadow-run` 명령의 옵션으로
한 줄에 함께 입력합니다.

생성 파일:

- `shadow_daily_ranking.csv`: 가치·품질·모멘텀·위험 순위
- `shadow_trade_proposals.csv`: 실제 전송되지 않은 매수·매도 제안
- `shadow_positions.csv`: 가상 보유수량과 평균가격
- `shadow_performance.csv`: 미래 일별·누적성과와 시장 ETF 비교
- `shadow_attribution.csv`: 종목별 기여도·제약 기회비용·거래비용

매 거래일에는 먼저 가격과 가치 스냅샷을 증분 갱신한 뒤 `shadow-run`을 한 번 실행합니다.

같은 거래일에 다시 실행하면 기존 가상계좌와 성과를 그대로 반환하고, 거래·성과
재계산을 생략합니다.

## 20~30종목 CSV 유니버스

`config/universe_kr_24.example.csv`는 업종별 3개, 총 24개 종목을 넣은 편집용
예시입니다. 추천목록이 아니며, `enabled=false`로 종목을 제외할 수 있습니다.

```bash
python -m src.main collect-multi --universe-csv config/universe_kr_24.example.csv --days 1825
python -m src.main collect-valuation --universe-csv config/universe_kr_24.example.csv
python -m src.main collect-financial-series --universe-csv config/universe_kr_24.example.csv --start-year 2024 --end-year 2025
python -m src.main rank-universe --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500 --export-csv universe_24_ranking.csv
python -m src.main shadow-run --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500 --capital 100000000 --top-n 12 --rebalance-band 0.02 --min-order 500000 --stock-cap 0.10 --sector-cap 0.25 --output-prefix shadow_24
```

기존 6종목 기록과 24종목 기록을 분리하려면 포트폴리오 ID를 지정합니다.

```bash
python -m src.main shadow-run --universe-csv config/universe_kr_24.example.csv --portfolio-id shadow_24 --benchmark-code 069500 --capital 100000000 --top-n 12 --rebalance-band 0.02 --min-order 500000 --stock-cap 0.10 --sector-cap 0.25 --output-prefix shadow_24
```

- 구버전 단일 그림자 계좌는 자동으로 `default`에 복사됩니다.
- `default`와 `shadow_24`는 현금·보유수량·성과·거래제안이 완전히 분리됩니다.
- 동일 포트폴리오 ID와 동일 거래일만 중복 실행이 차단됩니다.
- 다른 포트폴리오 ID는 같은 날짜에도 독립된 신규 계좌로 시작할 수 있습니다.

등록된 그림자 계좌와 최신 성과 확인:

```bash
python -m src.main shadow-list
```

포트폴리오 누적 MDD·샤프·회전율·거래비용 확인:

```bash
python -m src.main shadow-report --portfolio-id shadow_24 --export-csv shadow_24_report.csv
```

## 전략 버전 고정과 일일 통합 실행

그림자 계좌는 전략 버전과 유니버스·벤치마크·초기자금·top-n·리밸런싱 밴드·
최소주문·종목/업종 한도·거래비용·최소 거래대금을 설정 해시로 저장합니다.
같은 포트폴리오 ID에 다른 설정을 사용하면 기존 성과 보호를 위해 실행을 차단합니다.
설정을 바꾸려면 새 `--portfolio-id`를 사용합니다.

가격·가치지표 수집, 그림자 실행, CSV 저장, 누적 리포트를 한 번에 실행:

```bash
python -m src.main daily-shadow --universe-csv config/universe_kr_24.example.csv --portfolio-id shadow_24_filtered --benchmark-code 069500 --capital 100000000 --top-n 12 --rebalance-band 0.02 --min-order 500000 --stock-cap 0.10 --sector-cap 0.25 --min-liquidity 1000000000 --output-prefix shadow_24_filtered
```

- 같은 날짜는 자동으로 중복 거래를 생략합니다.
- 오늘 가치지표가 이미 있으면 API 호출을 생략합니다.
- 한 종목 수집 실패 시 저장 데이터로 나머지 작업을 계속합니다.
- 종목별 최신 가격일이 다르면 공통 평가일과 날짜 경고를 출력합니다.
- 누적 거래일에 따라 준비(20일 미만), 초기 관찰(20~59일), 중간 검증
  (60~119일), 정식 평가(120일 이상) 단계를 표시합니다.

일일 안전장치:

- `daily-shadow`는 최근 7일 가격을 항상 다시 조회해 최신 거래일 지연을 방지
- 한국시간 평일 15:40 이전 실행 차단(`--allow-before-close`는 점검용)
- 모든 종목과 벤치마크의 최신 거래일이 같아야만 가상거래 실행
- 동일 포트폴리오의 동시 실행 잠금, 4시간 이상 된 비정상 잠금 자동 복구
- 성공·실패·평가일·수집행·오류를 `daily_run_logs`에 기록

최근 실행 상태:

```bash
python -m src.main daily-status --portfolio-id shadow_24_filtered --limit 10
```

머신러닝 준비도:

```bash
python -m src.main ml-readiness --universe-csv config/universe_kr_24.example.csv --portfolio-id shadow_24_filtered
```

지도학습은 최소 3년 가격, 120일 이상의 시점별 가치지표, 3개년 재무 데이터를
기본 준비 기준으로 확인합니다. 뉴스와 재무 데이터는 반드시 실제 공개시각을 보존해
예측 시점 이후 정보가 학습행에 들어가지 않도록 해야 합니다.

Windows 작업 스케줄러에서는 `scripts/run_daily_shadow.bat`를 평일 16:10 이후에
실행하도록 등록할 수 있습니다. 실제 주문 기능은 포함하지 않습니다.

- 당일 성공 기록이 있으면 가격 API를 호출하기 전에 전체 실행을 `SKIPPED` 처리합니다.
- 점검 목적으로 같은 날 다시 수집할 때만 `daily-shadow`에 `--force-refresh`를 추가합니다.
- 배치 파일의 화면 출력과 종료코드는 `logs/daily_shadow.log`에도 누적됩니다.

그림자 실행 결과에는 목표·실제 투자비중과 차이가 표시되고,
`shadow_24_skipped_orders.csv`에는 적격성 탈락, 최소 주문금액, 리밸런싱 밴드,
현금 부족 및 수량 변화 없음 등의 주문 제외 사유가 저장됩니다. 신규 계좌의 첫날은
비교 기준이 없으므로 현금 기회비용과 방어기여를 모두 0원으로 기록합니다.

CSV의 업종은 자동으로 사용되며, 명령행의 `--industry 코드=업종`이 CSV 값을
우선하여 덮어씁니다. 실제 운용 전에는 거래정지·관리종목·유동성 기준으로 목록을
검토해야 합니다.

## 시점 보존 Feature Store와 기준 머신러닝

이번 단계는 실제 주문이나 자동 투자판정이 아니라, 과거 시점에 알 수 있었던 정보만으로
기준 모델을 학습하고 검증하는 연구 파이프라인입니다. 24종목에 하나의 공통 모델을
적용하며 종목별 모델은 만들지 않습니다.

### 1. 의존성 업데이트

```bash
pip install -r requirements.txt
```

### 2. 과거 DART 재무자료 수집

기존 데이터베이스를 유지한 상태에서 2021~2025년 분기·반기·사업보고서를 채웁니다.
이미 저장된 행은 기본키 기준으로 갱신되며 중복되지 않습니다.
연결재무제표(CFS)가 없는 회사·연도는 별도재무제표(OFS)를 한 번 더 조회합니다.
Feature Store는 같은 연도에 CFS가 있으면 CFS를 우선하고, 없을 때만 OFS를 사용합니다.

```bash
python -m src.main collect-financial-series --universe-csv config/universe_kr_24.example.csv --start-year 2021 --end-year 2025
```

### 3. Feature Store와 미래수익 라벨 생성

```bash
python -m src.main build-feature-store --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500
```

저장 특징:

- 5·20·60·126거래일 수익률과 시장 대비 상대수익률
- 20·60일 변동성, RSI14, ATR14, 이동평균 괴리율, 거래대금
- KODEX 200 수익률·120일선 괴리·변동성·시장 국면
- 실제 DART 접수일 이후에만 연결한 성장률·영업이익률·ROE·부채비율·현금흐름
- DART 연간 EPS와 순이익에서 추정한 주식 수로 계산한 BPS 및 당시 가격 기준 PER·PBR
- 실제 저장된 KIS 가치 스냅샷은 해당 스냅샷 날짜 이후에만 별도 연결

`estimated_bps`와 `historical_per/pbr`은 DART 연간 EPS에서 역산한 주식 수를 사용한
연구용 복원값입니다. 유상증자·감자·주식분할이 있었던 기간에는 왜곡될 수 있으므로
KIS 실시간 스냅샷과 다른 열로 분리했습니다.

라벨:

- 5·20·60거래일 미래 종목 수익률
- 같은 기간 KODEX 200 수익률과 초과수익률
- 시장 초과 여부 분류값
- 해당 기간 중 최대 하락폭
- 라벨을 실제로 알 수 있게 된 미래 거래일 `label_available_at`

학습 분할 시 `label_available_at`이 다음 구간 시작일보다 앞선 행만 사용하므로, 구간
경계에서 미래 라벨이 학습 자료에 섞이는 문제도 차단합니다.

### 4. 기준 모델 학습과 봉인시험

```bash
python -m src.main ml-train --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --artifact models/baseline_h20.joblib --output-prefix ml_baseline_h20
```

- 개발 학습구간 → 모델 선택용 검증 126거래일 → 최종 봉인시험 126거래일 순서
- 로지스틱 회귀와 HistGradientBoosting 비교
- 검증구간 Brier score를 우선해 모델 선택
- 정확도·ROC-AUC·Brier score·상위 20% 예측의 실제 초과수익률 기록
- 봉인시험은 모델 선택에 사용하지 않음

생성 파일:

- `models/baseline_h20.joblib`: 두 기준 모델, 선택 모델, 특징 목록과 학습 기준일
- `ml_baseline_h20_metrics.csv`: 검증·봉인시험 성능
- `ml_baseline_h20_predictions.csv`: 표본별 확률과 실제 결과
- `ml_baseline_h20_metadata.json`: 기간·표본·모델 메타데이터

### 5. 확장형 워크포워드 검증

```bash
python -m src.main ml-walk-forward --horizon 20 --benchmark-code 069500 --min-train-days 504 --test-days 126 --output-csv ml_walk_forward_h20.csv
```

학습기간을 과거에서부터 확장하고 바로 다음 126거래일만 반복 평가합니다. 한 번의
봉인시험보다 여러 시장 국면에서 성능이 유지되는지 확인하는 용도입니다.

### 6. 최신 날짜 예측

매일 가격 수집 뒤 Feature Store를 갱신하고 학습된 모델로 확률을 계산합니다.

```bash
python -m src.main build-feature-store --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500
python -m src.main ml-predict --artifact models/baseline_h20.joblib --output-csv ml_latest_predictions.csv
```

확률은 향후 20거래일에 해당 종목이 KODEX 200을 초과할 모델 추정치입니다. 이것을
즉시 매수 신호로 사용하지 않고, 워크포워드와 그림자 실측이 충분히 누적될 때까지 기존
규칙 기반 순위와 나란히 비교합니다.

### 7. 준비도 재확인

```bash
python -m src.main ml-readiness --universe-csv config/universe_kr_24.example.csv --portfolio-id shadow_24_filtered
```

실시간 PER·PBR 스냅샷 120일은 계속 축적하지만 가격 기반 기준 모델의 필수조건은
아닙니다. 다음 뉴스 단계에서는 DART 이벤트를 접수시각 기준으로 먼저 추가하고, 이후
라이선스가 확인된 일반 뉴스의 게시시각·제목·요약·중복그룹·감성점수를 같은 구조에
연결합니다.

## ML 진단·비용 반영 포트폴리오 검증

기준 모델을 실전 신호에 연결하기 전에 다음 종합 진단을 실행합니다. 이 명령은 모델을
검증할 뿐 실제 주문을 만들지 않습니다.

```bash
python -m src.main ml-diagnose --universe-csv config/universe_kr_24.example.csv --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --portfolio-id shadow_24_filtered --start-year 2021 --end-year 2025 --output-prefix ml_diagnostic_h20
```

검증 원칙:

- Dummy prior, 로지스틱 회귀, HistGradientBoosting 비교
- 가격·시장 특징만, 재무 특징만, 가격+재무 특징 비교
- 검증기간 Brier score로 모델·특징군 선택
- 봉인시험은 선택에 사용하지 않음
- 모든 워크포워드 경계에서 `label_available_at < test_start`인 학습행만 사용
- 미래 20일 라벨이 다음 검증구간에 겹치지 않도록 purge 적용
- 20거래일 간격의 비중첩 리밸런싱으로 상위 10%·20%·30% 비교
- 편도 수수료 0.015%, 매도세 0.18%, 편도 슬리피지 0.05% 기본 적용
- 매 리밸런싱의 실제 종목 교체비중으로 회전율과 비용 계산

생성 파일:

- `ml_diagnostic_h20_metrics.csv`: 검증·봉인시험 성능과 Dummy 대비 Brier Skill Score
- `ml_diagnostic_h20_walk_forward.csv`: purge 적용 구간별 성능과 상위 20% 비용차감 성과
- `ml_diagnostic_h20_portfolios.csv`: 상위 10%·20%·30%와 KODEX 200 비교
- `ml_diagnostic_h20_calibration.csv`: 확률구간별 예측확률과 실제 적중률
- `ml_diagnostic_h20_feature_coefficients.csv`: 로지스틱 회귀 표준화 계수
- `ml_diagnostic_h20_by_year.csv`: 연도별 ROC-AUC·평균 초과수익
- `ml_diagnostic_h20_by_industry.csv`: 업종별 ROC-AUC·평균 초과수익
- `ml_diagnostic_h20_financial_items.csv`: 종목·연도·계정항목별 결측과 CFS/OFS 출처
- `ml_diagnostic_h20_feature_missingness.csv`: 종목·특징별 결측률
- `ml_diagnostic_h20_shadow_comparison.csv`: 기존 규칙 기반 그림자 계좌 실측 비교
- `ml_diagnostic_h20_verdict.json`: 자동 채택 판정과 비용 가정

자동 판정은 다음 다섯 조건을 모두 충족할 때만 `ADOPT`입니다.

1. 봉인시험 Brier score가 Dummy보다 우수
2. 워크포워드 평균 ROC-AUC가 0.5 초과
3. 상위 20% 포트폴리오의 비용차감 워크포워드 초과수익이 양수
4. 워크포워드 구간 과반수에서 상위 20% 비용차감 초과수익이 양수
5. 최종 봉인시험 상위 20% 비용차감 초과수익이 양수

하나라도 실패하면 `RESEARCH_ONLY`이며 ML 예측을 매수 신호로 연결하지 않습니다.
그림자 전략은 120거래일 미만이면 `OBSERVATION_ONLY`로 표시해 장기간 ML 백테스트와
동등한 성과로 오해하지 않도록 구분합니다.

금융주 보조수집 후에는 Feature Store와 진단을 다시 생성합니다.

```bash
python -m src.main collect-financial-series --universe-csv config/universe_kr_24.example.csv --start-year 2021 --end-year 2025
python -m src.main build-feature-store --universe-csv config/universe_kr_24.example.csv --benchmark-code 069500
python -m src.main ml-diagnose --universe-csv config/universe_kr_24.example.csv --output-prefix ml_diagnostic_h20
```

## 교정 ML 진단 v2: 독립 평가·시점별 유니버스·금융업 분리

기존 진단에서 발견된 봉인시험/워크포워드 중첩과 금융업 결측 패턴 의존을 교정하는
명령입니다. 기존 `ml-diagnose` 결과는 비교 기준선으로 보존하고 새 명령을 실행합니다.

Windows에서 기존 645개 경고가 재현되지 않도록 새 가상환경에는 검증 조합을 고정한
파일을 우선 사용합니다.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-lock.txt
set PYTHONWARNINGS=error
python -m pytest -q
```

검증 조합은 Python 3.12, NumPy 2.3.5, pandas 2.2.3, scikit-learn 1.8.0,
joblib 1.5.3입니다. 일반 범위 설치가 필요할 때만 `requirements.txt`를 사용합니다.

```bash
python -m src.main ml-diagnose-v2 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --lockbox-start 20260105 --rank-scope market --output-prefix ml_corrected_h20
```

`--lockbox-start`는 이미 확인한 봉인기간의 최초 거래일로 데이터베이스에 최초 1회
등록합니다. 같은 벤치마크·예측기간의 다음 실행에서 다른 날짜를 넣으면 실행을 거부하므로
최근 126일로 이동시킬 수 없습니다. 워크포워드는 모델 선택용 검증기간보다도 앞에서 종료되며,
각 학습 경계에서 `label_available_at < fold_start` 조건으로 20일 라벨을 purge합니다.

추가 교정 내용:

- 결측 표시 특징 포함/제거를 별도 후보로 비교
- 같은 날짜의 종목 간 백분위 순위로 특징 스케일 교정
- 금융업은 매출성장률·영업이익률·부채비율·영업현금흐름을 제외한 `bank_safe` 진단
- 금융업과 비금융업의 검증·봉인 성능 분리
- 시장 상승·중립·하락 국면별 성능 분리
- 상위 10%·20%·30%의 리밸런싱별 보유종목·기여도·집중도·회전율 출력
- 연구·그림자 전용 안전 상태 고정, 실제 주문 기능 없음

생성 파일:

- `ml_corrected_h20_metrics.csv`: 모델·특징군·결측 표시 제거 실험
- `ml_corrected_h20_walk_forward.csv`: 검증·봉인 이전 전용 워크포워드
- `ml_corrected_h20_portfolios.csv`: 비용 차감 상위 포트폴리오 성과
- `ml_corrected_h20_holding_contributions.csv`: 날짜·종목별 수익 기여
- `ml_corrected_h20_concentration.csv`: 종목 수·HHI·업종 집중·회전율
- `ml_corrected_h20_financial_nonfinancial.csv`: 금융/비금융 분리 성능
- `ml_corrected_h20_market_regimes.csv`: 시장 국면별 성능
- `ml_corrected_h20_universe_audit.csv`: 종목별 시점 적격성 적용 결과
- `ml_corrected_h20_independence_audit.csv`: 기간 독립성·purge·봉인 고정 검사
- `ml_corrected_h20_feature_coefficients.csv`: 최종 로지스틱 모델 계수
- `ml_corrected_h20_verdict.json`: 8개 필수 기준과 안전 상태

### 시점별 유니버스 이력 적용

`config/universe_history.template.csv`를 복사해 각 종목이 당시 투자 후보였다는 사실을
그 시점에 확인할 수 있었던 기간을 입력합니다.

```csv
code,eligible_from,eligible_to,selection_known_at,source
005930,20210104,20221229,20210104,보관한_2021년_유니버스_파일
```

- `eligible_from`, `eligible_to`: 포함 시작일과 종료일. 현재까지 포함이면 종료일 공란
- `selection_known_at`: 그 포함 사실을 당시 알 수 있었던 날짜
- `source`: 당시 구성표·보관 파일 등 검증 출처. 공란이면 검증 자료로 인정하지 않음

모든 원래 종목의 이력이 유효하게 채워진 파일만 다음처럼 적용합니다.

```bash
python -m src.main ml-diagnose-v2 --lockbox-start 20260105 --universe-history-csv config/universe_history.csv --output-prefix ml_corrected_h20
```

이 파일 없이 실행해도 나머지 교정 진단은 완료되지만
`point_in_time_universe_verified`는 미통과합니다. 가격 데이터의 최초 존재일만으로는
2026년에 고른 24종목의 과거 사후선정 편향이 해결되지 않기 때문입니다.

v2는 아래 8개 기준을 모두 통과할 때만 `ADOPT`입니다.

1. 워크포워드·검증·봉인시험 기간이 완전히 독립
2. 봉인시험 시작일을 데이터베이스에 변경 불가 상태로 등록
3. 과거 시점별 유니버스 이력 완전 검증
4. 봉인시험 Brier score가 Dummy보다 우수
5. 검증 이전 워크포워드 평균 ROC-AUC가 0.5 초과
6. 상위 20% 비용차감 워크포워드 초과수익이 양수
7. 워크포워드 구간 과반수에서 초과수익이 양수
8. 봉인시험 상위 20% 비용차감 초과수익이 양수

하나라도 실패하면 `RESEARCH_ONLY`입니다. 특히 시점별 유니버스 이력을 만들지 않은
상태에서 좋은 수익률이 나오더라도 실전 채택 판정은 불가능합니다.

## V3: 시점별 유니버스·수익률 감사·이중 벤치마크·모델 토너먼트

V3는 V2 결과를 보고 모델을 다시 고르는 방식이 아닙니다. V2 봉인기간을 모델 선택에
사용하지 않고, 검증기간에서 후보를 선택한 뒤 별도로 고정된 V3 봉인기간을 한 번만
평가합니다. 실제 주문 기능은 포함하지 않습니다.

비교 후보:

- Ridge, Elastic Net, HistGradientBoosting 회귀
- 20거래일 ETF 대비 초과수익 회귀
- 날짜별 횡단면 순위 학습
- 업종 중립 횡단면 순위 학습
- 단순 가치·품질·모멘텀·위험 팩터 기준선
- 가격 전용, 금융안전 재무 전용, 결합 특징군

금융·은행·증권·보험 행에는 일반기업용 매출성장률·영업이익률·부채비율·
영업현금흐름을 사용하지 않습니다. 모델 선발은 검증기간의 일별 순위 IC,
동일 유니버스 동일가중 대비 비용차감 초과수익, KODEX 200 대비 비용차감 초과수익,
IC 양수 날짜 비율을 함께 사용합니다.

```bash
python -m src.main ml-diagnose-v3 --horizon 20 --benchmark-code 069500 --validation-days 126 --test-days 126 --min-train-days 504 --fold-days 126 --commission 0.015 --tax 0.18 --slippage 0.05 --rank-scope market --output-prefix ml_v3_h20
```

첫 실행은 현재 자료로 연구 토너먼트만 수행하고 `--lockbox-start`를 넣지 않습니다.
이때 현재 라벨의 마지막 날짜가 V3 연구 컷오프로 DB에 기록됩니다. `20260105`부터 시작한
V2 기간은 이미 열어봤으므로 V3 신규 봉인시험으로 재사용할 수 없습니다. 이후 컷오프보다
뒤에서 시작하는 미관측 미래자료가 충분히 쌓였을 때만 `--lockbox-start`를 지정합니다.
최초 등록 후에는 같은 벤치마크·예측기간에서 날짜를 이동할 수 없습니다.

### V3 시점별 유니버스 형식

`config/universe_history_v3.template.csv`를 복사해 실제 과거 구성 이력과 출처를
입력합니다.

```csv
code,effective_from,effective_to,selection_known_at,listing_date,delisting_date,industry,liquidity_eligible,source
005930,20210104,20221229,20210104,19750611,,반도체,true,보관한_2021년_구성표
```

모든 원래 종목의 전체 관측기간이 유효한 이력 구간으로 덮여야 검증 완료로 인정합니다.
가격이 존재했다는 사실만으로는 당시 투자 후보였다고 인정하지 않습니다.

```bash
python -m src.main ml-diagnose-v3 --lockbox-start YYYYMMDD --universe-history-csv config/universe_history_v3.csv --output-prefix ml_v3_h20
```

생성 파일:

- `ml_v3_h20_model_tournament.csv`: 28개 ML 후보와 팩터 기준선의 검증 성과
- `ml_v3_h20_walk_forward.csv`: 검증·봉인 이전 구간별 순위 IC와 이중 벤치마크 성과
- `ml_v3_h20_dual_benchmark_portfolios.csv`: 상위 10·20·30% 누적성과
- `ml_v3_h20_portfolio_periods.csv`: 리밸런싱 날짜별 모델·동일유니버스·ETF 수익
- `ml_v3_h20_holding_contributions.csv`: 종목별 비용차감 기여도
- `ml_v3_h20_return_audit.csv`: 매수가·매도가·원시수익·라벨수익 대조
- `ml_v3_h20_universe_audit.csv`: 시점 이력 적용과 전체기간 커버리지
- `ml_v3_h20_independence_audit.csv`: 워크포워드·검증·봉인 독립성
- `ml_v3_h20_lockbox_predictions.csv`: 봉인시험 점수와 실제 사후수익
- `ml_v3_h20_verdict.json`: 11개 기준, 수익률 감사 상태, 안전 상태

현재 가격 표에는 배당과 기업행사 조정 여부를 독립 검증할 자료가 없습니다. 따라서 원시
종가 산술이 라벨과 일치해도 수익률 감사는 `ARITHMETIC_CHECKED_CORPORATE_ACTIONS_UNVERIFIED`
상태로 남으며, 배당·분할·병합 자료가 추가되기 전에는 `ADOPT`가 될 수 없습니다.

## Git 커밋 순서

```bash
git add .
git commit -m "feat: initialize stock analytics MVP"
git push -u origin main
```

API 키가 들어 있는 `.env`와 수집 데이터베이스는 `.gitignore`에 포함되어 커밋되지 않습니다.

## 데이터 주의사항

백테스트 결과는 과거 데이터의 계산 결과일 뿐이며, 미래 수익을 보장하지 않습니다. 신호 생성과 실주문은 분리해 두었으며, 주문 기능은 별도 검증 단계 후에 추가합니다.

## V3.2.1 evaluation/risk correction

V3.2.1 keeps V3.1 as Champion and does not introduce a new model. It applies one common risk overlay to Champion and Challengers, audits hard stock/industry/exposure limits on every interval, separates cumulative dual-benchmark outperformance from simultaneous period wins, adds Jaccard/turnover/fixation and single-outlier contribution stress tests, and upgrades the financial PIT audit to `FINANCIAL_DISCLOSURE_PIT_PARTIAL` vs `FULL_PIT_VERIFIED`. Research is frozen through 2026-07-09. See `V3_2_1_UPGRADE.md`.

## V3.2.1 Data Integrity Phase 2

Historical valuation snapshots can now be strictly validated/imported before rebuilding the feature store:

```bash
python -m src.main import-valuation-snapshots-v321 --csv config/valuation_snapshots_v321.csv
```

After import, rerun `build-feature-store`, then rerun `ml-diagnose-v321` with the historical universe, total-return and corporate-action CSV inputs. V3.2.1 also writes `<output-prefix>_selection_persistence_audit.csv` to distinguish unexplained stock fixation from repeated selection supported by subsequent excess returns.

The research boundary remains fixed at `2026-07-09`; data after `2026-07-09` must not be used to retune V3.2.1.

## V3.2.1 Phase 4.2 — resumable KRX acquisition

For annual chunking, timeout/retry, checkpoint/resume and progress-display usage, see `V3_2_1_HISTORICAL_DATA_PHASE4_2.md`.
