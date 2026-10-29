import sharp from 'sharp';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
async function render(source, targets) {
  const svg = await readFile(new URL(source, import.meta.url));
  for (const target of targets) {
    const file = new URL(target, root);
    await mkdir(new URL('./', file), { recursive: true });
    await sharp(svg).png().toFile(fileURLToPath(file));
  }
}
await render('poster.svg', ['preview.png', 'Contents/mods/BSCCraftFromContainers/42/poster.png']);
console.log('Generated preview.png and Build 42 poster.png (512 x 512).');
await render('icon.svg', ['Contents/mods/BSCCraftFromContainers/42/icon.png']);
console.log('Generated Build 42 icon.png (128 x 128).');
await render('how-it-works.svg', ['docs/images/how-it-works.png']);
console.log('Generated docs/images/how-it-works.png (1200 x 630).');
