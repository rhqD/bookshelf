"""Exact geometric sequential ray tracing, mm, optical Z from sensor to scene.

Sphere / circular-cylinder / plane intersections and vector Snell refraction.
No thin-lens power or imposed field-of-view / image squeeze is used in tracing.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
from layout import active_layout, geometry

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-8


@dataclass
class Surface:
    name: str
    z: float
    radius: float
    n_before: float
    n_after: float
    kind: str = 'sphere'
    diameter: float = 0
    width: float = 0
    height: float = 0


def normalize(d):
    return d / np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-30)


def intersect(o, d, s):
    """Return the near vertex-hemisphere intersection, not the other sphere cap."""
    if s.kind == 'plane' or s.radius == 0:
        t = (s.z - o[:, 2]) / np.where(abs(d[:, 2]) > EPS, d[:, 2], EPS)
        p = o + t[:, None] * d
        n = np.broadcast_to([0., 0., 1.], p.shape).copy()
        return p, n, (t > -EPS) & (abs(d[:, 2]) > EPS)
    c = np.array([0., 0., s.z+s.radius])
    v = o-c
    axes = [1, 2] if s.kind == 'cylinder' else [0, 1, 2]
    a = np.sum(d[:, axes]**2, axis=1)
    b = 2*np.sum(v[:, axes]*d[:, axes], axis=1)
    cc = np.sum(v[:, axes]**2, axis=1)-s.radius**2
    discriminant = b*b-4*a*cc
    root = np.sqrt(np.maximum(discriminant, 0))
    ts = np.stack([(-b-root)/(2*a+1e-30), (-b+root)/(2*a+1e-30)], axis=1)
    zs = o[:, 2, None] + ts*d[:, 2, None]
    branch = (zs-c[2])*s.radius <= EPS
    ts = np.where((ts > -EPS) & branch, ts, np.inf)
    t = np.min(ts, axis=1)
    ok = (discriminant >= 0) & np.isfinite(t)
    p = o + np.where(ok, t, 0)[:, None]*d
    n = p-c
    if s.kind == 'cylinder':
        n[:, 0] = 0
    return p, normalize(n), ok


def refract(d, n, n1, n2):
    n = np.where((np.sum(d*n, axis=1) > 0)[:, None], -n, n)
    ci = np.clip(-np.sum(d*n, axis=1), 0, 1)
    eta = n1/n2
    st2 = eta*eta*(1-ci*ci)
    ct = np.sqrt(np.maximum(0, 1-st2))
    result = eta*d + (eta*ci-ct)[:, None]*n
    rs = ((n1*ci-n2*ct)/(n1*ci+n2*ct+1e-30))**2
    rp = ((n1*ct-n2*ci)/(n1*ct+n2*ci+1e-30))**2
    return normalize(result), st2 <= 1, 1-(rs+rp)/2


def trace(o, d, surfaces, reverse=False, apertures=True, stop_at=None, record=False):
    o = np.asarray(o, float).reshape(-1, 3).copy()
    d = normalize(np.asarray(d, float).reshape(-1, 3).copy())
    valid = np.ones(len(o), bool)
    throughput = np.ones(len(o))
    reason = np.full(len(o), '', dtype='U40')
    paths = [o.copy()] if record else None
    for s in (list(reversed(surfaces)) if reverse else surfaces):
        hit, n, ok = intersect(o, d, s)
        if apertures:
            if s.diameter:
                ok &= np.sum(hit[:, :2]**2, axis=1) <= (s.diameter/2)**2
            else:
                ok &= (abs(hit[:, 0]) <= s.width/2) & (abs(hit[:, 1]) <= s.height/2)
        failed = valid & ~ok
        reason[failed] = s.name + ': aperture/intersection'
        valid &= ok
        o = hit
        if record:
            paths.append(np.where(valid[:, None], o, np.nan))
        if s.name == stop_at:
            break
        if s.n_before != s.n_after:
            n1, n2 = (s.n_after, s.n_before) if reverse else (s.n_before, s.n_after)
            d, ok, power = refract(d, n, n1, n2)
            reason[valid & ~ok] = s.name + ': TIR'
            valid &= ok
            throughput *= power
    return dict(o=o, d=d, valid=valid, weight=throughput, reason=reason, paths=paths)


def camera_surfaces(scale=.30, stop_diameter=1.3):
    data = np.loadtxt(ROOT/'data/optics/pbrt-fisheye-10mm.dat')
    vertex = -np.r_[0, np.cumsum(data[:-1, 1])]*scale
    surfaces = []
    for i in range(len(data)-1, -1, -1):
        radius, sep, eta, aperture = data[i]
        before = eta if eta else 1
        after = data[i-1, 2] if i else 1
        if not after:
            after = 1
        surfaces.append(Surface('STOP' if radius == 0 else f'CAM{i+1:02}',
            float(vertex[i]), float(-radius*scale), float(before), float(after),
            'plane' if radius == 0 else 'sphere',
            min(stop_diameter, float(aperture*scale)) if radius == 0 else float(aperture*scale)))
    return surfaces


def design(params=None):
    # Camera front vertex is the old C reference. Actual entrance pupil is traced.
    p = dict(scale=.30, stop=1.30, rear_z=8.0, rear_r=8.0, rear_t=1.3,
             front_z=43.0, front_r=42.0, front_t=4.0,
             rear_width=44., rear_height=10., front_width=180., front_height=20.,
             film_gap=3.1)
    if params:
        p.update(params)
    surfaces = camera_surfaces(p['scale'], p['stop'])
    n = 1.51680  # SCHOTT N-BK7, d line 587.6 nm.
    surfaces.extend([
        Surface('L1 rear concave', p['rear_z'], -p['rear_r'], 1, n, 'cylinder', width=p['rear_width'], height=p['rear_height']),
        Surface('L1 front concave', p['rear_z']+p['rear_t'], p['rear_r'], n, 1, 'cylinder', width=p['rear_width'], height=p['rear_height']),
        Surface('L2 rear convex', p['front_z'], p['front_r'], 1, n, 'cylinder', width=p['front_width'], height=p['front_height']),
        Surface('L2 front convex', p['front_z']+p['front_t'], -p['front_r'], n, 1, 'cylinder', width=p['front_width'], height=p['front_height']),
    ])
    film_z = surfaces[0].z-p['film_gap']
    return p, surfaces, film_z


LAYOUT=active_layout()
C,BASIS,M,N,TANGENT=geometry(LAYOUT)
X,U,F=BASIS.T


def to_local(p):
    return (np.asarray(p)-C) @ BASIS


def to_shelf(p):
    return np.asarray(p) @ BASIS.T+C


def reflect_points(p):
    p = np.asarray(p)
    return p-2*np.sum((p-M)*N, axis=-1, keepdims=True)*N


def object_points(xs=(-370, -185, 0, 185, 370), ys=(10, 125, 240)):
    real = np.array([[x, y, 60.] for y in ys for x in xs])
    return real, to_local(reflect_points(real))


def aim_at_stop(objects, pupil, surfaces, max_iterations=18, continuation=True, initial_aim=None):
    """Newton-shoot rays through the actual stop; all pre-stop surfaces refract."""
    objects = np.asarray(objects).reshape(-1, 3)
    pupil = np.asarray(pupil).reshape(-1, 2)
    front_z = surfaces[-1].z+.1
    # First-order entrance-pupil guess from the actual pre-stop stack, only for
    # the Newton initial value. The converged rays still use exact surfaces.
    h0 = 1e-4
    origins = np.array([[h0,0,front_z],[0,h0,front_z],[0,0,front_z],[0,0,front_z]])
    dirs = np.array([[0,0,-1],[0,0,-1],[h0,0,-1],[0,h0,-1]])
    para = trace(origins, dirs, surfaces, reverse=True, apertures=False, stop_at='STOP')['o']
    aa = np.array([para[0,0],para[1,1]])/h0
    bb = np.array([para[2,0],para[3,1]])/h0
    distance = objects[:, 2, None]-front_z
    aim = (pupil + bb*objects[:, :2]/distance)/(aa+bb/distance)
    if initial_aim is not None:
        aim=np.asarray(initial_aim,float).reshape(-1,2).copy()

    def run(a, obj=objects):
        target = np.c_[a, np.full(len(a), front_z)]
        return trace(obj, target-obj, surfaces, reverse=True, apertures=False, stop_at='STOP')

    def solve(aim, obj, iterations):
        for _ in range(iterations):
            result = run(aim, obj)
            residual = result['o'][:, :2]-pupil
            if np.all(result['valid'] & (np.linalg.norm(residual, axis=1) < 1e-7)):
                break
            h = 1e-4
            rx = run(aim+[h, 0], obj)
            ry = run(aim+[0, h], obj)
            jx = (rx['o'][:, :2]-result['o'][:, :2])/h
            jy = (ry['o'][:, :2]-result['o'][:, :2])/h
            det = jx[:, 0]*jy[:, 1]-jy[:, 0]*jx[:, 1]
            det = np.where(abs(det) > 1e-12, det, 1e-12)
            dx = (jy[:, 1]*residual[:, 0]-jy[:, 0]*residual[:, 1])/det
            dy = (-jx[:, 1]*residual[:, 0]+jx[:, 0]*residual[:, 1])/det
            step = np.c_[dx, dy]
            step *= np.minimum(1, 3/np.maximum(np.linalg.norm(step, axis=1, keepdims=True), 1e-10))
            old_error = np.where(result['valid'], np.linalg.norm(residual, axis=1), np.inf)
            changed = np.zeros(len(aim), bool)
            for factor in [1, .5, .25, .125, .0625]:
                candidate = aim-step*factor
                rr = run(candidate, obj)
                error = np.where(rr['valid'], np.linalg.norm(rr['o'][:, :2]-pupil, axis=1), np.inf)
                use = ~changed & (error < old_error)
                aim[use] = candidate[use]
                changed |= use
            if not np.any(changed):
                break
        return aim

    aim = solve(aim, objects, max_iterations)
    result = run(aim)
    failed = ~result['valid'] | (np.linalg.norm(result['o'][:, :2]-pupil, axis=1) >= 1e-5)
    if continuation and np.any(failed):
        # Follow chief rays smoothly from the axis rather than treating a failed
        # large-angle Newton initial guess as optical vignetting.
        axis = objects.copy()
        axis[:, :2] = 0
        guess = pupil/(aa+bb/distance)
        guess = solve(guess, axis, 12)
        for fraction in np.linspace(.05, 1., 20):
            intermediate = objects.copy()
            intermediate[:, :2] *= fraction
            guess = solve(guess, intermediate, 10)
        aim[failed] = guess[failed]
    result = run(aim)
    converged = result['valid'] & (np.linalg.norm(result['o'][:, :2]-pupil, axis=1) < 1e-5)
    target = np.c_[aim, np.full(len(aim), front_z)]
    return normalize(target-objects), converged


def object_to_film(objects, pupil, surfaces, film_z, apertures=True, record=False, continuation=True,initial_aim=None):
    directions, converged = aim_at_stop(objects, pupil, surfaces, continuation=continuation,initial_aim=initial_aim)
    result = trace(objects, directions, surfaces, reverse=True, apertures=apertures, record=record)
    t = (film_z-result['o'][:, 2])/result['d'][:, 2]
    result['film'] = result['o'] + t[:, None]*result['d']
    result['valid'] &= converged & (t > 0)
    result['converged'] = converged
    objects=np.asarray(objects).reshape(-1,3)
    tt=(surfaces[-1].z+.1-objects[:,2])/directions[:,2]
    result['shooting_aim']=(objects+tt[:,None]*directions)[:,:2]
    return result


def disk_samples(n=128):
    i = np.arange(n)
    r = np.sqrt((i+.5)/n)
    theta = i * (np.pi*(3-np.sqrt(5)))
    return np.c_[r*np.cos(theta), r*np.sin(theta)]


if __name__ == '__main__':
    p, surfaces, film_z = design()
    real, objects = object_points()
    result = object_to_film(objects, np.zeros((len(objects), 2)), surfaces, film_z)
    print('film_z', film_z)
    print(np.c_[real[:, :2], result['film'][:, :2], result['valid']])
    print(result['reason'])
