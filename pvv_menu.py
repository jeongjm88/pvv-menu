"""판교세븐벤처밸리 구내식당 식단표 PDF를 받아 웹페이지로 만든다.

사용법:
    python pvv_menu.py              # 최신 식단으로 site/index.html, site/menu.json 생성
    python pvv_menu.py --open       # 생성 후 브라우저로 열기 (받기 실패해도 이전 페이지는 연다)
    python pvv_menu.py --pdf a.pdf  # 로컬 PDF 파싱 결과만 JSON으로 출력 (테스트용)

필요: pip install pymupdf
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import fitz  # PyMuPDF

BASE = "http://www.pvv.co.kr/bbs/"
LIST_URL = BASE + "index.php?page=1&code=bbs_menu01"
HERE = Path(__file__).resolve().parent

MEAL_RE = re.compile(r"^[조중석]\s*식$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
DATE_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일\s*\((.)\)")
CLOSED_RE = re.compile(r"운영\s*없음|미운영|휴무|휴일|연휴|공휴일|한글날|개천절|광복절|성탄|설날|추석")
JUNK_RE = re.compile(r"^(이달의|메뉴|이달의\s*메뉴)$")   # 병합 셀 장식 문구


def _is_closure(t):
    return bool(CLOSED_RE.search(t) or JUNK_RE.search(t))


def _clean(t):
    return re.sub(r"^[-★☆\s]+|[-★☆\s]+$", "", t)


# ---------------------------------------------------------------- 게시판

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def list_posts():
    """게시판 첫 페이지의 식단표 글 목록 (최신순)."""
    page = fetch(LIST_URL).decode("euc-kr", errors="replace")
    posts = []
    for row in re.findall(r"<tr.*?</tr>", page, re.S):
        m = re.search(r'bbsView\.php\?id=(\d+)[^"]*">\s*(.*?)</a>', row, re.S)
        f = re.search(r"href='(download\.php\?[^']+\.pdf)'", row, re.I)
        d = re.search(r"(\d{4}-\d{2}-\d{2})", row)
        if not (m and f):
            continue
        # 파일명은 EUC-KR 퍼센트 인코딩이어야 서버가 찾는다
        href = f.group(1)
        prefix, fname = href.split("filename=", 1)
        href = prefix + "filename=" + urllib.parse.quote(fname, encoding="euc-kr", safe="()")
        posts.append({
            "id": int(m.group(1)),
            "title": html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip(),
            "posted": d.group(1) if d else None,
            "pdf_url": BASE + href,
            "view_url": BASE + f"bbsView.php?id={m.group(1)}&code=bbs_menu01",
        })
    posts.sort(key=lambda p: p["id"], reverse=True)
    return posts


# ---------------------------------------------------------------- PDF 파싱

def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if t:
                x0, y0, x1, y1 = ln["bbox"]
                out.append({"t": t, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                            "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2})
    return out


def _hlines(page):
    """가로 괘선 (x0, x1, y). 엑셀 PDF는 얇은 검은 사각형으로 선을 그린다."""
    res = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "re":
                r = it[1]
                if r.height < 2 and r.width > 20:
                    res.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
            elif it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 0.5 and abs(a.x - b.x) > 20:
                    res.append((min(a.x, b.x), max(a.x, b.x), a.y))
    return res


def _vlines(page):
    """세로 괘선 (x, y0, y1)."""
    res = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "re":
                r = it[1]
                if r.width < 2 and r.height > 5:
                    res.append(((r.x0 + r.x1) / 2, r.y0, r.y1))
            elif it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.x - b.x) < 0.5 and abs(a.y - b.y) > 5:
                    res.append((a.x, min(a.y, b.y), max(a.y, b.y)))
    return res


def _cuts(hlines, x, top, bottom):
    """x 위치를 가로지르는 가로선들의 y (top~bottom 범위, 중복 제거)."""
    ys = sorted(y for x0, x1, y in hlines if x0 - 1 <= x <= x1 + 1 and top - 2 <= y <= bottom + 2)
    merged = []
    for y in ys:
        if not merged or y - merged[-1] > 3:
            merged.append(y)
    return merged


def _bands(cuts):
    return list(zip(cuts, cuts[1:]))


def _featured_regions(page, lines):
    """Excel 배지의 숨은 텍스트 좌표 대신 실제 파란 삼각형 위치를 사용한다."""
    if not any("이달의" in l["t"] for l in lines):
        return []
    regions = []
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        rect = drawing["rect"]
        if (drawing.get("type") == "f" and fill and len(fill) == 3
                and fill[0] < .2 and .4 < fill[1] < .85 and fill[2] > .8
                and 15 < rect.width < 65 and 15 < rect.height < 65
                and len(drawing["items"]) == 3
                and all(item[0] == "l" for item in drawing["items"])):
            regions.append(((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2))
    return regions


def parse_pdf(data: bytes, year_hint: int | None = None) -> dict:
    page = fitz.open(stream=data, filetype="pdf")[0]
    lines = _lines(page)
    hl = _hlines(page)
    featured_regions = _featured_regions(page, lines)

    # 날짜 헤더 → 요일 칸
    heads = sorted((l for l in lines if DATE_RE.search(l["t"])), key=lambda l: l["cx"])
    if not heads:
        raise ValueError("날짜 헤더를 찾지 못했습니다")
    header_bottom = max(l["y1"] for l in heads)
    col_w = (heads[-1]["cx"] - heads[0]["cx"]) / max(len(heads) - 1, 1)
    label_right = heads[0]["cx"] - col_w / 2
    edges = [label_right] + [(a["cx"] + b["cx"]) / 2 for a, b in zip(heads, heads[1:])] + [heads[-1]["cx"] + col_w / 2]

    year = year_hint or dt.date.today().year
    days = []
    for h in heads:
        mo, d, wd = DATE_RE.search(h["t"]).groups()
        days.append({"date": f"{year:04d}-{int(mo):02d}-{int(d):02d}", "label": f"{int(mo)}/{int(d)}",
                     "weekday": wd, "closed": False, "note": [], "meals": []})

    left = [l for l in lines if l["x1"] <= label_right + 2 and l["y0"] > header_bottom]
    table_left = min((x0 for x0, x1, y in hl), default=0)
    outer_x = table_left + 10                       # 끼니 라벨 칸 (조식/중식/석식) 을 지나는 x
    inner_x = label_right - 10                      # 코너 라벨 칸 (A코너/B코너...) 을 지나는 x

    all_cuts = _cuts(hl, inner_x, header_bottom, page.rect.height)
    meal_cuts = _cuts(hl, outer_x, header_bottom, page.rect.height)
    table_bottom = all_cuts[-1] if all_cuts else page.rect.height

    vl = _vlines(page)

    def cols_of(l):
        """텍스트가 속한 셀(세로 괘선 사이)이 걸치는 요일 칸들. 병합 셀이면 여러 개."""
        ls = [x for x, y0, y1 in vl if x <= l["cx"] and y0 - 1 <= l["cy"] <= y1 + 1]
        rs = [x for x, y0, y1 in vl if x >= l["cx"] and y0 - 1 <= l["cy"] <= y1 + 1]
        lo = max(ls, default=l["x0"]); hi = min(rs, default=l["x1"])
        lo, hi = min(lo, l["x0"]), max(hi, l["x1"])
        return [i for i in range(len(days)) if lo - 2 <= (edges[i] + edges[i + 1]) / 2 <= hi + 2]

    meals = []
    extras = []
    notes = []
    for mt, mb in _bands(meal_cuts):
        mleft = [l for l in left if mt < l["cy"] < mb]
        name = next((re.sub(r"\s", "", l["t"]) for l in mleft if MEAL_RE.match(l["t"])), None)
        if name is None:
            name = " ".join(l["t"] for l in mleft if l["t"] != "~").strip()
        if not name:                                  # 라벨 없는 영역 = 표 아래 원산지 등 안내문
            notes += [l["t"] for l in sorted(lines, key=lambda l: l["y0"]) if mt < l["cy"] < mb and "@" not in l["t"]]
            continue
        times = [l["t"] for l in sorted(mleft, key=lambda l: l["y0"]) if TIME_RE.match(l["t"])]
        sub_bands = [(t, b) for t, b in _bands(all_cuts) if t >= mt - 2 and b <= mb + 2]
        body = [l for l in lines if mt < l["cy"] < mb and l["x0"] >= label_right - 2 and not JUNK_RE.fullmatch(l["t"])]

        # 모든 요일에 걸친 한 줄짜리 행 = 공통 안내 (예: Take Out)
        if not times and body and all(len(cols_of(l)) == len(days) for l in body):
            extras.append({"name": name, "text": " ".join(l["t"] for l in body)})
            continue

        meal = {"name": name, "time": "~".join(times[:2]) if len(times) >= 2 else "", "corners": []}
        for st, sb in sub_bands:
            corner = " ".join(l["t"] for l in left if st < l["cy"] < sb
                              and not MEAL_RE.match(l["t"]) and not TIME_RE.match(l["t"]) and l["t"] != "~")
            cells = [[] for _ in days]
            for l in sorted((l for l in body if st < l["cy"] < sb), key=lambda l: (l["y0"], l["x0"])):
                for i in cols_of(l):
                    cells[i].append(l["t"])
            featured = [any(edges[i] <= x < edges[i + 1] and st < y < sb
                            for x, y in featured_regions) for i in range(len(days))]
            meal["corners"].append({"name": corner, "cells": cells, "featured": featured})
        meals.append(meal)

    for i, day in enumerate(days):
        for m in meals:
            corners = [{"name": c["name"], "items": c["cells"][i], "featured": c["featured"][i]} for c in m["corners"] if c["cells"][i]]
            if not corners:
                continue
            items = [t for c in corners for t in c["items"]]
            if all(_is_closure(t) for t in items):    # 끼니 전체가 '운영없음'
                day["note"] += items
                day["meals"].append({"name": m["name"], "time": m["time"], "closed": True, "corners": []})
                continue
            for c in corners:                         # 코너만 '운영없음' (예: SALAD BOX)
                c["closed"] = all(_is_closure(t) for t in c["items"])
            day["meals"].append({"name": m["name"], "time": m["time"], "closed": False, "corners": corners})
        all_items = [t for c in (m["corners"] for m in meals) for cell in c for t in cell["cells"][i]]
        real = [t for t in all_items if not _is_closure(t)]
        # '운영없음' 이 있고 메뉴라 볼 만한 게 거의 없으면 휴일명(제헌절 등)까지 포함해 하루 휴무
        if not any(not m["closed"] for m in day["meals"]) or (len(real) < 5 and len(real) < len(all_items)):
            day["closed"] = True
            day["meals"] = []
            day["note"] = all_items
        day["note"] = list(dict.fromkeys(_clean(t) for t in day["note"] if _clean(t) and not JUNK_RE.search(t)))

    title = next((l["t"] for l in sorted(lines, key=lambda l: l["y0"]) if "주차" in l["t"] or "메뉴" in l["t"]), "")
    return {"title": title.strip(), "days": days, "extras": extras, "notes": notes}


# ---------------------------------------------------------------- 빌드

CACHE = HERE / "cache"


def fetch_pdf(post):
    """게시글 PDF. 한 번 받은 글은 cache/에서 읽는다 (수정본은 새 글로 올라오므로 id 기준이면 충분)."""
    path = CACHE / f"{post['id']}.pdf"
    if path.exists():
        return path.read_bytes()
    data = fetch(post["pdf_url"])
    if not data.startswith(b"%PDF"):
        raise ValueError(f"PDF가 아닙니다: {post['title']}")
    CACHE.mkdir(exist_ok=True)
    path.write_bytes(data)
    return data


def build(out_dir: Path, weeks: int = 2):
    posts = list_posts()
    if not posts:
        raise SystemExit("식단표 글을 찾지 못했습니다")
    result = []
    seen = set()
    for p in posts:
        key = re.sub(r"[_\s]*메뉴\s*수정.*$|\s+", "", p["title"])   # '..._메뉴수정' 재게시는 같은 주차로 취급
        if key in seen:
            continue
        seen.add(key)
        year = int(p["posted"][:4]) if p["posted"] else None
        week = parse_pdf(fetch_pdf(p), year)
        # 12월 말에 올라온 1월 식단은 다음 해
        if p["posted"] and p["posted"][5:7] == "12":
            for d in week["days"]:
                if d["date"][5:7] == "01":
                    d["date"] = f"{year + 1}" + d["date"][4:]
        if len(week["days"]) != 5 or not any(d["meals"] or d["note"] for d in week["days"]):
            raise ValueError("식단표의 날짜 또는 메뉴를 확인하지 못했습니다")
        week.update(source={"title": p["title"], "posted": p["posted"], "pdf": p["pdf_url"], "view": p["view_url"]})
        result.append(week)
        if len(result) >= weeks:
            break

    payload = {"generated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec="minutes"), "weeks": result, "list": LIST_URL}
    out_dir.mkdir(parents=True, exist_ok=True)
    _write(out_dir / "menu.json", json.dumps(payload, ensure_ascii=False, indent=1))
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    page = tpl.replace("/*__MENU_DATA__*/null", data)
    _write(out_dir / "index.html",
           '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           + page.replace("</style>", "</style>\n</head>\n<body>", 1) + "\n</body>\n</html>\n")
    return payload


def _write(path: Path, text: str):
    """임시 파일에 쓰고 바꿔치기. 예약 작업이 쓰는 도중에 브라우저가 열어도 반쯤 쓴 파일을 보지 않게."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _log(msg: str):
    """update.log 에 한 줄 남기고 최근 100줄만 유지 (예약 작업은 창이 없어서 여기서 확인)."""
    log = HERE / "update.log"
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    lines.append(f"{dt.datetime.now():%Y-%m-%d %H:%M} {msg}")
    log.write_text("\n".join(lines[-100:]) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="로컬 PDF 파싱 결과만 출력")
    ap.add_argument("--out", default=str(HERE / "site"))
    ap.add_argument("--weeks", type=int, default=2)
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    if sys.stdout:                      # pythonw(예약 작업)로 돌면 콘솔이 없다
        sys.stdout.reconfigure(encoding="utf-8")
    if a.pdf:
        print(json.dumps(parse_pdf(Path(a.pdf).read_bytes()), ensure_ascii=False, indent=1))
        return
    index = Path(a.out) / "index.html"
    try:
        payload = build(Path(a.out), a.weeks)
        summary = " / ".join(w["source"]["title"] for w in payload["weeks"])
        for w in payload["weeks"]:
            print(w["source"]["title"], "→", ", ".join(d["label"] + ("(휴무)" if d["closed"] else "") for d in w["days"]))
        print("생성:", index)
        _log("OK " + summary)
    except Exception as e:
        _log(f"실패 {e!r}")
        print("식단표를 새로 받지 못했습니다:", e)
        if not (a.open and index.exists()):
            raise
        print("이전에 만든 페이지를 엽니다.")
    if a.open:
        import webbrowser
        webbrowser.open(index.resolve().as_uri())


if __name__ == "__main__":
    main()
