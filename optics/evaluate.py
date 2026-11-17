"""Backward finite-pupil ray bundles and book-spine response footprints."""
from pathlib import Path
import json
import numpy as np
from sequential import (ROOT, Surface, design, trace, normalize, disk_samples,
                        to_shelf, BASIS, M, N, TANGENT)

OUT = ROOT/'references/ikea-billy-oxberg/sequential-trace'
SENSOR_W, SENSOR_H = 6.4, 3.6
NATIVE_W, NATIVE_H = 4000, 2250
PIXEL_MM = SENSOR_W/NATIVE_W


def load_design(path=None):
    data = json.loads(Path(path or ROOT/'data/optics/trial-prescription.json').read_text())
    return data['parameters'], [Surface(**s) for s in data['surfaces']], data['film_z']


def from_film(film_points, pupil, surfaces, film_z):
    origins = np.c_[film_points, np.full(len(film_points), film_z)]
    target = np.c_[pupil, np.full(len(pupil), surfaces[0].z)]
    dirs = normalize(target-origins)
    result = trace(origins, dirs, surfaces)
    result['weight'] *= abs(dirs[:, 2])**4
    return result


def to_spine_plane(result, finite_mirror=True):
    o = to_shelf(result['o'])
    d = result['d'] @ BASIS.T
    denom = d@N
    t = ((M-o)@N)/np.where(abs(denom) > 1e-10, denom, 1e-10)
    q = o+t[:, None]*d
    valid = result['valid'] & (t > 0)
    if finite_mirror:
        valid &= (abs(q[:, 0]) <= 290) & (abs((q-M)@TANGENT) <= 26)
    # The straight lens→mirror segment must remain in the free top corridor.
    valid &= np.all((q >= [-380, 0, 0]) & (q <= [380, 328, 260]), axis=1)
    # On both segments the convex empty cabinet bounds suffice. Check book
    # envelope before the mirror separately (all lenses clear the book tops).
    for y in [250.]:
        tb = (y-o[:, 1])/np.where(abs(d[:, 1]) > 1e-10, d[:, 1], 1e-10)
        pp = o+tb[:, None]*d
        valid &= ~((tb > 0) & (tb < t) & (pp[:, 2] >= 60) & (pp[:, 2] <= 260) & (abs(pp[:, 0]) <= 380))
    reflected = d-2*denom[:, None]*N
    tt = (60-q[:, 2])/np.where(abs(reflected[:, 2]) > 1e-10, reflected[:, 2], 1e-10)
    hit = q+tt[:, None]*reflected
    valid &= (tt > 0)
    return hit, valid, q, reflected


def bundles(film_points, surfaces, film_z, count=128, pupil_radius=1.25):
    """Uniform disk at the rear-vertex reference plane, includes rejected rays."""
    film_points = np.asarray(film_points).reshape(-1, 2)
    pupil = np.tile(disk_samples(count)*pupil_radius, (len(film_points), 1))
    film = np.repeat(film_points, count, axis=0)
    r = from_film(film, pupil, surfaces, film_z)
    points, valid, q, d = to_spine_plane(r)
    return dict(points=points.reshape(-1,count,3), valid=valid.reshape(-1,count),
                weight=(r['weight']*valid).reshape(-1,count), film=film_points,
                lens_valid=r['valid'].reshape(-1,count), mirrors=q.reshape(-1,count,3))


def summary(bundle):
    w = bundle['weight'];sw=np.sum(w,axis=1)
    points = bundle['points']
    centroid = np.sum(w[:,:,None]*points,axis=1)/np.maximum(sw[:,None],1e-30)
    distance = np.linalg.norm(points[:,:,:2]-centroid[:,None,:2],axis=2)
    order=np.argsort(distance,axis=1)
    cumulative=np.cumsum(np.take_along_axis(w,order,axis=1),axis=1)
    idx=np.argmax(cumulative >= sw[:,None]*.8,axis=1)
    d80=2*np.take_along_axis(np.take_along_axis(distance,order,axis=1),idx[:,None],axis=1)[:,0]
    d80[sw==0]=np.nan
    rms=np.sqrt(np.sum(w*distance**2,axis=1)/np.maximum(sw,1e-30))
    # Geometric modulation of an object-space 1 mm stroke / 1 mm gap test.
    mtf_y=abs(np.sum(w*np.exp(1j*np.pi*(points[:,:,1]-centroid[:,None,1])),axis=1))/np.maximum(sw,1e-30)
    mtf_x=abs(np.sum(w*np.exp(1j*np.pi*(points[:,:,0]-centroid[:,None,0])),axis=1))/np.maximum(sw,1e-30)
    return dict(centroid=centroid, d80=d80, rms=rms, mtf_y=mtf_y, mtf_x=mtf_x,
                throughput=sw/w.shape[1], valid_count=np.sum(bundle['valid'],axis=1))


if __name__=='__main__':
    p,s,film=load_design()
    xs=np.linspace(-3.2,3.2,41);ys=np.linspace(-1.8,1.8,31)
    grid=np.array([[x,y] for y in ys for x in xs])
    b=bundles(grid,s,film,64)
    r=summary(b)
    useful=(r['valid_count']>=3)&(abs(r['centroid'][:,0])<380)&(r['centroid'][:,1]>0)&(r['centroid'][:,1]<250)
    print('useful pixels',sum(useful),'/',len(grid),'lens pass rays',b['lens_valid'].sum(),'mirror pass rays',b['valid'].sum())
    for j in np.flatnonzero(useful)[::max(1,int(useful.sum())//15)]:
        print(grid[j],r['centroid'][j,:2],'D80 mm',r['d80'][j], 'MTF',r['mtf_y'][j])
    np.savez_compressed(OUT/'diagnostic.npz',**r,film=grid,useful=useful)
