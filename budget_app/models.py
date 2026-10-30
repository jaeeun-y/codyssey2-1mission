"""가계부에서 사용하는 거래 객체와 입력값 검증을 정의합니다."""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import uuid


def parse_amount(value: str | int | float | Decimal) -> Decimal:
    # 부동소수점 오차를 피하고 저장·계산에 쓸 소수점 둘째 자리로 맞춥니다.
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("금액은 숫자로 입력하세요.") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("금액은 0보다 큰 값이어야 합니다.")
    return amount.quantize(Decimal("0.01"))


def validate_date(value: str) -> str:
    # ISO 날짜로 파싱해 실제 존재하는 날짜인지 확인합니다.
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc


def validate_month(value: str) -> str:
    # 해당 월의 1일을 날짜로 해석해 YYYY-MM 형식과 월 범위를 검증합니다.
    try:
        date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise ValueError("월은 YYYY-MM 형식이어야 합니다.") from exc
    return value


@dataclass(frozen=True)
class Transaction:
    """수입 또는 지출 한 건을 나타내는 변경 불가 객체입니다."""
    id: str
    type: str
    date: str
    amount: Decimal
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 생성 경로와 관계없이 객체가 항상 유효한 값만 갖도록 정규화합니다.
        if self.type not in {"income", "expense"}:
            raise ValueError("type은 income 또는 expense여야 합니다.")
        object.__setattr__(self, "date", validate_date(self.date))
        object.__setattr__(self, "amount", parse_amount(self.amount))
        if not self.category.strip():
            raise ValueError("카테고리를 입력하세요.")

    @classmethod
    def create(cls, type: str, date: str, amount: Decimal, category: str,
               memo: str = "", tags: tuple[str, ...] = ()) -> "Transaction":
        return cls(uuid.uuid4().hex[:12], type, date, amount, category, memo, tags)

    def to_dict(self) -> dict[str, Any]:
        # JSON에서 다룰 수 있도록 Decimal과 튜플을 문자열·목록으로 바꿉니다.
        result = asdict(self)
        result["amount"] = str(self.amount)
        result["tags"] = list(self.tags)
        return result

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Transaction":
        # 저장된 레코드를 다시 검증하면서 도메인 객체로 복원합니다.
        return cls(str(row["id"]), str(row["type"]), str(row["date"]),
                   parse_amount(row["amount"]), str(row["category"]),
                   str(row.get("memo", "")), tuple(row.get("tags", ())))
