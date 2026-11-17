import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {build} from 'esbuild';
const root=new URL('../',import.meta.url);
const folder='references/ikea-billy-oxberg/two-cylinder-v2/';
const data=JSON.parse(await readFile(new URL(folder+'comparison.json',root),'utf8'));
const geometry=JSON.parse(await readFile(new URL('references/ikea-billy-oxberg/camera-render-input.json',root),'utf8')).books;
const titles=JSON.parse(await readFile(new URL('data/example-book-titles.json',root),'utf8'));
if(titles.length!==geometry.length)throw new Error('Book title count must match scene geometry.');
const books=geometry.map((b,i)=>({...b,id:i+1,title:titles[i]}));
const assets={};
async function url(path,mime){return `data:${mime};base64,${(await readFile(new URL(path,root))).toString('base64')}`;}
for(const d of data){
  d.books=books;d.prescriptionData=JSON.parse(await readFile(new URL(d.prescription,root),'utf8'));
  const dir=folder+d.name+'/';
  assets[d.name]={sensor:await url('references/ikea-billy-oxberg/sequential-trace/'+d.renderName+'-preview.jpg','image/jpeg'),crop:await url(dir+'mirror-crop.jpg','image/jpeg'),rectified:await url(dir+'rectified-preview.jpg','image/jpeg'),centre:await url(dir+'centre.png','image/png'),nativeUrl:'references/ikea-billy-oxberg/sequential-trace/'+d.renderName+'-corrected.png'};
}
const model=await readFile(new URL('assets/ikea/billy-oxberg/billy-oxberg-80x30x202-white-web.glb',root));
const output=await build({entryPoints:[fileURLToPath(new URL('viewer/cylinder-effect.js',root))],bundle:true,minify:true,format:'iife',target:['es2022'],write:false,define:{REPORT_DATA:JSON.stringify(data),REPORT_ASSETS:JSON.stringify(assets),MODEL_BASE64:JSON.stringify(model.toString('base64'))}});
const html=(await readFile(new URL('viewer/cylinder-effect.html',root),'utf8')).replace('/* CYLINDER_REPORT_SCRIPT */',()=>output.outputFiles[0].text.replace(/<\/script/gi,'<\\/script'));
await writeFile(new URL('two-cylinder-effect.html',root),html);
console.log(`Built two-cylinder-effect.html (${(Buffer.byteLength(html)/1024/1024).toFixed(2)} MB)`);
