"""Maximise the minimum singular value of the native sensor Jacobian.

Every objective evaluation shoots actual chief rays through every camera surface
and its physical stop. No imposed FOV or anamorphic mapping is used.
"""
import argparse,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution, minimize
from sequential import object_to_film,camera_surfaces,disk_samples,ROOT
from layout import BASELINE,geometry

OUT=ROOT/'references/ikea-billy-oxberg/layout-optimization'
OUT.mkdir(exist_ok=True)
SURFACES=camera_surfaces(.30,.8)
OLD=json.loads((ROOT/'references/ikea-billy-oxberg/baseline-single-mirror/current-prescription.json').read_text())
FILM=OLD['film_z']

def decode(v):
    pitch,theta,cy,cz,my,mz=v
    a=np.radians(pitch);t=np.radians(theta)
    # Full camera chassis/board envelope, optical front vertex at rear=0.
    corners=np.array([[r,u] for r,half in [(3,10),(17,10),(19,12),(21,12)] for u in [-half,half]])
    dy=-corners[:,0]*np.sin(a)+corners[:,1]*np.cos(a)
    dz=corners[:,0]*np.cos(a)+corners[:,1]*np.sin(a)
    cy0=255-dy.min();cy1=324-dy.max()
    cz0=75.;cz1=256-dz.max()
    hy=26*abs(np.cos(t))+.75*abs(np.sin(t))
    hz=26*abs(np.sin(t))+.75*abs(np.cos(t))
    return dict(BASELINE,camera=[0.,cy0+cy*(cy1-cy0),cz0+cz*(cz1-cz0)],pitch_deg=float(pitch),
        mirror=[0.,255+hy+my*(324-255-2*hy),4+hz+mz*(56-4-2*hz)],tilt_deg=float(theta))

def project(points,layout,film=FILM,record=False):
    c,b,m,n,tangent=geometry(layout)
    virtual=points-2*((points-m)@n)[:,None]*n
    obj=(virtual-c)@b
    if np.any(obj[:,2]<5):return None
    r=object_to_film(obj,np.zeros((len(obj),2)),SURFACES,film,record=True,continuation=False)
    origin=r['paths'][1]@b.T+c
    d=virtual-origin;d/=np.maximum(1e-30,np.linalg.norm(d,axis=1,keepdims=True))
    den=d@n
    q=origin+(((m-origin)@n)/np.where(abs(den)>1e-12,den,1e-12))[:,None]*d
    uv=r['film'][:,:2]/.0016+np.array([1999.5,1124.5])
    return uv,r,q,origin

def density(points,layout,film=FILM):
    delta=np.array([[0,0,0],[.05,0,0],[-.05,0,0],[0,.05,0],[0,-.05,0]])
    answer=project((points[:,None,:]+delta).reshape(-1,3),layout,film)
    if answer is None:return None
    uv,r,q,origin=answer;uv=uv.reshape(-1,5,2)
    J=np.stack(((uv[:,1]-uv[:,2])/.1,(uv[:,3]-uv[:,4])/.1),axis=2)
    sv=np.linalg.svd(np.nan_to_num(J),compute_uv=False)
    return dict(uv=uv[:,0],density=sv[:,-1],J=J,valid=r['valid'].reshape(-1,5).all(axis=1),q=q[::5],origin=origin[::5])

GRID=np.array([[x,y,60.] for y in [0,50,125,200,225,240,250] for x in [-380,-285,-190,0,190,285,380]])
calls=0;best=0;start=time.time()

def objective(v):
    global calls,best
    calls+=1;l=decode(v);c,b,m,n,t=geometry(l)
    if c[2]-m[2]<40:return 10+(40-c[2]+m[2])
    d=density(GRID,l)
    if d is None:return 100.
    if not np.all(d['valid']):return 5+int((~d['valid']).sum())
    # Extra coarse-search buffer: dense validation must retain >=10px and >=1mm.
    uv=d['uv'];q=d['q']
    violation=np.r_[13-uv[:,0],uv[:,0]-3986,13-uv[:,1],uv[:,1]-2236,
        abs(q[:,0])-288.5,abs((q-m)@t)-24.5,-q[:,1],q[:,1]-328,-q[:,2],q[:,2]-260]
    penalty=np.maximum(violation,0).sum()
    if penalty>0:return 1+penalty/30
    score=float(d['density'].min())
    if score>best:
        best=score
        (OUT/'search-best.json').write_text(json.dumps(dict(layout=l,density=score,variables=list(v),calls=calls),indent=2))
        print(f'best {score:.6f} px/mm, call {calls}, {time.time()-start:.1f}s',flush=True)
    return -score

def refocus(layout):
    c,b,m,n,t=geometry(layout);p=np.array([[0.,125.,60.]])
    obj=(p-2*((p-m)@n)[:,None]*n-c)@b
    pupil=disk_samples(512)*.4
    r=object_to_film(np.repeat(obj,512,axis=0),pupil,SURFACES,FILM,continuation=True)
    valid=r['valid'];w=r['weight'][valid];w/=w.sum()
    a=r['d'][valid,:2]/r['d'][valid,2,None];bb=r['o'][valid,:2]-a*r['o'][valid,2,None]
    aa=a-np.sum(w[:,None]*a,axis=0);bc=bb-np.sum(w[:,None]*bb,axis=0)
    film=-np.sum(w[:,None]*aa*bc)/np.sum(w[:,None]*aa*aa)
    spots=a*film+bb;cent=np.sum(w[:,None]*spots,axis=0)
    return float(film),float(np.sqrt(np.sum(w*np.sum((spots-cent)**2,axis=1)))*1000)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--iterations',type=int,default=80);ap.add_argument('--seed',type=int,default=17);args=ap.parse_args()
    bounds=[(-40,40),(10,65),(0,1),(0,1),(0,1),(0,1)]
    initial=json.loads((OUT/'search-best.json').read_text())['variables'] if (OUT/'search-best.json').exists() else None
    r=differential_evolution(objective,bounds,x0=initial,popsize=10,maxiter=args.iterations,seed=args.seed,tol=1e-5,polish=False,updating='immediate')
    local=minimize(objective,r.x,method='Nelder-Mead',bounds=bounds,options={'maxiter':450,'xatol':1e-7,'fatol':1e-8})
    v=local.x if local.fun<r.fun else r.x;l=decode(v)
    film,rms=refocus(l)
    (OUT/'candidate.json').write_text(json.dumps(dict(layout=l,film_z=film,focusRmsUm=rms,objective=-objective(v),calls=calls,seconds=time.time()-start,seed=args.seed,maxGenerations=args.iterations,warmStartVariables=initial,
        scope='symmetric X=0 camera, mirror axis parallel shelf width; same lens/sensor/stop and 580x52 mirror',
        constraints='mirror/chassis at least 5mm above 250mm books, 4mm from roof/front/back envelope; full 760x250 spine rectangle, 1mm mirror and 10px sensor sampling margins',
        method='seeded differential evolution + bounded Nelder Mead; each density from exact sequential chief-ray finite-difference Jacobian; numerical candidate, not proof of global optimum'),indent=2)+'\n')
    print('CANDIDATE',json.dumps(l),film,rms,flush=True)

if __name__=='__main__':main()
