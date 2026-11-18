import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
const { Presentation } = await import(pathToFileURL('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-737-0_26.1112.737.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs'));
const p=await Presentation.load('C:/Users/fenip/Downloads/WAD_Project_Template.pptx');
console.log('slides',p.slides.items.length);
const snap=await p.inspect({kind:'slide,textbox,shape,image',maxChars:30000});
console.log(snap.records);
for (let i=0;i<p.slides.items.length;i++){const b=await p.export({slide:p.slides.items[i],format:'png',scale:1}); await fs.writeFile(`.codex-build/template-${i+1}.png`,new Uint8Array(await b.arrayBuffer()))}
