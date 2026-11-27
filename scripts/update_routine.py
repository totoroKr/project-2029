"""Fetch public exam schedule metadata. Never access user accounts or results."""
import datetime as dt, json, re, pathlib, urllib.request, sys
from bs4 import BeautifulSoup

SOURCE = "https://livemcq.com/central-routine/"
OUT = pathlib.Path(__file__).resolve().parents[1] / "routine-feed.json"
DATE = re.compile(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})$")
def classify(title):
    t = title.lower()
    if re.search(r"নতুনদের.*বিসিএস.*(?:২০০|200)", t): return "beginner"
    if re.search(r"ফ্রি.*সাপ্তাহিক.*মডেল|weekly.*model", t): return "model"
    if "vocabulary booster" in t: return "vocab"
    if "english wizard" in t: return "grammar"
    if re.search(r"ব্যাংক\s*(?:নিয়োগ|নিয়োগ|মডেল)|bank recruitment", t): return "bank"
    if re.search(r"\biba\b.*(?:ফ্যাকাল্টি|faculty)", t): return "iba"
    if re.search(r"(?:৯ম|9th).*(?:১৩|13)", t): return "grade"
    return None

def parse(raw):
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript"]): tag.decompose()
    text = soup.get_text("\n", strip=True).replace("\u00a0", " ")
    # Some markup puts the separator or the title in separate text nodes.
    text = re.sub(r"\n\s*\|\s*\n", " | ", text)
    text = re.sub(r"\n\s*\|[ \t]*", " | ", text)
    text = re.sub(r"[ \t]*\|\s*\n", " | ", text)
    rows, day, cur = [], None, None
    def flush():
        if cur and cur["programme"] and cur["parts"]:
            # Keep only concise topic metadata; full syllabus remains on source.
            parts = [p for p in cur["parts"] if p and not re.match(
                r"^(?:[-—–]+|\[নির্দেশিকা|\[গাইড|\[সকল|উৎস\s*:|সোর্স\s*:|source\s*:|[\"“]?Award Mania)", p, re.I)]
            parts = [p for p in parts if not re.match(r"^(?:টপিকসমূহ|টপিক|topics?)\s*[:\-]?$", p, re.I)]
            topic = " / ".join(parts[:5]).strip()
            if topic:
                rows.append(dict(date=cur["date"], programme=cur["programme"], title=cur["title"],
                                 topic=topic[:420], marks=cur["marks"], end="", source=SOURCE))
    for line in text.splitlines():
        line = re.sub(r"[ \t]+"," ",line).strip()
        m = DATE.fullmatch(line)
        if m:
            flush(); cur = None
            try: day = dt.datetime.strptime(" ".join(m.groups()), "%B %d %Y").date().isoformat()
            except ValueError: day = None
            continue
        if not day: continue
        if " | " in line:
            flush()
            title, detail = line.split(" | ",1)
            cur = dict(date=day, programme=classify(title), title=title, parts=[detail], marks="")
            continue
        if cur is not None:
            m = re.match(r"^মার্ক[ঃ:]\s*([0-9০-৯]+)",line)
            if m:
                cur["marks"] = int(m.group(1).translate(str.maketrans("০১২৩৪৫৬৭৮৯","0123456789")))
            elif re.match(r"^পরীক্ষার সময়|^পরীক্ষার সময়",line):
                flush(); cur = None
            elif line: cur["parts"].append(line)
    flush()
    result = {}
    for row in rows:
        key = (row["date"],row["programme"],row["title"],row["topic"])
        result[key] = row
    return sorted(result.values(),key=lambda r:(r["date"],r["programme"],r["title"]))

def main():
    request=urllib.request.Request(SOURCE,headers={"User-Agent":"Project2029 personal schedule reader"})
    with urllib.request.urlopen(request,timeout=25) as response:
        raw=response.read(4_000_001)
    if len(raw)>4_000_000: raise RuntimeError("Unexpected page size")
    rows=parse(raw)
    if len(rows)<10 or len({r["date"] for r in rows})<5:
        raise RuntimeError("Source format changed or incomplete; preserving last good feed.")
    # Do not commit every run if the schedule content did not change.
    if OUT.exists():
        try:
            if json.loads(OUT.read_text(encoding="utf-8")).get("exams")==rows:
                print("No schedule changes"); return
        except (ValueError,OSError): pass
    data={"source":SOURCE,"updatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),"exams":rows}
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{len(rows)} exams across {len({r['date'] for r in rows})} dates")

if __name__=="__main__": main()
