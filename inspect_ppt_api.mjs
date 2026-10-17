import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/User/Desktop/test/SkinDetect/檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08.pptx";
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
console.log("slides keys", Reflect.ownKeys(presentation.slides));
console.log("slides proto", Reflect.ownKeys(Object.getPrototypeOf(presentation.slides)));
console.log("slides items", presentation.slides.items?.length);
const slide = presentation.slides.items[10];
console.log("slide keys", Reflect.ownKeys(slide));
console.log("slide proto", Reflect.ownKeys(Object.getPrototypeOf(slide)));
console.log("slide id", slide.id);
console.log("shapes keys", Reflect.ownKeys(slide.shapes));
console.log("shapes proto", Reflect.ownKeys(Object.getPrototypeOf(slide.shapes)));
console.log("shape count", slide.shapes.items?.length);
for (let i = 0; i < (slide.shapes.items?.length ?? 0); i++) {
  const shape = slide.shapes.items[i];
  console.log(i, shape.id, shape.type, Reflect.ownKeys(shape), Reflect.ownKeys(Object.getPrototypeOf(shape)));
}
