import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/User/Desktop/test/SkinDetect";
const sourcePath = path.join(workspaceDir, "檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08_修正版1.pptx");
const buildDir = path.join(workspaceDir, "檔案室/.ppt_edit_body_pretraining_labels");
const finalPath = path.join(workspaceDir, "檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08_部位預訓練標記版.pptx");
const skillDir = "C:/Users/User/.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations";
const runtimePython = "C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const fontFamily = "Microsoft JhengHei";

const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));

// Slides that train, transfer, or compare the DensePose/COCO body-site pretrained model.
const targetSlideNumbers = [4, 5, 6, 7, 8, 17, 18];
const labelText = "※ 部位辨識預訓練使用 DensePose／COCO 人體部位資料（非皮膚病資料集）";

for (const slideNumber of targetSlideNumbers) {
  const slide = presentation.slides.items[slideNumber - 1];
  if (!slide) throw new Error(`找不到第 ${slideNumber} 頁`);
  const label = slide.shapes.add({
    geometry: "textbox",
    position: { left: 620, top: 34, width: 550, height: 30 },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  label.text = labelText;
  label.text.style = {
    typeface: fontFamily,
    fontSize: 15,
    bold: true,
    color: "#C56F3B",
    alignment: "right",
    autoFit: "shrinkText",
  };
}

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
  receiptPath: path.join(buildDir, "body_pretraining_labels.validation.json"),
});
console.log(JSON.stringify(result, null, 2));
