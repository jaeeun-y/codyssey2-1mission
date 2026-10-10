"""Typed domain objects and validation."""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
import uuid


def parse_amount(value: str | int | float | Decimal) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("금액은 숫자로 입력하세요.") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("금액은 0보다 큰 값이어야 합니다.")
    return amount.quantize(Decimal("0.01"))


def validate_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc


def validate_month(value: str) -> str:
    try:
        date.fromisoformat(value + "-01")
    except ValueError as exc:
        raise ValueError("월은 YYYY-MM 형식이어야 합니다.") from exc
    return value


@dataclass(frozen=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: Decimal
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
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
        result = asdict(self)
        result["amount"] = str(self.amount)
        result["tags"] = list(self.tags)
        return result

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Transaction":
        return cls(str(row["id"]), str(row["type"]), str(row["date"]),
                   parse_amount(row["amount"]), str(row["category"]),
                   str(row.get("memo", "")), tuple(row.get("tags", ())))
