import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const root = new URL('../', import.meta.url);
const model = await readFile(new URL('assets/ikea/billy-oxberg/billy-oxberg-80x30x202-white-web.glb', root));
const activeOptics = JSON.parse(await readFile(new URL('references/ikea-billy-oxberg/sequential-trace/current-no-cylinders-viewer.json', root), 'utf8'));
const output = await build({
  entryPoints: [fileURLToPath(new URL('viewer/scene.js', root))],
  bundle: true,
  minify: true,
  format: 'iife',
  target: ['es2022'],
  legalComments: 'inline',
  write: false,
  define: { MODEL_BASE64: JSON.stringify(model.toString('base64')), ACTIVE_OPTICS: JSON.stringify(activeOptics) },
});
const template = await readFile(new URL('viewer/template.html', root), 'utf8');
const cameraRender = await readFile(new URL('references/ikea-billy-oxberg/sequential-trace/current-no-cylinders-raw.jpg', root));
const rectified = await readFile(new URL('references/ikea-billy-oxberg/image-based-rectification/rectified.png', root));
const mirrorCrop = await readFile(new URL('references/ikea-billy-oxberg/mirror-rectification/mirror-crop-preview.jpg', root));
const rectifiedCentre = await readFile(new URL('references/ikea-billy-oxberg/image-based-rectification/rectified-centre.png', root));
const densityComparison = await readFile(new URL('references/ikea-billy-oxberg/layout-optimization/density-comparison.png', root));
const baselineMirror = await readFile(new URL('references/ikea-billy-oxberg/baseline-single-mirror/mirror-rectification/mirror-crop-preview.jpg', root));
const detectedFeatures = await readFile(new URL('references/ikea-billy-oxberg/image-based-rectification/detected-features.png', root));
const script = output.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const html = template.replace('/* INLINE_VIEWER */', () => script)
  .replaceAll('CAMERA_RENDER_DATA_URL', () => `data:image/jpeg;base64,${cameraRender.toString('base64')}`)
  .replaceAll('RECTIFIED_IMAGE_DATA_URL', () => `data:image/png;base64,${rectified.toString('base64')}`)
  .replaceAll('MIRROR_CROP_DATA_URL', () => `data:image/jpeg;base64,${mirrorCrop.toString('base64')}`)
  .replaceAll('DETECTED_FEATURES_DATA_URL', () => `data:image/png;base64,${detectedFeatures.toString('base64')}`)
  .replaceAll('RECTIFIED_CENTRE_DATA_URL', () => `data:image/png;base64,${rectifiedCentre.toString('base64')}`)
  .replaceAll('DENSITY_COMPARISON_DATA_URL', () => `data:image/png;base64,${densityComparison.toString('base64')}`)
  .replaceAll('BASELINE_MIRROR_CROP_DATA_URL', () => `data:image/jpeg;base64,${baselineMirror.toString('base64')}`);
await writeFile(new URL('index.html', root), html);
console.log(`Built self-contained index.html (${(Buffer.byteLength(html) / 1024 / 1024).toFixed(2)} MB).`);
