import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const sourcePath = "C:/Users/User/Desktop/test/SkinDetect/檔案室/簡報/皮膚病偵測_圖表時間軸_2026-09-08.pptx";
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const slide = presentation.slides.items[10];
console.log("images keys", Reflect.ownKeys(slide.images));
console.log("images proto", Reflect.ownKeys(Object.getPrototypeOf(slide.images)));
console.log("images items", slide.images.items?.length);
for (const image of slide.images.items ?? []) {
  console.log("image", image.id, Reflect.ownKeys(image), Reflect.ownKeys(Object.getPrototypeOf(image)), image.position);
}
console.log("elements", slide.elements?.items?.map(e => [e.id,e.type,e.position]));
