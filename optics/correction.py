"""Image-only reconstruction with a space-variant, ray-traced linear operator.

Inputs: the saved linear sensor observation, surface prescription, and geometry.
No book textures, titles, clean render, character dictionary or learned image
generator is read by this module. Ground truth belongs to assessment only.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import time
import numpy as np
from scipy import sparse
from scipy.stats import qmc
from PIL import Image
from numba import njit, prange, set_num_threads
from sequential import ROOT
from evaluate import load_design
from fast import one_ray, scene_ray, pack

OUT=ROOT/'references/ikea-billy-oxberg/correction'
TRACE=ROOT/'references/ikea-billy-oxberg/sequential-trace'
OUT.mkdir(exist_ok=True)
PPM=4
OW,OH=760*PPM,250*PPM
SW,SH=2000,1125
CACHE_TAG=f'{PPM}ppm-256'


def geometry():
    source=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
    books=np.array([[b['x0']+.35,b['x1']-.35,b['height']] for b in source])
    xx=-380+(np.arange(OW)+.5)/PPM
    yy=250-(np.arange(OH)+.5)/PPM
    labels=np.full((OH,OW),-1,np.int16)
    for i,b in enumerate(books):
        inside=(yy[:,None]<=b[2])&(xx[None,:]>=b[0])&(xx[None,:]<=b[1])
        labels[inside]=i
    return books,labels


@njit(cache=True,parallel=True)
def operator_rows(y0,y1,surfaces,film_z,bounds,samples,books,labels):
    ns=len(samples);n=(y1-y0)*SW
    # Raw row entries; SciPy coalesces repeated image cells afterward.
    indices=np.zeros((n,ns*4),np.int32)
    weights=np.zeros((n,ns*4),np.float32)
    background=np.zeros(n,np.float32)
    moments=np.zeros((n,4),np.float64) # gain, gain*x, gain*y, gain*(x²+y²)
    empty=np.zeros((len(books),1,1),np.uint8) # Explicitly zero; no text input.
    nr=len(bounds);maxr=math.sqrt(3.2**2+1.8**2)
    for row in prange(n):
        yy=y0+row//SW;xx=row%SW
        hsh=(xx*831557 ^ yy*938531)&0x7fffffff
        shift1=(hsh%100003)/100003.;shift2=((hsh//100003)%100019)/100019.
        for ss in range(ns):
            # Integrate the same 2×2 original native-pixel centres, with an
            # independent rear-pupil quadrature (not the rendering seed).
            sub=ss%4
            film_x=((xx+.5)/SW-.5)*6.4+((sub%2)-.5)*.0016
            film_y=((yy+.5)/SH-.5)*3.6+((sub//2)-.5)*.0016
            rr=math.sqrt(film_x*film_x+film_y*film_y)
            aa=min(nr-1.000001,rr/maxr*(nr-1));j=int(aa);aa-=j
            qmin=bounds[j,0]*(1-aa)+bounds[j+1,0]*aa
            qmax=bounds[j,1]*(1-aa)+bounds[j+1,1]*aa
            qtan=bounds[j,2]*(1-aa)+bounds[j+1,2]*aa
            ux=film_x/rr if rr>1e-12 else 1.;uy=film_y/rr if rr>1e-12 else 0.
            qr=qmin+((samples[ss,0]+shift1)%1.)*(qmax-qmin)
            qt=(((samples[ss,1]+shift2)%1.)*2-1)*qtan
            px=qr*ux-qt*uy;py=qr*uy+qt*ux
            dx=px-film_x;dy=py-film_y;dz=surfaces[0,0]-film_z
            ll=math.sqrt(dx*dx+dy*dy+dz*dz)
            cos4=(dz/ll)**4
            x,y,z,dx,dy,dz,power,valid,reason=one_ray(film_x,film_y,film_z,dx,dy,dz,surfaces)
            if not valid:continue
            lum,bid,hx,hy=scene_ray(x,y,z,dx,dy,dz,books,empty)
            weight=power*cos4*(qmax-qmin)*2*qtan/(surfaces[0,0]-film_z)**2/ns
            if bid<0:
                background[row]+=weight*lum
                continue
            weight*=.92 # All front-spine hits in this geometry are via M1.
            gx=(hx+380)*PPM-.5;gy=(250-hy)*PPM-.5
            ix=int(math.floor(gx));iy=int(math.floor(gy));fx=gx-ix;fy=gy-iy
            norm=0.
            for v in range(2):
                for u in range(2):
                    cx=ix+u;cy=iy+v
                    if 0<=cx<OW and 0<=cy<OH and labels[cy,cx]==bid:
                        norm+=(fx if u else 1-fx)*(fy if v else 1-fy)
            if norm<=1e-15:continue
            for v in range(2):
                for u in range(2):
                    cx=ix+u;cy=iy+v
                    if 0<=cx<OW and 0<=cy<OH and labels[cy,cx]==bid:
                        at=ss*4+v*2+u
                        indices[row,at]=cy*OW+cx
                        weights[row,at]=weight*(fx if u else 1-fx)*(fy if v else 1-fy)/norm
            moments[row,0]+=weight;moments[row,1]+=weight*hx;moments[row,2]+=weight*hy
            moments[row,3]+=weight*(hx*hx+hy*hy)
    return indices,weights,background,moments


def build_operator(spp=256):
    operator_path=OUT/f'operator-{PPM}ppm-{spp}.npz'
    extra_path=OUT/f'operator-{PPM}ppm-{spp}-meta.npz'
    if operator_path.exists() and extra_path.exists():
        return sparse.load_npz(operator_path),dict(np.load(extra_path))
    p,s,film=load_design(ROOT/'data/optics/final-prescription.json')
    books,labels=geometry()
    raw=np.load(TRACE/'sensor-data.npz')['linear']
    observation=raw.reshape(SH,2,SW,2).mean((1,3))
    nz=np.flatnonzero(raw.max(1)>0)
    lo=max(0,int(nz[0]//2)-3);hi=min(SH,int(nz[-1]//2)+4)
    bounds=np.load(TRACE/'sensor-pupil-bounds.npy')
    samples=qmc.Sobol(2,scramble=True,seed=94183).random_base2(int(np.ceil(np.log2(spp))))[:spp]
    chunks=[];bg=[];stats=[];start=time.time()
    for y0 in range(lo,hi,4):
        y1=min(hi,y0+4)
        idx,w,b,m=operator_rows(y0,y1,pack(s),film,bounds,samples,books,labels)
        n=len(idx);indptr=np.arange(n+1,dtype=np.int64)*(spp*4)
        a=sparse.csr_matrix((w.ravel(),idx.ravel(),indptr),shape=(n,OW*OH))
        a.sum_duplicates();a.eliminate_zeros();chunks.append(a);bg.append(b);stats.append(m)
        if (y0-lo)%32==0:print(f'operator rows {y1}/{hi}, nnz {sum(c.nnz for c in chunks):,}, {time.time()-start:.1f}s',flush=True)
    A=sparse.vstack(chunks,format='csr');background=np.concatenate(bg);moments=np.concatenate(stats)
    gain=moments[:,0]
    scale=float(np.percentile(gain[gain>0],90))
    A.data/=scale;background/=scale;observation=observation[lo:hi].ravel()/scale
    meta=dict(observation=observation.astype('float32'),background=background,
              moments=moments,labels=labels,lo=np.array(lo),hi=np.array(hi),scale=np.array(scale),
              row_gain=gain/scale)
    sparse.save_npz(operator_path,A)
    np.savez_compressed(extra_path,**meta)
    print('OPERATOR DONE',A.shape,A.nnz,'seconds',time.time()-start,flush=True)
    return A,meta


@njit(cache=True)
def geometric_unwrap(values,moments,lo,hi,labels):
    gain=moments[:,0]
    ref=0.
    for g in gain:ref=max(ref,g)
    out=np.zeros((OH,OW),np.float32);score=np.full((OH,OW),1e20,np.float32)
    support=np.zeros((OH,OW),np.uint8)
    for yy in range(hi-lo-1):
        for xx in range(SW-1):
            root=yy*SW+xx
            for triangle in range(2):
                ids=(root,root+1,root+SW) if triangle==0 else (root+SW+1,root+SW,root+1)
                ids0,ids1,ids2=ids
                if min(gain[ids0],gain[ids1],gain[ids2])<ref*.005:continue
                xs=np.zeros(3);ys=np.zeros(3);sigmas=np.zeros(3)
                good=True
                for k in range(3):
                    i=ids[k];cx=moments[i,1]/gain[i];cy=moments[i,2]/gain[i]
                    if abs(cx)>390 or not -5<=cy<=255:good=False;break
                    xs[k]=(cx+380)*PPM-.5;ys[k]=(250-cy)*PPM-.5
                    sigmas[k]=math.sqrt(max(0.,moments[i,3]/gain[i]-cx*cx-cy*cy))
                if not good:continue
                if max(xs)-min(xs)>100 or max(ys)-min(ys)>100:continue
                det=(ys[1]-ys[2])*(xs[0]-xs[2])+(xs[2]-xs[1])*(ys[0]-ys[2])
                if abs(det)<1e-6:continue
                for gy in range(max(0,int(math.floor(min(ys)))),min(OH-1,int(math.ceil(max(ys))))+1):
                    for gx in range(max(0,int(math.floor(min(xs)))),min(OW-1,int(math.ceil(max(xs))))+1):
                        if labels[gy,gx]<0:continue
                        b0=((ys[1]-ys[2])*(gx-xs[2])+(xs[2]-xs[1])*(gy-ys[2]))/det
                        b1=((ys[2]-ys[0])*(gx-xs[2])+(xs[0]-xs[2])*(gy-ys[2]))/det
                        b2=1-b0-b1
                        if min(b0,b1,b2)<-1e-7:continue
                        ss=b0*sigmas[0]+b1*sigmas[1]+b2*sigmas[2]
                        if ss<score[gy,gx]:
                            out[gy,gx]=max(0.,b0*values[ids0]+b1*values[ids1]+b2*values[ids2])
                            score[gy,gx]=ss;support[gy,gx]=1
    return out,support,score


def display_object(image,support,labels,path):
    # Identical fixed radiometric display for geometry and deconvolution.
    v=np.maximum(0,image)
    srgb=np.where(v<=.0031308,12.92*v,1.055*v**(1/2.4)-.055)
    grey=np.uint8(np.clip(srgb,0,1)*255+.5)
    rgb=np.repeat(grey[:,:,None],3,axis=2)
    missing=(labels>=0)&~support
    yy,xx=np.indices(labels.shape);hatch=((xx+yy)%16)<2
    rgb[missing]=[207,208,199];rgb[missing&hatch]=[185,188,179]
    rgb[labels<0]=[239,241,232]
    Image.fromarray(rgb).save(path)


def poisson_objective(y,pred):
    return float(np.sum(pred-y*np.log(np.maximum(pred,1e-8))))


def masked_tv_prox(image,labels,support,weight=.004,iterations=22):
    """Label-free TV proximal step; no gradient across book / coverage edges."""
    f=image.copy();u=f.copy();bar=u.copy()
    px=np.zeros_like(f);py=np.zeros_like(f)
    validx=support[:,:-1]&support[:,1:]&(labels[:,:-1]==labels[:,1:])
    validy=support[:-1,:]&support[1:,:]&(labels[:-1,:]==labels[1:,:])
    for _ in range(iterations):
        px[:,:-1]+=.25*(bar[:,1:]-bar[:,:-1])*validx
        py[:-1,:]+=.25*(bar[1:,:]-bar[:-1,:])*validy
        norm=np.maximum(1,np.sqrt(px*px+py*py)/weight)
        px/=norm;py/=norm
        div=px+py
        div[:,1:]-=px[:,:-1];div[1:,:]-=py[:-1,:]
        unew=(u+.25*div+.25*f)/1.25
        unew[~support]=0
        bar=2*unew-u;u=unew
    return u


def reconstruct(A,meta,iterations=80):
    y=meta['observation'].astype('float32');b=meta['background'].astype('float32')
    gain=np.asarray(A.sum(axis=1)).ravel();normal=np.asarray(A.sum(axis=0)).ravel()
    labels=meta['labels'];support=(normal.reshape(OH,OW)>np.max(normal)*1e-6)&(labels>=0)
    normal=np.maximum(normal,1e-12)
    # No book-specific seed: all observed object cells start at one constant.
    constant=float(np.median(np.clip((y-b)[gain>.1]/gain[gain>.1],0,1)))
    x=np.full(OW*OH,constant,np.float32);x[~support.ravel()]=0
    At=A.T.tocsr();history=[];checkpoints={}
    for k in range(iterations):
        pred=np.maximum(A@x+b,1e-8)
        ratio=np.clip(y/pred,0,20)
        x*=np.asarray(At@ratio).ravel()/normal
        x=np.clip(x,0,1.0)
        x[~support.ravel()]=0
        # The same fixed TV penalty for all books; no character/word templates.
        if k%8==7:
            x=masked_tv_prox(x.reshape(OH,OW),labels,support,.004).ravel()
        if (k+1)%10==0 or k==0:
            pred=np.maximum(A@x+b,1e-8)
            dev=float(np.sqrt(np.mean((pred-y)**2)))
            loss=poisson_objective(y,pred)
            history.append(dict(iteration=k+1,forwardRmse=dev,poissonObjective=loss))
            print('ITER',k+1,'forward RMSE',dev,'loss',loss,flush=True)
        if k+1 in [40,80,160,240]:checkpoints[k+1]=x.copy()
    return x.reshape(OH,OW),support,history,checkpoints,constant


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spp',type=int,default=256);ap.add_argument('--iterations',type=int,default=80);args=ap.parse_args()
    set_num_threads(8)
    A,meta=build_operator(args.spp)
    y=meta['observation'];b=meta['background'];g=np.asarray(A.sum(1)).ravel()
    values=np.maximum(0,y-b)/np.maximum(g,1e-9)
    geo,geo_support,geo_score=geometric_unwrap(values,meta['moments'],int(meta['lo']),int(meta['hi']),meta['labels'])
    display_object(geo,geo_support.astype(bool),meta['labels'],OUT/'geometry.png')
    recon,support,history,checkpoints,constant=reconstruct(A,meta,args.iterations)
    display_object(recon,support,meta['labels'],OUT/'deconvolution.png')
    np.savez_compressed(OUT/'reconstruction.npz',geometry=geo,geometry_support=geo_support,geometry_score=geo_score,
        deconvolution=recon,support=support,labels=meta['labels'],**{f'iteration_{k}':v.reshape(OH,OW) for k,v in checkpoints.items()})
    # Adjointness is a numerical requirement of the iterative inverse.
    rng=np.random.default_rng(879);xx=rng.random(A.shape[1],dtype='float32');vv=rng.random(A.shape[0],dtype='float32')
    left=float(np.dot(A@xx,vv));right=float(np.dot(xx,A.T@vv));adjoint_error=abs(left-right)/max(abs(left),abs(right))
    assert adjoint_error<2e-5
    metadata=dict(method='space-variant ray-traced Richardson-Lucy / nonnegative Poisson EM, early stopping + masked total-variation proximal steps',
        iterations=args.iterations,tvWeight=.004,tvStepEvery=8,quadratureRaysPerWorkingSensorBin=args.spp,sensorBinning='exact 2×2 mean of the saved 4000×2250 linear observation',
        workingSensor=[SW,SH],objectPlanePixels=[OW,OH],objectPixelMm=1/PPM,
        operatorShape=list(A.shape),nonzeroCoefficients=A.nnz,background='computed from texture-free cabinet/book-box geometry; foreground title textures never read',
        geometry='piecewise affine unwrap of finite-pupil response centroids; minimum-footprint branch selected on overlaps; same flat-field compensation',
        reconstructionInput=['saved linear sensor observation','optical surfaces','book/cabinet geometry','independent pupil sampling, seed 94183'],
        prohibitedInputsNotUsed=['clean book textures','book titles','clean spine render','character dictionary','generative super-resolution'],
        initializationConstant=constant,display='same fixed linear→sRGB curve for both flattened outputs; grey hatching marks missing support',
        rawObservation='original saved noiseless monochrome geometric ray render; this is an optimistic exact-calibration test, not measured camera RAW',
        limitations=['no real shot/read noise','no calibration error','no full wave diffraction or color','finite independent ray quadrature and 0.5 mm object grid','regularization can sharpen artifacts; pixel detail is not proof of a correct title'],
        relativeAdjointError=adjoint_error,history=history,
        hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['data/optics/final-prescription.json','references/ikea-billy-oxberg/sequential-trace/sensor-data.npz']})
    (OUT/'correction-settings.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print('DONE correction',metadata['operatorShape'],metadata['nonzeroCoefficients'],flush=True)


if __name__=='__main__':main()
