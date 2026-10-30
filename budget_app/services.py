import csv
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Iterator
from .models import Transaction, parse_amount, validate_date, validate_month
from .storage import KeyValueStore, TransactionRepository


class BudgetService:
    """거래, 카테고리, 예산에 대한 가계부 업무 규칙을 제공합니다."""
    def __init__(self, data_dir: Path):
        # 저장 파일을 준비하고 카테고리가 비어 있을 때 기본 항목을 등록합니다.
        self.data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = KeyValueStore(data_dir / "categories.jsonl")
        self.budgets = KeyValueStore(data_dir / "budgets.jsonl")
        if not self.categories.read():
            self.categories.write({name: name for name in ("food", "transport", "housing", "salary", "other")})

    def category_names(self) -> list[str]:
        return sorted(self.categories.read())

    def add_category(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("카테고리 이름을 입력하세요.")
        values = self.categories.read()
        if name in values:
            raise ValueError("이미 등록된 카테고리입니다.")
        values[name] = name
        self.categories.write(values)

    def remove_category(self, name: str) -> None:
        # 거래에서 사용 중인 카테고리는 남겨 참조가 끊기지 않게 합니다.
        if any(t.category == name for t in self.transactions.iter_all()):
            raise ValueError("이 카테고리를 사용하는 거래가 있어 삭제할 수 없습니다.")
        values = self.categories.read()
        if name not in values:
            raise ValueError("카테고리를 찾을 수 없습니다.")
        del values[name]
        self.categories.write(values)

    def create(self, type: str, date: str, amount: str, category: str,
               memo: str = "", tags: str = "") -> Transaction:
        if category not in self.categories.read():
            raise ValueError(f"등록되지 않은 카테고리입니다: {category} (category add로 등록하세요)")
        item = Transaction.create(type, date, parse_amount(amount), category, memo,
                                  tuple(x.strip() for x in tags.split(",") if x.strip()))
        self.transactions.add(item)
        return item

    def iter_filtered(self, start: str | None = None, end: str | None = None,
                      category: str | None = None, type: str | None = None,
                      query: str | None = None, tag: str | None = None,
                      month: str | None = None) -> Iterator[Transaction]:
        if start: validate_date(start)
        if end: validate_date(end)
        if month: validate_month(month)
        # 조건을 하나라도 만족하지 않는 거래는 건너뛰어 결과만 순회합니다.
        for item in self.transactions.iter_all():
            if start and item.date < start or end and item.date > end: continue
            if month and not item.date.startswith(month): continue
            if category and item.category != category: continue
            if type and item.type != type: continue
            if query and query.casefold() not in item.memo.casefold(): continue
            if tag and tag not in item.tags: continue
            yield item

    def ordered(self, **filters: str | None) -> list[Transaction]:
        # 원본은 스트리밍으로 읽지만 최신순 출력에는 검색 결과 정렬이 필요합니다.
        return sorted(self.iter_filtered(**filters), key=lambda t: (t.date, t.id), reverse=True)

    def delete(self, item_id: str) -> bool:
        if not self.transactions.find(item_id): return False
        self.transactions.rewrite(t for t in self.transactions.iter_all() if t.id != item_id)
        return True

    def update(self, item_id: str, changes: dict[str, str | None]) -> bool:
        if not self.transactions.find(item_id): return False
        category = changes.get("category")
        if category and category not in self.categories.read():
            raise ValueError(f"등록되지 않은 카테고리입니다: {category}")
        # 수정 대상 외의 거래는 그대로 흘려보내고 대상 거래만 새 객체로 만듭니다.
        def updated() -> Iterator[Transaction]:
            for t in self.transactions.iter_all():
                if t.id != item_id:
                    yield t
                else:
                    tags = changes.get("tags")
                    yield replace(t,
                        date=validate_date(changes["date"]) if changes.get("date") else t.date,
                        type=changes.get("type") or t.type,
                        category=category or t.category,
                        amount=parse_amount(changes["amount"]) if changes.get("amount") else t.amount,
                        memo=changes.get("memo") if changes.get("memo") is not None else t.memo,
                        tags=tuple(x.strip() for x in tags.split(",") if x.strip()) if tags is not None else t.tags)
        self.transactions.rewrite(updated())
        return True

    def set_budget(self, month: str, amount: str) -> None:
        validate_month(month)
        budgets = self.budgets.read(); budgets[month] = str(parse_amount(amount)); self.budgets.write(budgets)

    def summary(self, month: str) -> dict[str, object]:
        # 월별 합계와 지출 카테고리 합계를 한 번의 거래 순회로 계산합니다.
        validate_month(month)
        totals = {"income": Decimal(0), "expense": Decimal(0)}
        by_category: defaultdict[str, Decimal] = defaultdict(Decimal)
        count = 0
        for t in self.iter_filtered(month=month):
            count += 1; totals[t.type] += t.amount
            if t.type == "expense": by_category[t.category] += t.amount
        budget = self.budgets.read().get(month)
        return {"count": count, "income": totals["income"], "expense": totals["expense"],
                "balance": totals["income"] - totals["expense"], "categories": by_category,
                "budget": Decimal(budget) if budget else None}

    def import_csv(self, path: Path) -> int:
        # 필수 열을 확인한 뒤 각 행을 일반 거래 생성 경로로 검증·저장합니다.
        added = 0
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            required = {"date", "type", "category", "amount"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("CSV 헤더에 date,type,category,amount 열이 필요합니다.")
            for row in reader:
                self.create(row["type"], row["date"], row["amount"], row["category"],
                            row.get("memo", "") or "", row.get("tags", "") or "")
                added += 1
        return added

    def export_csv(self, path: Path, **filters: str | None) -> int:
        # 필터 결과를 UTF-8 BOM 형식으로 기록해 스프레드시트에서 한글을 보존합니다.
        items = self.ordered(**filters)
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id", "date", "type", "category", "amount", "memo", "tags"])
            writer.writeheader()
            for t in items:
                writer.writerow({"id": t.id, "date": t.date, "type": t.type, "category": t.category,
                                 "amount": str(t.amount), "memo": t.memo, "tags": ",".join(t.tags)})
        return len(items)
