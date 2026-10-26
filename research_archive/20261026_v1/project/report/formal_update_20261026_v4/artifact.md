# SkinDetect E 正式範本執行契約

日期：2026-10-20，Asia/Taipei。
原檔：[USER_HOME]\Downloads\專題_Ver_28.docx
SHA256：c2fb05fda2355962aeba72f01933b3e421db2d82d4c208af06eae778a7b1d67c
原檔 50 頁、3 分節；Word 唯讀匯出 template_word/layout.pdf。完整逐段與套件證據 template_audit.json。

## 保留規格

- 三分節、A4 11906×16838 twip，直式。上/下1440、左/右1797、裝訂0、header0、footer454 twip；單欄，欄距425。每節 docGrid linePitch360。各節 titlePg 保留。
- 第1節封面，頁碼upperRoman起1；第2節摘要及清單，upperRoman起1；第3節正文，阿拉伯數字起1。footer XML與關係原樣保存，原檔無可見頁首。
- 中文一律 DFKai-SB，ascii/hAnsi/cs Times New Roman；移除字型theme覆蓋，但保留尺寸、粗體等。這是使用者明確要求，優先於範本殘留的新細明體與theme。
- 封面克隆原p6標題與原學生/教師欄位。使用者補充確認封面已有組員/教授資料並重新提供同一檔，因此保留封面學生[PERSON_REDACTED]、[PERSON_REDACTED]、[PERSON_REDACTED]及教授[PERSON_REDACTED]；未見學號，不猜測。封面日期改為初稿製作月份民國115年10月，不宣稱為畢業日期。
- 正文克隆p95：14pt、兩端對齊、after120twip、exact480twip（24pt）、firstLine560twip及firstLineChars200。
- 中文摘要克隆p23：14pt、1.5倍、after120、firstLine560/200。英文摘要p33：14pt、固定24pt。
- H1克隆p79：20pt、置中、前後360twip、單行；H2 p80：18pt、前360後180、單行、left721/hanging721，hangingChars200；H3 p119/146：16pt、前360後180、left961/hanging961/hangingChars300。保留原相應run粗體設定。新增一套真正連動三層編號，修復原多套單層list，外觀第1章／1.1／1.1.1。
- Caption克隆p144（caption原生樣式af0）：14pt、粗體、置中、after360twip、單行，章節.序號；使用STYLEREF/SEQ，圖下表上。
- 表格沿用原表格tblPr與cell/paragraph規格（表格樣式ac，14pt、exact400twip=20pt），可編輯；寬度以正文可用8312twip配置，列高自動，標題列重複。
- 目錄沿用toc1/2/3，圖表目錄沿用table of figures樣式af1，三種清單均真正TOC欄位。順序維持目錄→表目錄→圖目錄。
- 書目沿用p275：編號、作者年、固定24pt；作者/標題/出版資訊/DOI或URL均查證，BibTeX為可維護來源，SEQ/REF為可更新編號/內文交互連結，不冒稱Word Source Manager。

## 章節與插入位置

使用者後續明確修正：「那是舊的版本，只要參考他們的格式就好，標題跟內文的文字都做更改」。因此保留原7主章、階層與相同槽位/順序，依SkinDetect改寫所有專有標題。
主章依序為研究動機與目的；文獻探討；研究內容、方法與工作項目；模型比較與實驗結果；結論與研究限制；參考文獻；專題工作配置與完成紀錄。
第2章4節改為皮膚分類與資料集、ResNet、V2與遷移、資料不平衡/評估/來源差異；第3章維持4節與3/3/4/3子節：環境、治理、模型、訓練評估；第4章維持5節：整體/來源與Recall/初始化/曲線/時間；第5章維持2節及3/4子節：已完成結論/研究限制；第7章2節為工作項目/完成時程，不捏造個人人力分工。
摘要、英文摘要、來源表、類別表、模型設定、選模/指標定義、15run/三seed/三來源/Recall、10張C正式比較與曲線全部使用已完成研究。

## 套件修改界線

以原DOCX套件直接patch。可修改word/document.xml（內容）、styles.xml（字型與內建樣式繼承修正）、numbering.xml（新增連動編號）、settings.xml（updateFields與Caption登錄）、document.xml.rels與[Content_Types].xml（新增正式圖）、theme/theme1.xml（英中主/次要字型繼承）、docProps核心標題與Word更新的頁數統計。其餘40個parts逐byte保留，包括頁尾、既有media、customXml及其他關係。
原DOCX唯一content control是目錄gallery，已完整盤點；只取代原目錄內容為可更新欄位，非RichText資料輸入控制。所有其他opaque parts保持。

## 驗收與差異

原檔SHA不變；節幾何前後一致；原標題名稱/階層/順序一致；圖無變形；無手動目錄；正文/清單/Caption所有字型無Aptos/Calibri/新細明體；數字可追溯C CSV與原始result；Test不讀取。Word實際更新欄位、匯PDF後raster逐頁檢查。render_docx.py已嘗試，因缺LibreOffice失敗，使用本機Word作正式排版基準。
書目維護限制與專有小節留白列交付說明；頁數因研究內容變更而變更，不要求50頁。


## 2026-10-21 update v2 contract supersedes the initial scope
Edit the delivered formal v1 in place at OOXML level and publish a new version. Preserve all 48 heading texts and their hierarchy, all 12 figures and 11 references, page geometry and styles. Add only completed first-round findings and timestamped in-progress round-two / mock-website status. Source DOCX files remain immutable. Native Word fields updated; 44 pages verified.


## 2026-10-25 v3 narrow system update
Authority: delivered v2, SHA 3549643f098b514deae1e30302ad9f7ab4b457a40f5c8b8f61f0c4534e602669
Only document.xml changed before Word field refresh. Seven main chapters, all original 15 tables, 12 drawings, 11 references, sections/styles/numbering/footers/media preserved. Add 3.5 (implementation) and 4.6 (CPU functional QA); clarify historic/current website status in 5.2.4 and 7.1/7.2. No training numeric updates. Original source remains immutable. Native Word refresh and page render required.


## 2026-10-26 v4
Authority v3 SHA 9255269c7ef1b7a8e29a4fd6880015d986ebf1ba4fd375ca4881d97069c9cdd6; desktop Word identical. All 259 nonempty direct paragraphs correspond to supplied Markdown after markup normalization. Retain seven main chapters, 15 original tables and 12 figures. Add 8 native tables 4.11–4.18 and existing D figure4.13; 3.6 methods,4.7–4.12 results/status,original conclusion slots and chapter7 updated. Original references retained. Permanent D report plus same-version OneDrive local Word; do not claim cloud synchronization. No upstream analysis reruns.
