"""배포 전 생성물과 날짜를 확인한다. 실패하면 기존 Pages를 덮어쓰지 않는다."""
import datetime as dt
import json
import re
from pathlib import Path

site = Path(__file__).resolve().parent / "site"
data = json.loads((site / "menu.json").read_text(encoding="utf-8"))
page = (site / "index.html").read_text(encoding="utf-8")
assert data["weeks"], "식단이 비어 있습니다"
assert dt.datetime.fromisoformat(data["generated"]).utcoffset() == dt.timedelta(hours=9)
for week in data["weeks"]:
    dates = [dt.date.fromisoformat(day["date"]) for day in week["days"]]
    assert len(dates) == 5 and len(set(dates)) == 5, "요일 칸이 잘못되었습니다"
    assert all((b - a).days == 1 for a, b in zip(dates, dates[1:])), "날짜가 연속되지 않습니다"
    assert any(day["meals"] or day["note"] for day in week["days"]), "메뉴가 없습니다"
embedded = re.search(r"const DATA = (.*?);\n", page, re.S)
assert embedded and json.loads(embedded[1].replace("<\\/", "</")) == data, "화면 데이터가 다릅니다"
assert "바탕 화면의" not in page, "PC용 안내가 남아 있습니다"
assert "/*__MENU_DATA__*/null" not in page
print(f"Verified {len(data['weeks'])} weeks; KST timestamp; matching HTML/JSON")
