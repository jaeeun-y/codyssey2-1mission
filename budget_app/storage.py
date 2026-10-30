import json
import os
from pathlib import Path
from typing import Any, Iterator
from .models import Transaction


class JsonlStore:
    """한 줄에 JSON 객체 하나를 저장하는 파일 저장소입니다."""
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

    def rows(self) -> Iterator[dict[str, Any]]:
        # 파일을 한 줄씩 읽어 큰 거래 내역도 한꺼번에 메모리에 올리지 않습니다.
        with self.path.open(encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"{self.path.name}:{line_no}의 JSON이 손상되었습니다.") from exc

    def replace(self, rows: Iterator[dict[str, Any]]) -> None:
        # 임시 파일을 완성한 뒤 교체해 쓰기 도중 원본이 손상되는 일을 줄입니다.
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
        finally:
            if temp.exists():
                temp.unlink()

    def append(self, row: dict[str, Any]) -> None:
        # 신규 레코드는 기존 내용을 다시 쓰지 않고 파일 끝에 추가합니다.
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


class TransactionRepository:
    """거래 객체와 JSONL 저장 형식 사이의 변환을 담당합니다."""
    def __init__(self, path: Path):
        self.store = JsonlStore(path)

    def iter_all(self) -> Iterator[Transaction]:
        for row in self.store.rows():
            yield Transaction.from_dict(row)

    def add(self, item: Transaction) -> None:
        self.store.append(item.to_dict())

    def find(self, item_id: str) -> Transaction | None:
        return next((item for item in self.iter_all() if item.id == item_id), None)

    def rewrite(self, items: Iterator[Transaction]) -> None:
        self.store.replace(item.to_dict() for item in items)


class KeyValueStore:
    """JSONL key/value records, kept in separate category and budget files."""
    def __init__(self, path: Path):
        self.store = JsonlStore(path)

    def read(self) -> dict[str, Any]:
        # 같은 키가 여러 번 나오면 파일에서 나중에 나온 값이 적용됩니다.
        result: dict[str, Any] = {}
        for row in self.store.rows():
            result[str(row["key"])] = row["value"]
        return result

    def write(self, values: dict[str, Any]) -> None:
        self.store.replace(iter({"key": key, "value": value} for key, value in values.items()))
