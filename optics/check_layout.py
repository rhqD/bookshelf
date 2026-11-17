"""Check new scene transforms, reciprocal rays, finite apertures and Jacobians."""
import json
import numpy as np
from numba import set_num_threads
from sequential import ROOT,trace,object_to_film,reflect_points,to_local,LAYOUT,C,BASIS,M,N,TANGENT
from evaluate import load_design
from fast import pack,trace_batch,scene_ray
from layout import packed
from render import books_and_textures
from optimize_layout import density

set_num_threads(4)
p,s,film=load_design(ROOT/'data/optics/current-prescription.json')
assert all(ss.kind!='cylinder' for ss in s)
books,textures=books_and_textures()
points=np.array([[(b[0]+b[1])/2,y,60.] for b in books for y in [5.,125.,b[2]-1]])
obj=to_local(reflect_points(points))
r=object_to_film(obj,np.zeros((len(obj),2)),s,film,record=True)
assert r['valid'].all()
back=trace(r['film'],-r['d'],s)
assert back['valid'].all()
fast=trace_batch(r['film'],-r['d'],pack(s))
assert fast[:,7].astype(bool).all()
np.testing.assert_allclose(fast[:,:3],back['o'],atol=1e-8)
np.testing.assert_allclose(fast[:,3:6],back['d'],atol=1e-8)
np.testing.assert_allclose(fast[:,6],back['weight'],atol=1e-10)
for i in range(len(points)):
    lum,bid,hx,hy=scene_ray(*back['o'][i],*back['d'][i],books,textures,packed(LAYOUT))
    assert bid>=0
    np.testing.assert_allclose([hx,hy],points[i,:2],atol=1e-6)
# Mechanical envelopes, including 1.5mm mirror thickness and full camera PCB.
corners=np.array([M+x*np.array([1,0,0])+y*TANGENT+z*N for x in [-290,290] for y in [-26,26] for z in [-.75,.75]])
assert corners[:,1].min()>=255 and corners[:,1].max()<=324
assert corners[:,2].min()>=4 and corners[:,2].max()<=56
body=np.array([C+x*BASIS[:,0]+u*BASIS[:,1]-r*BASIS[:,2] for r,h in [(3,10),(17,10),(19,12),(21,12)] for u in [-h,h] for x in [-16,16]])
assert body[:,1].min()>=255 and body[:,1].max()<=324
assert body[:,2].min()>=4 and body[:,2].max()<=256
validation=json.loads((ROOT/'references/ikea-billy-oxberg/layout-optimization/validation.json').read_text())
a=validation['after'];assert a['coverage']==1 and a['minSensorMarginPx']>=10 and a['minMirrorEdgeMarginMm']>=1
probe=np.array([[-379.65,0.,60.],[0,125,60.],[350,125,60.]])
d=density(probe,LAYOUT,film)
# Independent, smaller finite differences validate the objective's scale.
from optimize_layout import project
uv=[]
for offset in [[.01,0,0],[-.01,0,0],[0,.01,0],[0,-.01,0]]:
    uv.append(project(probe+offset,LAYOUT,film)[0])
J=np.stack(((uv[0]-uv[1])/.02,(uv[2]-uv[3])/.02),axis=2)
np.testing.assert_allclose(J,d['J'],rtol=1e-6,atol=1e-7)
np.testing.assert_allclose(d['density'][0],a['minPxPerMm'],rtol=1e-7)
print(json.dumps(dict(reciprocalBookRays=len(points),numpyNumbaAgreement=True,mechanicalEnvelope=True,denseSpinePoints=a['checkedSpinePoints'],minNativePxPerMm=a['minPxPerMm'],gainPercent=validation['gainPercent']),indent=2))
