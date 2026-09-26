# codyssey2-1mission

# JSONL 터미널 가계부

Python 표준 라이브러리만으로 만든 파일 기반 가계부입니다. Python 3.10 이상에서 저장소 폴더로 이동한 뒤 `python -m budget_app --help`를 실행하세요. 명령별 사용법은 `python -m budget_app COMMAND --help`로 확인할 수 있습니다. 처음 실행하면 `./data`와 저장 파일이 만들어지고 기본 카테고리(food, transport, housing, salary, other)가 등록됩니다. 저장 위치를 바꾸려면 전역 옵션을 명령 앞에 둡니다: `python -m budget_app --data-dir ./mydata list`.

## 저장 형식과 파일

기본 저장 위치는 실행 디렉터리의 `data/`입니다. 모든 데이터는 UTF-8 JSON Lines(JSONL)로 저장하며, 한 줄이 하나의 독립 JSON 객체입니다.

- `transactions.jsonl`: `id`, `type`, `date`, `amount`, `category`, `memo`, `tags`
- `categories.jsonl`: `key`, `value` (카테고리 이름)
- `budgets.jsonl`: `key`, `value` (월 `YYYY-MM`과 예산 금액)

이 세 파일은 거래, 카테고리, 예산을 분리해 영구 보관합니다. 거래 추가는 append 방식입니다. 수정·삭제·키/값 파일 갱신은 `.tmp` 임시 파일에 전체 내용을 쓴 다음 `os.replace`로 교체하여 중간 파일을 본 파일로 남기지 않습니다.

## 명령 예시

```text
python -m budget_app add
python -m budget_app list --limit 10
python -m budget_app search --from 2026-09-01 --to 2026-09-30 --category food --type expense --q 점심 --tag 회사
python -m budget_app summary --month 2026-09 --top 5
python -m budget_app budget set --month 2026-09 --amount 800000
python -m budget_app budget list
python -m budget_app category add books
python -m budget_app category list
python -m budget_app category remove books
python -m budget_app update --id abc123 --amount 12000 --memo 저녁
python -m budget_app delete --id abc123
python -m budget_app import --from transactions.csv
python -m budget_app export --out september.csv --month 2026-09
python -m budget_app export --out week.csv --from 2026-09-01 --to 2026-09-07
```

`add`는 날짜, 타입, 카테고리, 금액을 순서대로 대화형으로 입력받습니다. 날짜를 비우면 오늘 날짜를 사용합니다. 금액은 양수여야 하며 타입은 `income` 또는 `expense`입니다. 카테고리는 등록된 값만 선택할 수 있습니다. 메모와 쉼표로 나눈 태그는 선택 항목입니다. `update`는 옵션 방식으로 고정했습니다. 지정한 필드만 바뀝니다. 태그를 빈 문자열로 지정하면 태그를 비울 수 있습니다.

`search`의 모든 조건은 선택 사항이며 함께 사용하면 AND 조건으로 적용됩니다. `--from`과 `--to`는 양끝 날짜를 포함합니다. `summary`에는 총수입, 총지출, 잔액, 지출 카테고리 TOP N이 나옵니다. 예산이 있으면 사용률과 100% 초과 경고도 표시합니다. 거래가 없는 달은 `데이터 없음`이라고 표시합니다. 거래가 사용 중인 카테고리는 삭제할 수 없습니다.

## CSV 가져오기/내보내기 스키마

가져오기 CSV는 UTF-8 또는 UTF-8 BOM으로 읽습니다. 첫 행 헤더에 필수 열 `date,type,category,amount`를 포함해야 합니다. `memo`, `tags`는 선택 열이며, 태그는 쉼표로 구분합니다. `id` 열은 가져오지 않고 새 ID를 발급합니다.

```csv
date,type,category,amount,memo,tags
2026-09-12,expense,food,12000,점심,"회사,식사"
2026-09-15,income,salary,3000000,급여,
```

실제 위 예시에서 `tags` 값 안에 쉼표를 쓸 때는 CSV 규칙에 따라 해당 칸을 큰따옴표로 감싸야 합니다(예: `"회사,식사"`). 내보내기 헤더는 `id,date,type,category,amount,memo,tags`입니다. 가져온 거래의 카테고리가 등록되지 않았거나 필드 형식이 잘못되면 오류가 표시됩니다. 내보내기에는 `--month YYYY-MM` 또는 `--from YYYY-MM-DD --to YYYY-MM-DD` 조건이 필요합니다.

## 구조와 설계 설명

- `models.py`: `Transaction` dataclass가 거래 필드와 날짜/금액/타입 유효성을 책임집니다. `Decimal`을 써서 금액 연산에서 부동소수점 오차를 피합니다. 함수 시그니처의 타입 힌트는 각 계층이 주고받을 데이터 계약을 드러냅니다.
- `storage.py`: JSONL 한 줄씩 읽는 `rows()` 제너레이터와 거래 저장소, 키/값 저장소를 둡니다. 제너레이터는 파일 전체를 메모리에 올리지 않고 다음 행을 필요할 때 읽습니다. 필터링과 요약도 저장소의 레코드를 순회합니다. 목록의 최신순 정렬은 정렬 자체가 필요하므로 일치한 거래를 모아 메모리에서 정렬합니다.
- `service.py`: 카테고리 검증, CRUD, 검색, 요약, 예산, CSV 변환을 담당합니다. CLI나 화면 출력 로직은 포함하지 않습니다.
- `__main__.py`: `argparse` 명령/옵션을 정의하고 입력 및 결과를 출력합니다. `update`는 옵션 기반입니다. 오류는 이유와 간단한 해결 힌트를 출력하고 0이 아닌 종료 코드를 돌려줍니다.
- `decorators.py`: `@timed` 데코레이터가 CLI 실행 시간을 공통 출력합니다. 데코레이터는 명령의 핵심 로직과 공통 관심사를 분리합니다.

새 기능은 입력/출력 옵션은 CLI에, 업무 규칙은 서비스에, 파일 표현은 저장소에 추가하면 각 책임을 따라 확장할 수 있습니다. 제너레이터는 데이터 양이 커져도 읽기 단계에서 파일 전체 크기만큼의 메모리를 요구하지 않지만, 최신순 전역 정렬은 모든 일치 거래를 필요로 하므로 이 구현에서는 그 결과 집합만 메모리에 둡니다.