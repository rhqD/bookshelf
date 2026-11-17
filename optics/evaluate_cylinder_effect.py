"""Validate rendered two-cylinder trials using forward-map inversion.

The inverse initialisation is measured from physically traced chief rays. All
rectified intensity comes from the rendered observation; no reference text or
book silhouette is supplied to image reconstruction.
"""
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import LinearNDInterpolator,RectBivariateSpline
from scipy.spatial import cKDTree
from scipy.ndimage import map_coordinates,distance_transform_edt
from PIL import Image
from sequential import ROOT,Surface,disk_samples,object_to_film,trace
from layout import active_layout,geometry
from forward_cylinder_design import forward
from design_cylinders_v2 import project
from render import display

OUT=ROOT/'references/ikea-billy-oxberg/two-cylinder-v2'
TRACE=ROOT/'references/ikea-billy-oxberg/sequential-trace'

def valid_rays(r,s):
    ok=r['valid'].copy()&(r['mirrorDistance']>0)&(r['spineDistance']>0)
    for sf,p in zip(s,r['paths'][1:]):
        if sf.diameter:ok&=np.linalg.norm(p[:,:2],axis=1)<=sf.diameter/2
        else:ok&=(abs(p[:,0])<=sf.width/2)&(abs(p[:,1])<=sf.height/2)
    return ok

class Mapping:
    def __init__(self,prescription):
        self.prescription=json.loads(Path(prescription).read_text());self.s=[Surface(**sf) for sf in self.prescription['surfaces']]
        self.film=self.prescription['film_z'];self.layout=self.prescription.get('layout',active_layout())
        x=np.linspace(-3.19,3.19,161);y=np.linspace(-1.75,1.75,121)
        ff=np.array([[xx,yy] for yy in y for xx in x]);r=self.ray(ff)
        ok=valid_rays(r,self.s)&np.isfinite(r['hit']).all(axis=1)
        ok&=(abs(r['hit'][:,0])<650)&(r['hit'][:,1]>-150)&(r['hit'][:,1]<400)
        self.seed=LinearNDInterpolator(r['hit'][ok,:2],ff[ok]);self.tree=cKDTree(r['hit'][ok,:2]);self.ff=ff[ok]

    def ray(self,ff):return forward(ff,np.zeros((len(ff),2)),self.s,self.film,self.layout)

    def invert(self,points):
        xy=points[:,:2];ff=self.seed(xy)
        missing=~np.isfinite(ff).all(axis=1)
        if missing.any():ff[missing]=self.ff[self.tree.query(xy[missing])[1]]
        h=1e-6
        for _ in range(25):
            r=self.ray(ff);err=r['hit'][:,:2]-xy
            dx=(self.ray(ff+[h,0])['hit'][:,:2]-r['hit'][:,:2])/h
            dy=(self.ray(ff+[0,h])['hit'][:,:2]-r['hit'][:,:2])/h
            J=np.stack((dx,dy),axis=2)
            det=dx[:,0]*dy[:,1]-dx[:,1]*dy[:,0];det=np.where(abs(det)>1e-9,det,1e-9)
            step=np.c_[(dy[:,1]*err[:,0]-dy[:,0]*err[:,1])/det,(-dx[:,1]*err[:,0]+dx[:,0]*err[:,1])/det]
            step=np.nan_to_num(step,nan=0,posinf=.1,neginf=-.1);step*=np.minimum(1,.12/np.maximum(np.linalg.norm(step,axis=1,keepdims=True),1e-20))
            old=np.linalg.norm(err,axis=1);changed=np.zeros(len(ff),bool)
            for factor in [1.,.5,.25,.125]:
                candidate=np.clip(ff-step*factor,[-3.25,-1.85],[3.25,1.85])
                check=self.ray(candidate);new=np.linalg.norm(check['hit'][:,:2]-xy,axis=1)
                use=(new<old)&~changed&check['valid']
                ff[use]=candidate[use];changed|=use
            if np.max(np.linalg.norm(err,axis=1))<1e-7:break
        r=self.ray(ff);c,b,m,n,t=geometry(self.layout)
        ok=valid_rays(r,self.s)&(np.linalg.norm(r['hit'][:,:2]-xy,axis=1)<.001)&(abs(ff[:,0])<=3.2)&(abs(ff[:,1])<=1.8)
        ok&=(abs(r['mirror'][:,0])<=290)&(abs((r['mirror']-m)@t)<=26)
        J=np.nan_to_num(J,nan=0,posinf=0,neginf=0)
        pix_density=1/np.maximum(np.linalg.svd(J,compute_uv=False)[:,0],1e-30)/.0016
        return ff,ok,pix_density,r

def spot_report(mapping,books):
    pts=[]
    for x in [-370.,-285.,-190.,0.,190.,285.,370.]:
        height=next(b['height'] for b in books if b['x0']<=x<=b['x1'])
        pts.extend([[x,y,60.] for y in [3.,50.,125.,190.,height-1]])
    pts=np.array(pts);ff,ok,den,r=mapping.invert(pts)
    front=r['o'];dd=r['d'];aim=front+((mapping.s[-1].z+.1-front[:,2])/dd[:,2])[:,None]*dd
    count=256
    bundle=project(np.repeat(pts,count,axis=0),mapping.s,mapping.film,mapping.layout,np.tile(disk_samples(count)*.4,(len(pts),1)),
        initial_aim=np.repeat(aim[:,:2],count,axis=0),continuation=False)
    valid=(bundle['valid']&bundle['mirror_valid']).reshape(-1,count)&ok[:,None]
    xy=bundle['film'][:,:2].reshape(-1,count,2)/.0016
    w=bundle['weight'].reshape(-1,count)*valid;sw=w.sum(axis=1)
    centre=np.sum(xy*w[:,:,None],axis=1)/np.maximum(sw[:,None],1e-20)
    radius=np.linalg.norm(xy-centre[:,None,:],axis=2);order=np.argsort(radius,axis=1)
    cumulative=np.cumsum(np.take_along_axis(w,order,axis=1),axis=1)
    k=np.argmax(cumulative>=sw[:,None]*.8,axis=1)
    d80=2*np.take_along_axis(np.take_along_axis(radius,order,axis=1),k[:,None],axis=1)[:,0]
    good=(sw>0)&ok
    return dict(points=len(pts),raysPerPoint=count,acceptedFields=int(good.sum()),
        medianGeometricD80NativePx=float(np.median(d80[good])),maxGeometricD80NativePx=float(d80[good].max()),
        minPupilFraction=float(valid[good].mean(axis=1).min()),
        rows=[dict(pointMm=p.tolist(),chiefValid=bool(v),d80NativePx=float(d) if v else None,pupilFraction=float(vf.mean())) for p,v,d,vf in zip(pts,good,d80,valid)])

def evaluate(name,prescription,render_name):
    folder=OUT/name;folder.mkdir(exist_ok=True)
    mapping=Mapping(prescription)
    gx=np.linspace(-380,380,161);gy=np.linspace(0,250,81)
    pts=np.array([[x,y,60.] for y in gy for x in gx]);ff,ok,density,r=mapping.invert(pts)
    print('MAPPED',name,ok.sum(),'/',len(ok),flush=True)
    books=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
    bookmask=np.array([any(b['x0']+.35<=x<=b['x1']-.35 and y<=b['height'] for b in books) for x,y,z in pts])
    good=ok&bookmask;values=density[good]
    observed=np.load(TRACE/(render_name+'-data.npz'));image=observed['linear'];gain=float(observed['gain'])
    hits=observed['hits'];half=observed['half_hits'];target=np.array([[any(b['x0']+.35<=(-380+(i+.5)*5)<=b['x1']-.35 and (j+.5)*2.5<=b['height'] for b in books) for i in range(152)] for j in range(100)])
    row=np.flatnonzero(observed['rowSpineHits']>0)
    reached=(hits>0)&target;reached_half=(half>0)&target
    px=ff[:,0]/.0016+1999.5;py=ff[:,1]/.0016+1124.5
    grid_valid=ok.reshape(len(gy),len(gx));inds=distance_transform_edt(~grid_valid,return_distances=False,return_indices=True)
    fx=px.reshape(len(gy),len(gx))[tuple(inds)];fy=py.reshape(len(gy),len(gx))[tuple(inds)]
    sx=RectBivariateSpline(gy,gx,fx);sy=RectBivariateSpline(gy,gx,fy)
    xx=-380+(np.arange(3040)+.5)/4;yy=250-(np.arange(1000)+.5)/4;wx,wy=np.meshgrid(xx,yy)
    mx=sx.ev(wy.ravel(),wx.ravel()).reshape(1000,3040);my=sy.ev(wy.ravel(),wx.ravel()).reshape(1000,3040)
    valid=map_coordinates(grid_valid.astype(float),[(wy/250*80),(wx+380)/760*160],order=1,mode='nearest')>.9999
    flat=map_coordinates(image,[my,mx],order=1,mode='constant',cval=0,prefilter=False)
    encoded,_=display(flat,gain);rgb=np.repeat(encoded[:,:,None],3,axis=2)
    rgba=np.dstack((rgb,np.uint8(valid)*255));Image.fromarray(rgba).save(folder/'rectified.png')
    rgb[~valid]=[239,241,232];preview=Image.fromarray(rgb);preview.thumbnail((1920,1080));preview.save(folder/'rectified-preview.jpg',quality=95)
    Image.fromarray(rgb[220:680,1100:1940]).save(folder/'centre.png')
    roi=[max(0,int(px[ok].min())-20),max(0,int(py[ok].min())-20),min(4000,int(px[ok].max())+21),min(2250,int(py[ok].max())+21)]
    original=Image.fromarray(display(image,gain)[0]);crop=original.crop(tuple(roi)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    crop.save(folder/'mirror-crop.png');crop.thumbnail((1920,1080));crop.save(folder/'mirror-crop.jpg',quality=95)
    rng=np.random.default_rng(222);tests=np.c_[rng.uniform(-375,375,100),rng.uniform(2,248,100),np.full(100,60.)]
    tf,tv,_,_=mapping.invert(tests)
    interp=np.c_[sx.ev(tests[:,1],tests[:,0]),sy.ev(tests[:,1],tests[:,0])]
    delta=np.linalg.norm(interp-(tf/.0016+[1999.5,1124.5]),axis=1)
    compare=tv&(map_coordinates(grid_valid.astype(float),[tests[:,1]/250*80,(tests[:,0]+380)/760*160],order=1)>.9999)
    rays=[];c,b,m,n,t=geometry(mapping.layout)
    for x in [-370.,0.,370.]:
        height=next(book['height'] for book in books if book['x0']<=x<=book['x1'])
        for y in [3.,125.,height-1]:
            point=np.array([[x,y,60.]]);film,visible,_,ray=mapping.invert(point)
            if not visible[0]:continue
            path=[(np.r_[film[0],mapping.film]@b.T+c).tolist()]+[(q[0]@b.T+c).tolist() for q in ray['paths'][1:]]+[ray['mirror'][0].tolist(),point[0].tolist()]
            rays.append(path)
    metrics=dict(name=name,prescription=Path(prescription).resolve().relative_to(ROOT).as_posix(),layout=mapping.layout,renderName=render_name,
        sourceRender=json.loads((TRACE/(render_name+'-render.json')).read_text()),
        sampledRayReach=float(reached.sum()/target.sum()),halfSampleReach=float(reached_half.sum()/target.sum()),targetCells=int(target.sum()),
        spineSignalVerticalSpan=float((row[-1]-row[0]+1)/len(observed['rowSpineHits'])),
        chiefCheckedPoints=int(bookmask.sum()),chiefValidPoints=int(good.sum()),chiefReach=float(good.sum()/bookmask.sum()),
        minNativePxPerMmVisible=float(values.min()),medianNativePxPerMmVisible=float(np.median(values)),
        minNativePxPerMmFull=float(values.min()) if good.sum()==bookmask.sum() else 0.,
        geometricSpots=spot_report(mapping,books),
        mapInterpolationRmsNativePx=float(np.sqrt(np.mean(delta[compare]**2))) if compare.any() else None,
        mapInterpolationMaxNativePx=float(delta[compare].max()) if compare.any() else None,
        mapCheckedValidPoints=int(compare.sum()),rayPaths=rays,
        sourceCropPixels=roi,
        correction='inverse calibration of exact chief rays onto Z=60mm reference plane; intensity from same rendered observation only; transparent regions have a blocked chief or unconverged inverse; no clean texture or book silhouette input',
        limitations=['single wavelength geometric optics, not a photograph','no full diffraction/broadband colour/sensor noise/manufacturing tolerance','reached cells are not OCR accuracy','chief-ray density does not include finite-pupil blur','inverse camera root failure is reported separately from forward-render reach'])
    (folder/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(folder/'density.npz',x=gx,y=gy,density=density.reshape(len(gy),len(gx)),valid=grid_valid,bookmask=bookmask.reshape(len(gy),len(gx)))
    print('METRICS',name,{k:metrics[k] for k in ['sampledRayReach','chiefReach','minNativePxPerMmVisible','medianNativePxPerMmVisible','spineSignalVerticalSpan']},metrics['geometricSpots']['medianGeometricD80NativePx'],flush=True)
    return metrics

def main():
    all_results=[]
    for name,prescription,render in [('baseline',ROOT/'data/optics/current-prescription.json','current-no-cylinders'),('moderate',ROOT/'data/optics/two-cylinder-prescription.json','v2-moderate-100mm'),('high',OUT/'high-final.json','v2-high')]:
        all_results.append(evaluate(name,prescription,render))
    (OUT/'comparison.json').write_text(json.dumps(all_results,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':main()
