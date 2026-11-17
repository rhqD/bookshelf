"""Full-field cylinder optimisation using film-to-scene ray bundles.

Forward merit avoids interpreting failed scene-to-stop root finding as vignetting.
No image rescaling is applied by the renderer; field targets only guide design.
"""
import argparse,json,time
import numpy as np
from scipy.optimize import least_squares
from sequential import trace,normalize,camera_surfaces,disk_samples
import design_cylinders_v2 as design
from layout import geometry

CAM=camera_surfaces(.3,.8)
FIELDS=design.FIELDS
base=design.base_r['film'][:,:2]
PUPIL=np.vstack(([0.,0.],disk_samples(8)*.37))
last_aim=None;calls=0;started=time.time()

def film_stop(points,pupils,film):
    """Shoot through only the camera's rear half to its physical stop."""
    o=np.c_[points,np.full(len(points),film)]
    stop=next(s.z for s in CAM if s.name=='STOP')
    target=pupils.copy()
    def run(a):return trace(o,np.c_[a,np.full(len(a),stop)]-o,CAM,apertures=False,stop_at='STOP')
    for _ in range(12):
        r=run(target);res=r['o'][:,:2]-pupils
        if np.max(np.linalg.norm(res,axis=1))<1e-9:break
        h=1e-5
        dx=(run(target+[h,0])['o'][:,:2]-r['o'][:,:2])/h
        dy=(run(target+[0,h])['o'][:,:2]-r['o'][:,:2])/h
        det=dx[:,0]*dy[:,1]-dx[:,1]*dy[:,0]
        det=np.where(abs(det)>1e-10,det,1e-10)
        step=np.c_[(dy[:,1]*res[:,0]-dy[:,0]*res[:,1])/det,(-dx[:,1]*res[:,0]+dx[:,0]*res[:,1])/det]
        target-=np.clip(step,-.5,.5)
    return o,normalize(np.c_[target,np.full(len(target),stop)]-o)

def forward(points,pupils,s,film,layout,record=True):
    origin,direction=film_stop(points,pupils,film)
    r=trace(origin,direction,s,record=record,apertures=False)
    c,b,m,n,t=geometry(layout)
    world=r['o']@b.T+c;dd=r['d']@b.T
    den=dd@n;tm=((m-world)@n)/np.where(abs(den)>1e-10,den,1e-10)
    q=world+tm[:,None]*dd
    ref=dd-2*den[:,None]*n
    tb=(60-q[:,2])/np.where(abs(ref[:,2])>1e-10,ref[:,2],1e-10)
    hit=q+tb[:,None]*ref
    r.update(hit=hit,mirror=q,mirrorDistance=tm,spineDistance=tb)
    return r

def merit(v,target):
    global calls
    calls+=1
    s,film,layout=design.build(v)
    ff=base.copy();ff[:,1]*=target
    count=len(PUPIL)
    r=forward(np.repeat(ff,count,axis=0),np.tile(PUPIL,(len(ff),1)),s,film,layout)
    hits=np.nan_to_num(r['hit'][:,:2],nan=5000,posinf=5000,neginf=-5000).reshape(-1,count,2)
    centre=hits.mean(axis=1)
    # Focus is evaluated in world millimetres. Full image coordinates are free
    # to distort moderately, but the field grid must span the whole shelf.
    spots=(hits-centre[:,None,:])
    residual=[spots.ravel()*.8,((centre-FIELDS[:,:2])/8).ravel(),
        (~r['valid']).astype(float)*100,design.geometry_residual(s,layout)]
    for sf,p in zip(s,r['paths'][1:]):
        pp=np.nan_to_num(p,nan=100)
        if sf.diameter:extra=np.maximum(np.linalg.norm(pp[:,:2],axis=1)-sf.diameter/2,0)
        else:extra=np.maximum(abs(pp[:,:2])-[sf.width/2,sf.height/2],0).sum(axis=1)
        residual.append(extra*30)
    c,b,m,n,t=geometry(layout);q=np.nan_to_num(r['mirror'],nan=1000)
    residual.extend([np.maximum(abs(q[:,0])-289,0)*20,np.maximum(abs((q-m)@t)-25,0)*20,
        np.maximum(-r['mirrorDistance'],0)*5,np.maximum(-r['spineDistance'],0)*5])
    return np.concatenate(residual)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--targets',nargs='+',type=float,default=[1.5,2.,2.5,3.]);ap.add_argument('--evaluations',type=int,default=180);ap.add_argument('--compact',action='store_true');args=ap.parse_args()
    if args.compact:design.LENS_SIZES=[(120.,14.),(420.,28.)]
    bounds=([20,50,25,-.95,-.95,6.7,0,0,-10],[400,600,170,.95,.95,7.4,45,25,6])
    if args.compact:bounds[0][2]=16.
    prev=None
    for target in args.targets:
        if prev is None and args.compact:
            v=np.r_[json.loads((design.OUT/'weak-seed.json').read_text())['variables'],0.,0.]
        else:v=design.seed(target) if prev is None else prev.copy()
        print('FORWARD START',target,v.tolist(),flush=True)
        fit=least_squares(merit,v,args=(target,),bounds=bounds,x_scale='jac',max_nfev=args.evaluations,diff_step=1e-5,ftol=1e-7,xtol=1e-7,gtol=1e-7)
        prev=fit.x
        out=design.screen(prev,target)
        out.update(optimization='full-field film-to-scene finite-pupil merit; reverse-field screen is diagnostic only',forwardMerit=float(np.linalg.norm(fit.fun)),evaluations=int(fit.nfev),calls=calls,seconds=time.time()-started)
        name=f'compact-{target:g}' if args.compact else f'forward-{target:g}'
        (design.OUT/(name+'.json')).write_text(json.dumps(out,indent=2)+'\n')
        print('FORWARD RESULT',target,{k:out[k] for k in ['variables','forwardMerit','medianGeometricRmsNativePx','maxGeometricRmsNativePx','fieldChiefCoverage','sampledCentreVerticalMagnification']},'seconds',time.time()-started,flush=True)

if __name__=='__main__':main()
