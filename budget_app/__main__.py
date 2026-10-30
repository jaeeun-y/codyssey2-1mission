import argparse
import sys
from pathlib import Path
from .decorators import timed
from .models import validate_date
from .service import BudgetService


def parser() -> argparse.ArgumentParser:
    # 하위 명령별 옵션을 이곳에서 모아 CLI 사용법과 검증을 구성합니다.
    p = argparse.ArgumentParser(prog="python -m budget_app", description="JSONL 기반 개인 가계부")
    p.add_argument("--data-dir", type=Path, default=Path("./data"), help="저장 폴더 (기본: ./data)")
    commands = p.add_subparsers(dest="command", required=True)
    commands.add_parser("add", help="거래를 대화형으로 추가")
    listing = commands.add_parser("list", help="최신순 거래 목록")
    listing.add_argument("--limit", type=int, default=20)
    search = commands.add_parser("search", help="조건으로 거래 검색")
    search.add_argument("--from", dest="start"); search.add_argument("--to", dest="end")
    search.add_argument("--category"); search.add_argument("--type", choices=("income", "expense"))
    search.add_argument("--q"); search.add_argument("--tag")
    summary = commands.add_parser("summary", help="월별 수입/지출 요약")
    summary.add_argument("--month", required=True); summary.add_argument("--top", type=int, default=5)
    budget = commands.add_parser("budget", help="월 예산 설정 또는 조회")
    sub = budget.add_subparsers(dest="budget_action", required=True)
    setp = sub.add_parser("set"); setp.add_argument("--month", required=True); setp.add_argument("--amount", required=True)
    sub.add_parser("list")
    category = commands.add_parser("category", help="카테고리 관리")
    csub = category.add_subparsers(dest="category_action", required=True)
    for action in ("add", "remove"):
        cp = csub.add_parser(action); cp.add_argument("name")
    csub.add_parser("list")
    update = commands.add_parser("update", help="거래 수정 (옵션 방식)")
    update.add_argument("--id", required=True)
    for flag in ("date", "type", "category", "amount", "memo", "tags"):
        update.add_argument("--" + flag, choices=("income", "expense") if flag == "type" else None)
    delete = commands.add_parser("delete", help="거래 삭제"); delete.add_argument("--id", required=True)
    imp = commands.add_parser("import", help="CSV 거래 가져오기"); imp.add_argument("--from", dest="source", required=True, type=Path)
    exp = commands.add_parser("export", help="조건에 맞는 거래를 CSV로 내보내기")
    exp.add_argument("--out", required=True, type=Path); exp.add_argument("--month")
    exp.add_argument("--from", dest="start"); exp.add_argument("--to", dest="end")
    return p


def ask(label: str, validate=lambda x: x, default: str | None = None) -> str:
    # 입력값이 유효해질 때까지 다시 묻고, 값이 없으면 기본값을 적용합니다.
    while True:
        value = input(f"{label}" + (f" [{default}]" if default else "") + ": ").strip()
        if not value and default is not None: return default
        try: return validate(value)
        except ValueError as exc: print(f"오류: {exc}")


def show(items) -> None:
    # 검색 결과가 비어 있는 경우에도 사용자가 알 수 있도록 안내합니다.
    found = False
    for t in items:
        found = True
        print(f"{t.date} | {t.type:7} | {t.category} | {t.amount:>12} | {t.memo} | tags={','.join(t.tags)} | id={t.id}")
    if not found: print("조건에 맞는 거래가 없습니다.")


@timed
def run(args: argparse.Namespace) -> None:
    # 파싱된 명령을 서비스 계층에 전달하고 결과를 CLI에 출력합니다.
    service = BudgetService(args.data_dir)
    cmd = args.command
    if cmd == "add":
        print("카테고리: " + ", ".join(service.category_names()))
        type_ = ask("타입 (income/expense)", lambda x: x if x in ("income", "expense") else (_ for _ in ()).throw(ValueError("income 또는 expense 입력")))
        date_ = ask("날짜 YYYY-MM-DD (빈칸=오늘)", validate_date, __import__("datetime").date.today().isoformat())
        category = ask("카테고리", lambda x: x if x in service.categories.read() else (_ for _ in ()).throw(ValueError("등록된 카테고리를 입력하세요")))
        amount = ask("금액", lambda x: str(__import__("budget_app.models", fromlist=["parse_amount"]).parse_amount(x)))
        memo = input("메모 (선택): ").strip(); tags = input("태그 (쉼표 구분, 선택): ").strip()
        item = service.create(type_, date_, amount, category, memo, tags)
        print(f"저장했습니다. 거래 id: {item.id}")
    elif cmd == "list":
        if args.limit < 1: raise ValueError("--limit은 1 이상이어야 합니다.")
        show(service.ordered()[:args.limit])
    elif cmd == "search": show(service.ordered(start=args.start, end=args.end, category=args.category, type=args.type, query=args.q, tag=args.tag))
    elif cmd == "summary":
        if args.top < 0: raise ValueError("--top은 0 이상이어야 합니다.")
        s = service.summary(args.month)
        if not s["count"]: print(f"{args.month}: 데이터 없음"); return
        print(f"{args.month} | 수입 {s['income']} | 지출 {s['expense']} | 잔액 {s['balance']}")
        ranked = sorted(s["categories"].items(), key=lambda pair: pair[1], reverse=True)[:args.top]
        print("카테고리별 지출 TOP: " + (", ".join(f"{k} {v}" for k, v in ranked) if ranked else "없음"))
        if s["budget"] is not None:
            pct = s["expense"] / s["budget"] * 100
            print(f"예산 {s['budget']} | 사용률 {pct:.1f}%")
            if pct > 100: print("경고: 월 예산을 초과했습니다!")
    elif cmd == "budget":
        if args.budget_action == "set": service.set_budget(args.month, args.amount); print(f"{args.month} 예산을 저장했습니다.")
        else:
            for month, amount in sorted(service.budgets.read().items()): print(f"{month}: {amount}")
    elif cmd == "category":
        if args.category_action == "list": print("\n".join(service.category_names()) or "등록된 카테고리가 없습니다.")
        elif args.category_action == "add": service.add_category(args.name); print(f"카테고리 '{args.name}'을(를) 추가했습니다.")
        else: service.remove_category(args.name); print(f"카테고리 '{args.name}'을(를) 삭제했습니다.")
    elif cmd == "update":
        changes = {key: getattr(args, key) for key in ("date", "type", "category", "amount", "memo", "tags") if getattr(args, key) is not None}
        if not changes: raise ValueError("수정할 항목을 --date, --type 등으로 지정하세요.")
        print("수정했습니다." if service.update(args.id, changes) else "해당 id의 거래가 없습니다.")
    elif cmd == "delete": print("삭제했습니다." if service.delete(args.id) else "해당 id의 거래가 없습니다.")
    elif cmd == "import": print(f"{service.import_csv(args.source)}건을 가져왔습니다.")
    elif cmd == "export":
        if not args.month and not (args.start and args.end): raise ValueError("--month 또는 --from과 --to를 함께 지정하세요.")
        count = service.export_csv(args.out, month=args.month, start=args.start, end=args.end)
        print(f"{count}건을 {args.out}에 내보냈습니다.")


def main() -> int:
    p = parser()
    try:
        args = p.parse_args()
        run(args)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        print("힌트: --help로 명령 형식을 확인하고, 카테고리는 먼저 등록하세요.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
