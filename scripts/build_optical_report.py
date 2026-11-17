from pathlib import Path
import base64
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'references/ikea-billy-oxberg/sequential-trace'
r=json.loads((OUT/'results.json').read_text())
p=json.loads((ROOT/'data/optics/final-prescription.json').read_text())


def image(name,mime):
    return 'data:'+mime+';base64,'+base64.b64encode((OUT/name).read_bytes()).decode()


full=r['sampledAreaCoverage']['fullSamples'];half=r['sampledAreaCoverage']['halfSamples']
quality=[]
for i,label in [(17,'中心 X≈0，Y≈125 mm'),(16,'X≈105，Y≈125 mm'),(15,'X≈226，Y≈125 mm')]:
    f=r['fields'][i]
    meaning=['中心几何响应较集中','已明显展宽','展宽接近一个汉字高度'][[17,16,15].index(i)]
    quality.append(f"<tr><td>{label}</td><td>{f['objectD80Mm']:.2f} mm</td><td>{f['geometricMtfAtHalfCyclePerMmY']:.3f}</td><td>{meaning}</td></tr>")
surfaces=[]
for s in p['surfaces']:
    aperture=f"Ø{s['diameter']:.3f}" if s['diameter'] else f"{s['width']:g} × {s['height']:g}"
    radius=f"{s['radius']:+.6f}" if s['radius'] else '∞'
    surfaces.append(f"<tr><td>{s['name']}</td><td>{s['kind']}</td><td>{s['z']:.6f}</td><td>{radius}</td><td>{s['n_before']:.5f} → {s['n_after']:.5f}</td><td>{aperture}</td></tr>")
replacements=dict(SENSOR_IMAGE=image('sensor-preview.jpg','image/jpeg'),CONTROL_IMAGE=image('no-cylinders-preview.jpg','image/jpeg'),
    COVERAGE_IMAGE=image('coverage-map.svg','image/svg+xml'),SPOTS_IMAGE=image('response-spots.svg','image/svg+xml'),SECTION_IMAGE=image('lens-section.svg','image/svg+xml'),
    COVERAGE=f"{full['anyRayCoverage']*100:.1f}",HALF=f"{half['anyRayCoverage']*100:.3f}",FULL=f"{full['anyRayCoverage']*100:.3f}",
    DELTA=f"{(full['anyRayCoverage']-half['anyRayCoverage'])*100:.3f}",TARGET_CELLS=str(full['targetCells']),HIT_CELLS=str(full['reachedCells']),ROBUST=f"{full['atLeast8Rays']*100:.1f}",
    QUALITY_ROWS=''.join(quality),SURFACE_ROWS=''.join(surfaces),FILM_Z=f"{p['film_z']:.6f}",ERROR=f"{r['verification']['roundTripPositionErrorMm']:.2e}")
html=(ROOT/'viewer/optical-report.template.html').read_text()
for key,value in replacements.items():html=html.replace('__'+key+'__',value)
if (ROOT/'data/optics/current-prescription.json').exists():
    html=html.replace('<main>','<main><p class="note">历史柱面镜试算，已退出当前设计。<a href="index.html">打开当前无柱面镜模型 ↗</a></p>',1)
assert '__SENSOR_IMAGE__' not in html and '__SURFACE_ROWS__' not in html
(ROOT/'optical-validation.html').write_text(html)
print(f'Saved optical-validation.html ({len(html.encode())/1024/1024:.2f} MB), all preview images embedded.')
