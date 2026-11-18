"""由 edges_final.jsonl 與 themes_claims.json 產生知識庫的族譜頁面（衍生產物，可重跑）。
輸出到 <KB>：關聯.jsonl、族譜.md、結論.md，並在每個實驗頁插入／更新「前因與後果」區塊（以註解標記包住，重跑會覆蓋）。
用法（在倉庫根目錄）：python 實驗知識庫/tools/build_kb_graph.py 實驗知識庫 實驗知識庫/tools
"""
import json
import pathlib
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
KB = pathlib.Path(sys.argv[1]); W = pathlib.Path(sys.argv[2])
EXP = KB / "實驗"
CAUSAL = ["引發", "支持", "推翻或更正", "取代", "前置", "沿用", "複製"]
OUT_WORD = {"引發": "促成", "支持": "支持", "推翻或更正": "推翻／更正", "取代": "取代", "前置": "是…的前置", "沿用": "被…沿用", "複製": "被…複製"}
IN_WORD = {"引發": "由…促成", "支持": "受…支持", "推翻或更正": "被…推翻／更正", "取代": "被…取代", "前置": "以…為前置", "沿用": "沿用…", "複製": "複製…"}
B, E = "<!-- 族譜:開始（自動產生，勿手改） -->", "<!-- 族譜:結束 -->"

edges = [json.loads(l) for l in (W / "edges_final.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
tc = json.loads((W / "themes_claims.json").read_text(encoding="utf-8"))
pages = {p.stem for p in EXP.glob("*.md") if p.stem != "README"}
meta = json.loads((W / "meta.json").read_text(encoding="utf-8"))
for e in edges:
    assert e["src"] in pages and e["dst"] in pages, e
(KB / "關聯.jsonl").write_text("\n".join(json.dumps({k: e[k] for k in ("src", "dst", "type", "reason", "evidence", "confidence", "source")}, ensure_ascii=False) for e in edges) + "\n", encoding="utf-8")

ce = [e for e in edges if e["type"] in CAUSAL]
inn, out = defaultdict(list), defaultdict(list)
for e in ce:
    out[e["src"]].append(e); inn[e["dst"]].append(e)


def short(p):
    return meta[p]["title"].split("　", 1)[-1][:28]


for p in sorted(pages):
    f = EXP / f"{p}.md"; t = f.read_text(encoding="utf-8")
    t = re.sub(re.escape(B) + r".*?" + re.escape(E) + r"\n*", "", t, flags=re.S)
    L = [B, "## 前因與後果", ""]
    if not inn[p] and not out[p]:
        L += ["（沒有判讀出因果關係；只有比較或順帶提及。）", ""]
    for label, lst, other, word in (("前因", inn[p], "src", IN_WORD), ("後果", out[p], "dst", OUT_WORD)):
        if lst:
            L.append(f"**{label}**")
            for e in sorted(lst, key=lambda x: (CAUSAL.index(x["type"]), x[other])):
                o = e[other]
                L.append(f"- {e['type']}｜[{o}]({o}.md)（{short(o)}）：{e['reason']}")
            L.append("")
    L += ["完整關係見 [族譜](../族譜.md)、[結論](../結論.md)。", E, ""]
    block = "\n".join(L)
    if "\n## 來源檔案" in t:
        t = t.replace("\n## 來源檔案", "\n" + block + "\n## 來源檔案", 1)
    else:
        t = t.rstrip("\n") + "\n\n" + block
    f.write_text(t, encoding="utf-8")


def nid(p):
    return re.sub(r"\W", "_", p)


G = ["# 實驗族譜", "",
     "每條關係由實驗頁內文判讀而來（類型、方向、一句理由、出處），全部存在 [`關聯.jsonl`](關聯.jsonl)。",
     "只畫因果類關係（引發、支持、推翻或更正、取代、前置、沿用、複製）；「僅比較」「僅提及」只留在 jsonl。",
     f"共 {len(edges)} 條關係，其中因果類 {len(ce)} 條。判讀方式與抽查結果見文末。", ""]
theme_of = defaultdict(list)
for th in tc["themes"]:
    for p in th["pages"]:
        theme_of[p].append(th["name"])
G += ["## 主題之間", "", "```mermaid", "flowchart LR"]
tt = defaultdict(int)
for e in ce:
    for a in theme_of.get(e["src"], []):
        for b in theme_of.get(e["dst"], []):
            if a != b:
                tt[(a, b)] += 1
names = [th["name"] for th in tc["themes"]]
for i, n in enumerate(names):
    G.append(f'  T{i}["{n}"]')
for (a, b), n in sorted(tt.items(), key=lambda x: -x[1]):
    if n >= 2:
        G.append(f"  T{names.index(a)} -->|{n}| T{names.index(b)}")
G += ["```", "", "（箭頭上的數字是兩個主題之間的因果關係條數，只畫 ≥2 條的。）", ""]
for th in tc["themes"]:
    ps = set(th["pages"])
    G += [f"## {th['name']}", "", th.get("summary", ""), "", "```mermaid", "flowchart TD"]
    for p in sorted(ps):
        G.append(f'  {nid(p)}["{p} {short(p)}"]')
    for e in ce:
        if e["src"] in ps and e["dst"] in ps:
            G.append(f'  {nid(e["src"])} -->|{e["type"]}| {nid(e["dst"])}')
    G += ["```", ""]
    cross = [e for e in ce if (e["src"] in ps) != (e["dst"] in ps)]
    if cross:
        G += ["跨主題關係：", ""]
        for e in cross[:40]:
            G.append(f"- [{e['src']}](實驗/{e['src']}.md) —{e['type']}→ [{e['dst']}](實驗/{e['dst']}.md)：{e['reason']}")
        if len(cross) > 40:
            G.append(f"- …另 {len(cross) - 40} 條見 `關聯.jsonl`")
        G.append("")
G += ["## 判讀方式與抽查", "", tc.get("method_note", ""), ""]
(KB / "族譜.md").write_text("\n".join(G) + "\n", encoding="utf-8")

C = ["# 結論與證據", "", "每個結論列出支持與推翻它的實驗。狀態：成立、部分成立、被推翻、未定。", ""]
for c in tc["claims"]:
    C += [f"## {c['id']}　{c['statement']}", "", f"- 狀態：**{c['status']}**", ""]
    labs = (("support", "當時支持它的"), ("against", "推翻它的")) if c["status"] == "被推翻" else (("support", "支持"), ("against", "推翻或限制"))
    for k, lab in labs:
        if c.get(k):
            C.append(f"**{lab}**")
            for s in c[k]:
                C.append(f"- [{s['page']}](實驗/{s['page']}.md)：{s['why']}")
            C.append("")
    if c.get("note"):
        C += [f"註：{c['note']}", ""]
(KB / "結論.md").write_text("\n".join(C) + "\n", encoding="utf-8")
print("edges", len(edges), "causal", len(ce), "themes", len(tc["themes"]), "claims", len(tc["claims"]))
