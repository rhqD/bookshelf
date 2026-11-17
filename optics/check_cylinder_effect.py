"""Numerical/physical invariants for the new two-cylinder rendered cases."""
import json
import numpy as np
from sequential import ROOT,Surface,trace,normalize,disk_samples
from fast import pack,trace_batch
from forward_cylinder_design import film_stop
from layout import geometry

OUT=ROOT/'references/ikea-billy-oxberg/two-cylinder-v2'
rng=np.random.default_rng(83)
checks=[]
for filename in ['moderate-safe.json','forward-2.json']:
    p=json.loads((OUT/filename).read_text());s=[Surface(**v) for v in p['surfaces']];film=p['film_z']
    assert len([sf for sf in s if sf.n_before!=sf.n_after])==15
    assert len([sf for sf in s if sf.kind=='cylinder'])==4
    o=np.c_[rng.uniform([-3.1,-1.6],[3.1,1.6],(1500,2)),np.full(1500,film)]
    target=np.c_[rng.uniform(-1,1,(1500,2)),np.full(1500,s[0].z)]
    direction=normalize(target-o);a=trace(o,direction,s);b=trace_batch(o,direction,pack(s))
    assert np.array_equal(a['valid'],b[:,7].astype(bool))
    v=a['valid'];assert v.sum()>20
    error=float(np.max(abs(a['o'][v]-b[v,:3])));assert error<1e-7
    back=trace(a['o'][v],-a['d'][v],s,reverse=True)
    t=(film-back['o'][:,2])/back['d'][:,2];points=back['o']+t[:,None]*back['d']
    reciprocal=float(np.max(abs(points-o[v])));assert reciprocal<1e-7
    xy=np.array([[x,y] for x in [-3.,0.,3.] for y in [-1.,0.,1.]])
    pupils=np.tile(disk_samples(16)*.38,(len(xy),1));ff=np.repeat(xy,16,axis=0)
    oo,dd=film_stop(ff,pupils,film);stop=trace(oo,dd,s,stop_at='STOP',apertures=False)
    stop_error=float(np.linalg.norm(stop['o'][:,:2]-pupils,axis=1).max());assert stop_error<1e-7
    checks.append(dict(case=filename,independentRays=1500,comparedValidRays=int(v.sum()),numpyNumbaPositionErrorMm=error,reciprocalPositionErrorMm=reciprocal,stopShootingErrorMm=stop_error))
data=json.loads((OUT/'comparison.json').read_text())
for d in data:
    p=json.loads((ROOT/d['prescription']).read_text());c,b,m,n,t=geometry(p.get('layout',d['layout']))
    for path in d['rayPaths']:
        before,q,end=np.array(path[-3:]);incoming=normalize((q-before)[None])[0];out=normalize((end-q)[None])[0]
        np.testing.assert_allclose(incoming-2*np.dot(incoming,n)*n,out,atol=1e-8)
    assert d['sourceRender']['width']==4000 and d['sourceRender']['height']==2250
    assert d['sourceRender']['samplesPerPixel']==64
    assert abs(d['sampledRayReach']-d['halfSampleReach'])<.001
    assert d['mapCheckedValidPoints']>40
result=dict(cases=checks,allMirrorPathsObeyReflection=True,samplingCoverageConvergenceWithin=.001,
    limitations='numerical invariants only; no commercial optical-code or hardware cross-validation')
(OUT/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
