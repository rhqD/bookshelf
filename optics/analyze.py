"""Finite-pupil response, geometric MTF, coverage and auditable prescriptions."""
import json
import numpy as np
from scipy.stats import qmc
from PIL import Image
from sequential import (ROOT, design, asdict, normalize, trace, object_points,
                        object_to_film, disk_samples, to_shelf)
from evaluate import (OUT, load_design, to_spine_plane, summary, PIXEL_MM,
                      SENSOR_W, SENSOR_H)
from render import pupil_bounds, books_and_textures
from fast import pack, trace_batch

P,S,FILM=load_design(ROOT/'data/optics/final-prescription.json')
BOUNDS=pupil_bounds(S,FILM)
SOBOL=qmc.Sobol(2,scramble=True,seed=301).random_base2(11)


def response(film_points,count=1024,return_bundle=False):
    film_points=np.asarray(film_points,float).reshape(-1,2)
    rr=np.linalg.norm(film_points,axis=1);maximum=np.hypot(3.2,1.8)
    params=np.stack([np.interp(rr,np.linspace(0,maximum,len(BOUNDS)),BOUNDS[:,i]) for i in range(3)],axis=1)
    ux=np.divide(film_points[:,0],rr,out=np.ones(len(rr)),where=rr>1e-12)
    uy=np.divide(film_points[:,1],rr,out=np.zeros(len(rr)),where=rr>1e-12)
    qr=params[:,0,None]+SOBOL[None,:count,0]*(params[:,1]-params[:,0])[:,None]
    qt=(SOBOL[None,:count,1]*2-1)*params[:,2,None]
    px=qr*ux[:,None]-qt*uy[:,None];py=qr*uy[:,None]+qt*ux[:,None]
    origins=np.repeat(np.c_[film_points,np.full(len(rr),FILM)],count,axis=0)
    targets=np.c_[px.ravel(),py.ravel(),np.full(len(rr)*count,S[0].z)]
    directions=normalize(targets-origins)
    raw=trace_batch(origins,directions,pack(S))
    r=dict(o=raw[:,:3],d=raw[:,3:6],valid=raw[:,7].astype(bool),weight=raw[:,6]*abs(directions[:,2])**4)
    pts,ok,mirror,dd=to_spine_plane(r)
    weights=(r['weight']*ok).reshape(-1,count)
    bundle=dict(points=pts.reshape(-1,count,3),valid=ok.reshape(-1,count),weight=weights,film=film_points)
    result=summary(bundle)
    area=(params[:,1]-params[:,0])*2*params[:,2]
    result['throughput']*=area/(S[0].z-FILM)**2
    if return_bundle:return result,bundle,raw,directions
    return result


def detailed_fields():
    fields=np.array([[x,y] for y in [-.3,-.15,0,.15,.3] for x in [-2.4,-1.6,-.8,0,.8,1.6,2.4]])
    r,b,raw,direction=response(fields,2048,True)
    xp=response(fields+[PIXEL_MM,0],2048)
    yp=response(fields+[0,PIXEL_MM],2048)
    rows=[]
    for i,f in enumerate(fields):
        sw=b['weight'][i].sum();cent=r['centroid'][i,:2]
        J=np.stack([xp['centroid'][i,:2]-cent,yp['centroid'][i,:2]-cent],axis=1)
        invertible=abs(np.linalg.det(J))>1e-10 and np.linalg.cond(J)<100
        char_pixels=None;equivalent_d80=None
        if invertible and r['valid_count'][i]>32:
            inv=np.linalg.inv(J);char_pixels=float(np.linalg.norm(inv@np.array([0.,7.])))
            pix=(b['points'][i,:,:2]-cent)@inv.T
            radius=np.linalg.norm(pix,axis=1);order=np.argsort(radius);cdf=np.cumsum(b['weight'][i,order]);k=np.searchsorted(cdf,.8*sw)
            equivalent_d80=float(2*radius[order[min(k,len(order)-1)]])
        in_book=bool(-380<=cent[0]<=380 and 0<=cent[1]<=250)
        rows.append(dict(sensorMm=f.tolist(),sensorPixel=[float((f[0]/6.4+.5)*4000),float((f[1]/3.6+.5)*2250)],
            objectCentroidMm=cent.tolist(),validRays=int(r['valid_count'][i]),rays=2048,
            objectD80Mm=float(r['d80'][i]) if sw else None,objectRmsMm=float(r['rms'][i]) if sw else None,
            geometricMtfAtHalfCyclePerMmX=float(r['mtf_x'][i]),geometricMtfAtHalfCyclePerMmY=float(r['mtf_y'][i]),
            nominal7mmCharacterPixels=char_pixels,localEquivalentD80Pixels=equivalent_d80,
            inBookEnvelope=in_book,relativeThroughput=float(r['throughput'][i]/max(r['throughput'][17],1e-30))))
    centre=17
    ray_slice=slice(centre*2048,(centre+1)*2048);valid=b['valid'][centre]
    dd=direction[ray_slice][valid]
    # Central image-space NA, inferred from accepted rays incident on the film.
    theta_x=np.arctan2(dd[:,0],dd[:,2]);theta_y=np.arctan2(dd[:,1],dd[:,2])
    na_x=float(np.sin((theta_x.max()-theta_x.min())/2));na_y=float(np.sin((theta_y.max()-theta_y.min())/2))
    diffraction=dict(wavelengthNm=587.6,centralImageNA=[na_x,na_y],
        approximateImageFNumber=[1/(2*na_x),1/(2*na_y)],
        idealCircularPupilAiryFirstZeroDiameterUm=[2.44*.5876/(2*na_x),2.44*.5876/(2*na_y)],
        status='reference diffraction-limit estimate only; not added as a fabricated fixed blur kernel')
    np.savez_compressed(OUT/'field-responses.npz',fields=fields,points=b['points'],weights=b['weight'],valid=b['valid'],**{k:v for k,v in r.items()})
    return rows,diffraction


def checks():
    from sequential import refract
    # Analytic Snell: 30-degree air incidence into N-BK7.
    a=np.deg2rad(30);d=np.array([[np.sin(a),0,np.cos(a)]]);n=np.array([[0,0,-1.]])
    out,ok,w=refract(d,n,1.,1.5168)
    snell_error=float(abs(np.sin(a)-1.5168*abs(out[0,0])))
    assert ok[0] and snell_error<1e-12
    _,ok,_=refract(np.array([[np.sin(np.deg2rad(60)),0,np.cos(np.deg2rad(60))]]),n,1.5168,1.)
    assert not ok[0]
    rng=np.random.default_rng(32);o=np.c_[rng.uniform([-3.2,-1.8],[3.2,1.8],(5000,2)),np.full(5000,FILM)]
    target=np.c_[rng.uniform(-1,1,(5000,2)),np.full(5000,S[0].z)];d=target-o
    reference=trace(o,d,S);fast=trace_batch(o,d,pack(S));valid=reference['valid']
    assert np.array_equal(valid,fast[:,7].astype(bool))
    implementation_error=float(np.max(abs(reference['o'][valid]-fast[valid,:3])))
    assert implementation_error<1e-7
    reverse=trace(reference['o'][valid],-reference['d'][valid],S,reverse=True)
    tt=(FILM-reverse['o'][:,2])/reverse['d'][:,2];back=reverse['o']+tt[:,None]*reverse['d']
    reciprocal_error=float(np.max(abs(back-o[valid])))
    assert reciprocal_error<1e-7
    # Cylinder invariance: normals have no X component, so n*d_x is conserved.
    cyl=[s for s in S if s.kind=='cylinder'][0]
    from sequential import intersect
    oo=np.array([[.5,.2,cyl.z-1]])
    dd=normalize(np.array([[.2,.05,1.]]));hit,normal,okay=intersect(oo,dd,cyl)
    refr,okay,w=refract(dd,normal,cyl.n_before,cyl.n_after)
    cylinder_error=float(abs(cyl.n_before*dd[0,0]-cyl.n_after*refr[0,0]));assert cylinder_error<1e-10
    return dict(snellError=snell_error,totalInternalReflection=True,independentRayComparisons=5000,
        comparedValidRays=int(valid.sum()),numpyVsNumbaPositionErrorMm=implementation_error,
        roundTripPositionErrorMm=reciprocal_error,cylinderTangentialMomentumError=cylinder_error,
        note='Numerical and physical invariants; no commercial optical-code cross-validation')


def main():
    verified=checks();fields,diffraction=detailed_fields()
    render=np.load(OUT/'sensor-data.npz');hits=render['hits'];half=render['half_hits']
    books,_=books_and_textures();mask=np.zeros_like(hits,bool)
    for j in range(100):
        for i in range(152):
            x=-380+(i+.5)*5;y=(j+.5)*2.5
            mask[j,i]=any(b[0]<=x<=b[1] and y<=b[2] for b in books)
    fractions={}
    for key,counts in [('halfSamples',half),('fullSamples',hits)]:
        fractions[key]=dict(anyRayCoverage=float(((counts>0)&mask).sum()/mask.sum()),
            atLeast8Rays=float(((counts>=8)&mask).sum()/mask.sum()),
            reachedCells=int(((counts>0)&mask).sum()),targetCells=int(mask.sum()))
    np.savez_compressed(OUT/'coverage.npz',mask=mask,hits=hits,half_hits=half)
    payload=dict(status='FAILED: this two-cylinder trial does not yield clear full-width inventory images',
        prescription='data/optics/final-prescription.json',parameters=P,filmZMm=FILM,
        camera=dict(sensorMm=[6.4,3.6],nativePixels=[4000,2250],pixelPitchUm=1.6,
            sensor='unbound monochrome CMOS design target; not a claimed commercial product',
            nominalObjectiveEflMm=3.,designWavelengthNm=587.6,
            objective='PBRT Muller fisheye prescription uniformly scaled by 0.30; numeric glass indices from source',
            glassIndices='specified at one design wavelength; objective glass trade names and dispersion not supplied by PBRT'),
        rayModel=dict(refractions=15,stopPlanes=1,mirrorReflections=1,
            exact=['spherical intersections','circular cylindrical intersections','vector Snell refraction','Fresnel transmission','finite apertures and real stop','finite M1','book/cabinet occlusion'],
            noImposedFov=True,noImageSqueeze=True,
            excluded=['full diffraction wave propagation','broadband chromatic aberration','sensor shot/read noise','surface errors and tolerances','multi-reflection ghost/stray paths']),
        sampledAreaCoverage=fractions,
        coverageMethod='5 × 2.5 mm cells whose centres lie on the 27 example spines; a reached cell has at least one traced ray; sampling estimate, not a proof that all zero cells are impossible; blurred spill is counted only as geometric reach',
        qualityMethod='2048 rear-pupil samples per sensor location; reciprocity-based object-plane footprint D80 and geometric MTF at 0.5 cycle/mm; not an OCR success rate or full diffractive MTF',
        fields=fields,diffractionReference=diffraction,verification=verified,
        render=json.loads((OUT/'sensor-render.json').read_text()),
        sources=[{'title':'PBRT realistic camera method','url':'https://pbr-book.org/3ed-2018/Camera_Models/Realistic_Cameras'},
          {'title':'PBRT fisheye prescription','url':'https://github.com/mmp/pbrt-v4-scenes/blob/master/lenses/fisheye.10mm.dat'},
          {'title':'SCHOTT N-BK7 datasheet','url':'https://media.schott.com/api/public/content/41e799d0bf874807a0bb8e702fbb75b5?v=54856406'}])
    (OUT/'results.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(coverage=fractions,centralField=fields[17],diffractionReference=diffraction,verification=verified),indent=2,ensure_ascii=False))


if __name__=='__main__':main()
