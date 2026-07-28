# AI Media Pipeline Economics Audit — 한국어 안내

AI 영상·오디오·대본 파이프라인의 **실제 비용, 토큰, 캐시, 재시도 낭비와 품질 합격 산출물당 비용**을 증거 기반으로 계산하는 공개 커널입니다.

핵심은 단순한 “총 토큰”이 아닙니다.

> **품질 게이트를 통과한 산출물 1개를 만드는 데 정확히 얼마가 들었는가?**

## 공개 범위

이 저장소에는 다음만 들어 있습니다.

- 비용·토큰·캐시 receipt 스키마
- 안전한 JSONL 검증기
- 재시도·실패·중복 성공 호출 탐지
- 운영 정책 대비 provider/model/attempt/cost 감사
- 합격 산출물당 단위원가 계산
- baseline/candidate 비교기
- 결정론적 JSON·Markdown·SHA-256 산출물
- 무네트워크 synthetic demo와 테스트

다음은 포함하지 않습니다.

- `happyVideoFactory` 운영 코드
- 강남신사·웹툰·숏드라마 프롬프트
- 계정·채널·고객 데이터
- YouTube/TikTok 업로드 자동화
- 브라우저 세션·쿠키·토큰
- 실제 가격표와 환율 추정
- 비공개 품질 corpus와 creative policy

## 빠른 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
make check
make audit-demo
```

tracked synthetic 비교 결과는 exact cost 1.420000 USD → 0.790000 USD, 합격 산출물 2개 유지, non-cached input tokens 52,500 → 17,500입니다. 이 수치는 도구 검증용 합성 fixture이며 실제 운영 절감 실적이 아닙니다.

실제 절감 주장은 다음 조건을 모두 만족해야 합니다.

1. baseline과 candidate의 exact-cost coverage가 모두 100%
2. 동일한 artifact ID·kind·gate 계약 유지
3. candidate 품질 점수가 baseline보다 낮아지지 않음
4. high/critical finding이 증가하지 않음
5. candidate exact cost가 실제로 감소

## 데이터 안전선

입력 event에는 raw prompt, response, script, transcript, URL, 절대경로, credential, cookie, account/customer 식별자를 넣을 수 없습니다. validator가 이를 입력 단계에서 거부합니다. 원문 대신 SHA-256 fingerprint와 허용된 정량 필드만 기록합니다.

## 감사 결과 해석

- `exact`: provider 또는 검증된 host receipt와 hash가 있음
- `estimated`: 명시적 estimator가 만든 값
- `unknown`: 측정하지 못함. 0으로 취급하지 않음
- `not_applicable`: 해당 측정이 적용되지 않음

네 상태는 하나의 총액으로 합쳐지지 않습니다. exact coverage가 불완전하면 합격 산출물당 비용도 `N/A`로 표시됩니다.

자세한 내용은 영어 [README](README.md)와 [방법론](docs/methodology.md)을 참고하십시오.
