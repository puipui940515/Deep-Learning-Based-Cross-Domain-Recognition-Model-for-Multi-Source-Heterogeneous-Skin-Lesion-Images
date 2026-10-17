import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/User/Desktop/test/SkinDetect";
const sourcePath = path.join(workspaceDir, "檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08.pptx");
const buildDir = path.join(workspaceDir, "檔案室/.ppt_edit_timeline_comment1");
const finalPath = path.join(workspaceDir, "檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08_修正版1.pptx");
const skillDir = "C:/Users/User/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const runtimePython = "C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const fontFamily = "Microsoft JhengHei";

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const targetSlide = presentation.slides.items.find((slide) => slide.id === "jetc3ut0");
if (!targetSlide) throw new Error("找不到目標投影片 jetc3ut0");

function addShape(geometry, position, fill, line = { fill: "none", width: 0 }) {
  return targetSlide.shapes.add({ geometry, position, fill, line });
}

function addText(text, position, style = {}) {
  const shape = addShape("textbox", position, "none");
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: 14,
    color: "#24313C",
    autoFit: "shrinkText",
    ...style,
  };
  return shape;
}

// Cover only the overlapped title/legend strip embedded in Image 4 (object id 10).
addShape("rect", { left: 48, top: 239, width: 578, height: 50 }, "#FFFFFF");
addText(
  "加入 BCN20000 前後的 HAM10000／BCN20000 驗證比較",
  { left: 62, top: 241, width: 550, height: 20 },
  { fontSize: 14, bold: true, color: "#17324D", alignment: "center" },
);
addShape("ellipse", { left: 186, top: 267, width: 10, height: 10 }, "#1F77B4");
addText("加入 BCN20000 前", { left: 201, top: 262, width: 124, height: 20 }, { fontSize: 11 });
addShape("ellipse", { left: 338, top: 267, width: 10, height: 10 }, "#FF7F0E");
addText("加入 BCN20000 後", { left: 353, top: 262, width: 124, height: 20 }, { fontSize: 11 });

const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools/artifact_tool_utils.mjs"),
).href);
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(path.dirname(finalPath), { recursive: true });
const candidatePath = path.join(buildDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const sourceBytes = await fs.readFile(sourcePath);
const sourceSha256 = crypto.createHash("sha256").update(sourceBytes).digest("hex");
const result = await finalizePresentation({
  explicitTotalSlideCount: 20,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: {
    basis: "reference",
    families: [fontFamily],
    referencePath: sourcePath,
    referenceSha256: sourceSha256,
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(buildDir, "timeline_comment1.validation.json"),
});
console.log(JSON.stringify(result, null, 2));
