"""Make the active no-cylinder prescription, refocus, and export viewer data."""
from pathlib import Path
import sys,json,argparse
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'optics'))
from sequential import camera_surfaces,object_to_film,disk_samples,reflect_points,to_local,to_shelf,normalize,asdict,C,M,N,TANGENT,LAYOUT


def prepare():
    surfaces=camera_surfaces(.30,.8)
    real=np.array([[0.,125.,60.]])
    obj=to_local(reflect_points(real))
    pupil=disk_samples(512)*.4
    r=object_to_film(np.repeat(obj,len(pupil),axis=0),pupil,surfaces,surfaces[0].z-6.94,continuation=False)
    v=r['valid'];w=r['weight'][v];w/=w.sum()
    a=r['d'][v,:2]/r['d'][v,2,None];b=r['o'][v,:2]-a*r['o'][v,2,None]
    aa=a-np.sum(w[:,None]*a,axis=0);bb=b-np.sum(w[:,None]*b,axis=0)
    film=-np.sum(w[:,None]*aa*bb)/np.sum(w[:,None]*aa*aa)
    spots=a*film+b;cent=np.sum(w[:,None]*spots,axis=0)
    rms=float(np.sqrt(np.sum(w*np.sum((spots-cent)**2,axis=1)))*1000)
    out=dict(variant='camera-plus-M1-no-cylinders',units='mm',wavelength_nm=587.6,
        parameters=dict(scale=.30,stop=.8,film_gap=float(surfaces[0].z-film)),
        film_z=float(film),surfaces=[asdict(s) for s in surfaces],
        sensor_mm=[6.4,3.6],sensor_pixels=[4000,2250],
        cameraFrontShelfMm=C.tolist(),
        layout=LAYOUT,
        removed=['L1 cylinder','L2 cylinder','external cylinder frames and posts','anamorphic target mapping'],
        refocus=dict(targetShelfMm=real[0].tolist(),targetUnfoldedOpticalMm=obj[0].tolist(),acceptedRays=int(v.sum()),axisGeometricRmsUm=rms),
        note='Six-element rotationally symmetric camera objective retained; no external cylinders; single-wavelength research prescription, not a selected production module')
    (ROOT/'data/optics/current-prescription.json').write_text(json.dumps(out,indent=2)+'\n')
    print('ACTIVE PRESCRIPTION',json.dumps({'filmZ':float(film),'focusRmsUm':rms,'refractions':sum(s.n_before!=s.n_after for s in surfaces),'cylinders':0}))


def measure():
    outdir=ROOT/'references/ikea-billy-oxberg/sequential-trace'
    data=np.load(outdir/'current-no-cylinders-data.npz')
    base=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())
    books=base['books'];hits=data['hits'];mask=np.zeros_like(hits,bool)
    for j in range(100):
        for i in range(152):
            x=-380+(i+.5)*5;y=(j+.5)*2.5
            mask[j,i]=any(b['x0']+.35<=x<=b['x1']-.35 and y<=b['height'] for b in books)
    reached=(hits>0)&mask;ratio=float(reached.sum()/mask.sum())
    rows=np.flatnonzero(data['rowSpineHits']>0);span=float((rows[-1]-rows[0]+1)/len(data['rowSpineHits'])) if len(rows) else 0
    bands=[]
    for j in range(100):
        if np.all(mask[j]) and np.all(reached[j]):
            if bands and bands[-1]['endRow']==j-1:bands[-1].update(endRow=j,high=(j+1)*2.5)
            else:bands.append(dict(endRow=j,low=j*2.5,high=(j+1)*2.5))
    prescription=json.loads((ROOT/'data/optics/current-prescription.json').read_text())
    from sequential import Surface
    surfaces=[Surface(**s) for s in prescription['surfaces']]
    rays=[];angles=[]
    for x in [-370.,0.,370.]:
        b=next(b for b in books if b['x0']<=x<=b['x1'])
        for y in [3.,125.,b['height']-1]:
            real=np.array([[x,y,60.]])
            virtual=to_local(reflect_points(real))
            r=object_to_film(virtual,np.zeros((1,2)),surfaces,prescription['film_z'],record=True,continuation=True)
            if not r['valid'][0] or abs(r['film'][0,0])>3.2 or abs(r['film'][0,1])>1.8:continue
            front=to_shelf(r['paths'][1][0]);direction=normalize(to_shelf(virtual)-front)[0]
            t=np.dot(M-front,N)/np.dot(direction,N);q=front+t*direction
            if abs(q[0])>290 or abs(np.dot(q-M,TANGENT))>26:continue
            path=[to_shelf(r['film'][0]).tolist()]+[to_shelf(p[0]).tolist() for p in reversed(r['paths'][1:])]+[q.tolist(),real[0].tolist()]
            rays.append(path);d=real[0]-q;angles.append(float(np.degrees(np.arctan2(abs(d[2]),np.hypot(d[0],d[1])))))
    coverage=dict(variant='camera-plus-M1-no-cylinders',cylinders=0,ratio=ratio,bookCells=int(mask.sum()),reachedCells=int(reached.sum()),
        nx=152,ny=100,mask=reached.astype(int).ravel().tolist(),bands=bands,
        spineSignalVerticalSpan=span,spineSignalRowRange=[int(rows[0]),int(rows[-1])],
        angles=[min(angles),max(angles)],rayPaths=rays,
        render=json.loads((outdir/'current-no-cylinders-render.json').read_text()),
        note='Ray reach at default aligned books; not OCR accuracy. Signal span includes geometric blur; not a readable pixel count.')
    validation=ROOT/'references/ikea-billy-oxberg/layout-optimization/validation.json'
    if validation.exists():coverage['positionOptimization']=json.loads(validation.read_text())
    (outdir/'current-no-cylinders-viewer.json').write_text(json.dumps(coverage,indent=2)+'\n')
    print('CURRENT RESULTS',json.dumps({'coverage':ratio,'signalHeightFraction':span,'paths':len(rays)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--measure',action='store_true');args=p.parse_args()
    measure() if args.measure else prepare()
