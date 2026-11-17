"""Two physical cylindrical singlets, optimised on finite pupil field bundles.

All merit values come from sequential Snell tracing, not an imposed image squeeze.
Current no-cylinder design remains untouched while candidates are evaluated.
"""
import argparse,json,time
import numpy as np
from scipy.optimize import least_squares
from dataclasses import asdict
from sequential import ROOT,Surface,camera_surfaces,object_to_film,disk_samples
from layout import active_layout,geometry
from scipy.spatial import cKDTree
from fast import pack,trace_batch
from numba import set_num_threads
set_num_threads(4)

OUT=ROOT/'references/ikea-billy-oxberg/two-cylinder-v2'
OUT.mkdir(exist_ok=True)
BASE=active_layout()
OLD=json.loads((ROOT/'data/optics/current-prescription.json').read_text())
SENSOR=np.array([3.2,1.8]);PIXEL=.0016
GLASS=1.5168
LENS_SIZES=[(120.,16.),(620.,46.)]
FIELDS=np.array([[x,y,60.] for y in [1.,125.,249.] for x in [-379.,-285.,-190.,0.,190.,285.,379.]])
PUPIL=np.vstack(([0.,0.],disk_samples(8)*.38))

def build(v):
    rr,rf,zf,br,bf,gap,shift,raise_y,pitch_offset=v
    s=camera_surfaces(.30,.8)
    cr=[(br-1)/rr,(br+1)/rr,(bf+1)/rf,(bf-1)/rf]
    zs=[8.,10.5,zf,zf+8.]
    ns=[(1,GLASS),(GLASS,1),(1,GLASS),(GLASS,1)]
    for i,(cv,z,(n1,n2)) in enumerate(zip(cr,zs,ns)):
        width,height=LENS_SIZES[i//2]
        s.append(Surface(f'L{i//2+1}-{i%2+1}',float(z),float(1/cv) if abs(cv)>1e-10 else 0.,n1,n2,'cylinder' if abs(cv)>1e-10 else 'plane',width=width,height=height))
    layout=dict(BASE,camera=[0.,BASE['camera'][1]+float(raise_y),BASE['camera'][2]+float(shift)],pitch_deg=BASE['pitch_deg']+float(pitch_offset))
    return s,s[0].z-gap,layout

def objects(points,layout):
    c,b,m,n,t=geometry(layout)
    virtual=points-2*((points-m)@n)[:,None]*n
    return (virtual-c)@b,virtual

def project(points,s,film,layout,pupil=None,apertures=True,continuation=True,initial_aim=None):
    obj,virtual=objects(points,layout)
    if pupil is None:pupil=np.zeros((len(points),2))
    r=object_to_film(obj,pupil,s,film,apertures=apertures,record=True,continuation=continuation,initial_aim=initial_aim)
    c,b,m,n,t=geometry(layout)
    origin=r['paths'][1]@b.T+c
    d=virtual-origin;d/=np.maximum(np.linalg.norm(d,axis=1,keepdims=True),1e-30)
    den=d@n;q=origin+(((m-origin)@n)/np.where(abs(den)>1e-10,den,1e-10))[:,None]*d
    r['mirror']=q;r['mirror_valid']=(abs(q[:,0])<=290)&(abs((q-m)@t)<=26)
    return r

def geometry_residual(s,layout):
    vals=[];bounds=[]
    for lens in [s[-4:-2],s[-2:]]:
        zz=[]
        for sf in lens:
            y=sf.height/2
            if sf.radius and abs(sf.radius)<=y:
                zz.append(sf.z);vals.append((y-abs(sf.radius)+1)*20)
            else:
                sag=sf.radius-np.sign(sf.radius)*np.sqrt(sf.radius**2-y*y) if sf.radius else 0.
                zz.append(sf.z+sag);vals.append(0.)
        # Both lenses keep positive thickness at their clear-aperture edge.
        vals.append(max(0,1-(zz[1]-zz[0]))*20)
        bounds.extend(zz)
    vals.append(max(0,4-min(s[-4].z,bounds[0]))*20)
    c,b,m,n,t=geometry(layout)
    vals.append(max(0,(s[-1].z+5)-np.linalg.norm(m-c))*20)
    for sf in s[-4:]:
        for sign in [-1,1]:
            p=c+b[:,2]*sf.z+b[:,1]*sign*(sf.height/2+3)
            vals.extend([max(0,252-p[1])*20,max(0,p[1]-324)*20])
    return np.array(vals)

BASE_S=camera_surfaces(.30,.8)
BASE_FILM=OLD['film_z']
base_r=project(FIELDS,BASE_S,BASE_FILM,BASE)
base_y_span=float(np.ptp(base_r['film'].reshape(3,7,3)[:,3,1]))
calls=0;start=time.time()
LOOKUP=None;AIM_CACHE=None;LAST_V=None

def forward_seed(points,s,film,layout):
    global LOOKUP
    if LOOKUP is None:
        a=np.radians(np.linspace(-66,66,89));b=np.radians(np.linspace(-35,35,65))
        obj=np.array([[400*np.tan(x),400*np.tan(y),400.] for y in b for x in a])
        r=object_to_film(obj,np.zeros((len(obj),2)),BASE_S,BASE_FILM,continuation=True)
        LOOKUP=(r['o'][r['valid']],-r['d'][r['valid']])
    rear,direction=LOOKUP
    oo=rear+((film-rear[:,2])/direction[:,2])[:,None]*direction
    raw=trace_batch(oo,direction,pack(s));ok=raw[:,7].astype(bool)
    origin=raw[ok,:3];dd=raw[ok,3:6]
    c,b,m,n,t=geometry(layout)
    world=origin@b.T+c;dw=dd@b.T;den=dw@n
    tm=((m-world)@n)/den;q=world+tm[:,None]*dw
    reflected=dw-2*den[:,None]*n
    tb=(60-q[:,2])/reflected[:,2];hit=q+tb[:,None]*reflected
    valid=(tm>0)&(tb>0)&np.isfinite(hit).all(axis=1)
    # Ignore finite M1 here only to seed Newton; final tracing checks aperture.
    aim=origin+((s[-1].z+.1-origin[:,2])/dd[:,2])[:,None]*dd
    assert valid.sum()>30,'Too few physical forward rays for inversion seed.'
    tree=cKDTree(hit[valid,:2]);_,index=tree.query(points[:,:2])
    return aim[valid,:2][index]

def merit(v,target):
    global calls,AIM_CACHE,LAST_V
    calls+=1
    s,film,layout=build(v)
    n=len(PUPIL);pts=np.repeat(FIELDS,n,axis=0);pup=np.tile(PUPIL,(len(FIELDS),1))
    if AIM_CACHE is None or LAST_V is None or np.linalg.norm((v-LAST_V)/[100,200,100,1,1,.3,40,20,10])>.15:
        AIM_CACHE=np.repeat(forward_seed(FIELDS,s,film,layout),n,axis=0)
    r=project(pts,s,film,layout,pup,apertures=False,continuation=False,initial_aim=AIM_CACHE)
    if r['converged'].mean()>.9:AIM_CACHE=r['shooting_aim'];LAST_V=v.copy()
    xy=np.nan_to_num(r['film'][:,:2],nan=100,posinf=100,neginf=-100).reshape(-1,n,2)
    spots=(xy-xy.mean(axis=1,keepdims=True))/PIXEL
    centre=xy[:,0]
    magnification=np.ptp(centre.reshape(3,7,2)[:,3,1])/base_y_span
    # Match magnification, but use real full-field blur and finite apertures.
    terms=[spots.ravel(),np.array([(magnification-target)*120]),
           np.maximum(abs(centre)-[3.18,1.76],0).ravel()/PIXEL,
           (~r['valid']).astype(float)*50,geometry_residual(s,layout)]
    for sf,path in zip(reversed(s),r['paths'][1:]):
        pp=np.nan_to_num(path,nan=100)
        if sf.diameter:
            excess=np.maximum(np.linalg.norm(pp[:,:2],axis=1)-sf.diameter/2,0)
        else:excess=np.maximum(abs(pp[:,:2])-[sf.width/2,sf.height/2],0).sum(axis=1)
        terms.append(excess*20)
    q=np.nan_to_num(r['mirror'],nan=1000);c,b,m,normal,t=geometry(layout)
    terms.extend([np.maximum(abs(q[:,0])-289,0)*20,np.maximum(abs((q-m)@t)-25,0)*20])
    return np.concatenate(terms)

def seed(target):
    # Finite-conjugate axial starting point only. Full-field merit follows.
    front_r=200.;rear_r=front_r/target
    guess=np.array([rear_r,front_r,8.+max(17.,(front_r-rear_r)/(2*(GLASS-1))),0.,0.,6.95,35.,14.,-4.])
    def axis(v):
        vv=guess.copy();vv[[0,2,5]]=v
        s,f,l=build(vv)
        distance=objects(np.array([[0.,125.,60.]]),l)[0][0,2]
        pts=np.array([[0.,0.,distance]]*4+[[.1,0,distance],[0,.1,distance]])
        pup=np.array([[.15,0],[-.15,0],[0,.15],[0,-.15],[0,0],[0,0]])
        r=object_to_film(pts,pup,s,f,apertures=False,continuation=False)
        xy=r['film'][:,:2]
        ratio=xy[5,1]/xy[4,0]
        return np.nan_to_num([xy[0,0]-xy[1,0],xy[2,1]-xy[3,1],(ratio-target)*.01],nan=100)
    r=least_squares(axis,guess[[0,2,5]],bounds=([20,25,6.7],[400,170,7.4]),max_nfev=100,diff_step=1e-4)
    guess[[0,2,5]]=r.x
    return guess

def screen(v,target):
    s,film,layout=build(v)
    seed_aim=forward_seed(FIELDS,s,film,layout)
    r=project(np.repeat(FIELDS,65,axis=0),s,film,layout,np.tile(np.vstack(([0,0],disk_samples(64)*.4)),(len(FIELDS),1)),initial_aim=np.repeat(seed_aim,65,axis=0),continuation=False)
    valid=(r['valid']&r['mirror_valid']).reshape(-1,65)
    xy=r['film'][:,:2].reshape(-1,65,2)
    w=r['weight'].reshape(-1,65)*valid;sw=w.sum(axis=1)
    centre=np.sum(xy*w[:,:,None],axis=1)/np.maximum(sw[:,None],1e-30)
    rms=np.sqrt(np.sum(w*np.sum((xy-centre[:,None,:])**2,axis=2),axis=1)/np.maximum(sw,1e-30))/PIXEL
    chief=xy[:,0];sensor=np.all(abs(chief)<SENSOR,axis=1)
    magnification=float(np.ptp(chief.reshape(3,7,2)[:,3,1])/base_y_span)
    return dict(target=target,variables=v.tolist(),layout=layout,film_z=float(film),
        surfaces=[asdict(sf) for sf in s],parameters=dict(scale=.30,stop=.8,film_gap=float(s[0].z-film)),
        wavelength_nm=587.6,sensor_mm=[6.4,3.6],sensor_pixels=[4000,2250],glass='N-BK7 d-line n=1.51680; camera indices from PBRT research prescription',
        sampledCentreVerticalMagnification=magnification,
        fieldChiefCoverage=float(np.mean(valid[:,0]&sensor)),minPupilFraction=float(valid.mean(axis=1).min()),
        medianGeometricRmsNativePx=float(np.median(rms)),maxGeometricRmsNativePx=float(np.max(rms)),
        allFieldRmsNativePx=rms.tolist(),allFieldChiefValid=(valid[:,0]&sensor).tolist(),
        mechanicalResidual=float(np.max(geometry_residual(s,layout))),
        note='new full-field finite-pupil two-singlet trial; no imposed squeeze; not a production optical module')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--targets',type=float,nargs='+',default=[1.25,1.5,1.75,2.,2.5]);ap.add_argument('--evaluations',type=int,default=100);args=ap.parse_args()
    bounds=([20.,50.,25.,-.95,-.95,6.7,0.,0.,-10.],[400.,600.,170.,.95,.95,7.4,45.,25.,6.])
    all_results=[];previous=None
    for target in args.targets:
        initial=seed(target) if previous is None else previous.copy()
        print('OPTIMISE',target,'seed',initial.tolist(),flush=True)
        fit=least_squares(merit,initial,args=(target,),bounds=bounds,max_nfev=args.evaluations,diff_step=1e-5,x_scale='jac',ftol=2e-7,xtol=2e-7,gtol=1e-6)
        previous=fit.x
        result=screen(fit.x,target);result.update(merit=float(np.linalg.norm(fit.fun)),optimizerSuccess=bool(fit.success),evaluations=int(fit.nfev),calls=calls,elapsedSeconds=time.time()-start)
        file=OUT/f'candidate-{target:g}.json';file.write_text(json.dumps(result,indent=2)+'\n')
        all_results.append({k:v for k,v in result.items() if k not in ['surfaces','allFieldRmsNativePx','allFieldChiefValid']})
        (OUT/'search-summary.json').write_text(json.dumps(all_results,indent=2)+'\n')
        print('RESULT',json.dumps(all_results[-1]),flush=True)

if __name__=='__main__':main()
