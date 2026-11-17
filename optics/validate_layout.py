"""Dense independent field validation and finite-pupil blur comparison."""
import json
import numpy as np
from sequential import ROOT,object_to_film,disk_samples
from layout import BASELINE,geometry
from optimize_layout import density,SURFACES,FILM,OUT

def dense(layout,film):
    xs=np.linspace(-379.65,379.65,153);ys=np.linspace(0,250,101)
    points=np.array([[x,y,60.] for y in ys for x in xs])
    books=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
    mask=np.array([any(b['x0']+.35-1e-6<=x<=b['x1']-.35+1e-6 and y<=b['height'] for b in books) for x,y,z in points])
    chunks=[density(p,layout,film) for p in np.array_split(points,32)]
    result={k:np.concatenate([d[k] for d in chunks]) for k in chunks[0]}
    c,b,m,n,t=geometry(layout);uv=result['uv'];q=result['q']
    reached=result['valid']&(abs(q[:,0])<=290)&(abs((q-m)@t)<=26)&(uv[:,0]>=0)&(uv[:,0]<4000)&(uv[:,1]>=0)&(uv[:,1]<2250)
    values=result['density'][mask];idx=np.flatnonzero(mask)[np.argmin(values)]
    summary=dict(minPxPerMm=float(values.min()),p10PxPerMm=float(np.percentile(values,10)),medianPxPerMm=float(np.median(values)),
        worstPointMm=points[idx].tolist(),checkedSpinePoints=int(mask.sum()),reachedSpinePoints=int((reached&mask).sum()),coverage=float(reached[mask].mean()),
        minSensorMarginPx=float(np.min(np.c_[uv[:,0],3999-uv[:,0],uv[:,1],2249-uv[:,1]])),
        minMirrorEdgeMarginMm=float(min((290-abs(q[:,0])).min(),(26-abs((q-m)@t)).min())))
    return summary,dict(xs=xs,ys=ys,density=result['density'].reshape(len(ys),len(xs)),mask=mask.reshape(len(ys),len(xs)))

def spots(layout,film):
    points=np.array([[x,y,60.] for y in [1,50,125,200,219] for x in [-379, -285, -190,0,190,285,379]])
    c,b,m,n,t=geometry(layout)
    virt=points-2*((points-m)@n)[:,None]*n
    obj=(virt-c)@b;count=256
    r=object_to_film(np.repeat(obj,count,axis=0),np.tile(disk_samples(count)*.4,(len(obj),1)),SURFACES,film,record=True,continuation=True)
    front=r['paths'][1]@b.T+c;vv=np.repeat(virt,count,axis=0)
    d=vv-front;d/=np.linalg.norm(d,axis=1,keepdims=True)
    q=front+(((m-front)@n)/(d@n))[:,None]*d
    valid=r['valid']&(abs(q[:,0])<=290)&(abs((q-m)@t)<=26)
    xy=r['film'][:,:2].reshape(-1,count,2)/.0016
    w=(r['weight']*valid).reshape(-1,count);sw=w.sum(axis=1)
    cent=(xy*w[:,:,None]).sum(axis=1)/sw[:,None]
    radii=np.linalg.norm(xy-cent[:,None,:],axis=2);order=np.argsort(radii,axis=1)
    cum=np.cumsum(np.take_along_axis(w,order,axis=1),axis=1)/sw[:,None]
    k=np.argmax(cum>=.8,axis=1)
    d80=2*np.take_along_axis(np.take_along_axis(radii,order,axis=1),k[:,None],axis=1)[:,0]
    return dict(samplesPerObject=count,medianGeometricD80NativePx=float(np.median(d80)),maxGeometricD80NativePx=float(d80.max()),
        acceptedStopRayFractionRange=[float(valid.reshape(-1,count).mean(axis=1).min()),float(valid.reshape(-1,count).mean(axis=1).max())],
        rows=[dict(pointMm=p.tolist(),geometricD80NativePx=float(v)) for p,v in zip(points,d80)])

def main():
    candidate=json.loads((OUT/'candidate.json').read_text());new=candidate['layout'];film=candidate['film_z']
    results={}
    for name,layout,f in [('before',BASELINE,FILM),('after',new,film)]:
        print('Validate',name,flush=True)
        metrics,arrays=dense(layout,f);metrics['finitePupil']=spots(layout,f)
        metrics['layout']=layout;metrics['filmZMm']=f;results[name]=metrics
        np.savez_compressed(OUT/(name+'-density.npz'),**arrays)
    results['gainPercent']=100*(results['after']['minPxPerMm']/results['before']['minPxPerMm']-1)
    results['definition']='minimum singular value of d(native sensor pixel x,y)/d(spine mm x,y), central differences 0.1mm; minimum over actual book-spine samples; counts sampling, not resolved line pairs or OCR accuracy'
    results['search']=candidate
    (OUT/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({k:{j:v for j,v in a.items() if j not in ['finitePupil','layout']} if isinstance(a,dict) else a for k,a in results.items() if k!='search'},indent=2),flush=True)

if __name__=='__main__':main()
