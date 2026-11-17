"""Reproduce the finite-conjugate axial seed; not a full-field lens optimizer."""
import json
import numpy as np
from scipy.optimize import least_squares
from sequential import ROOT, design, object_to_film, asdict

BASE=dict(front_r=60.,front_t=8.,front_height=32.,front_width=250.,
          rear_z=5.,rear_t=2.,rear_height=14.,rear_width=44.,stop=1.3)
OBJECTS=np.array([[0.,0.,385.1775]]*4+[[.1,0,385.1775],[0,.1,385.1775]])
PUPIL=np.array([[.1,0],[-.1,0],[0,.1],[0,-.1],[0,0],[0,0]])


def objective(v):
    p,s,film=design({**BASE,'front_z':v[0],'rear_r':v[1],'film_gap':v[2]})
    r=object_to_film(OBJECTS,PUPIL,s,film,apertures=False,continuation=False)
    xy=r['film'][:,:2]
    # Optimize zero differential defocus in X and Y and a central finite-
    # conjugate scale ratio. This target is NOT imposed on later ray rendering.
    return [xy[0,0]-xy[1,0],xy[2,1]-xy[3,1],(xy[5,1]/xy[4,0]-5.574715)*.02]


if __name__=='__main__':
    r=least_squares(objective,[64,11,6.9353],bounds=([20,8,5],[120,40,9]),
        diff_step=1e-4,xtol=1e-10,ftol=1e-10,gtol=1e-10,max_nfev=120)
    assert r.success and np.linalg.norm(r.fun)<1e-7
    p,s,film=design({**BASE,'front_z':r.x[0],'rear_r':r.x[1],'film_gap':r.x[2]})
    trial=dict(parameters=p,film_z=film,surfaces=[asdict(v) for v in s])
    (ROOT/'data/optics/trial-prescription.json').write_text(json.dumps(trial,indent=2)+'\n')
    p,s,film=design({**p,'stop':.8})
    final=dict(parameters=p,film_z=film,surfaces=[asdict(v) for v in s],
        wavelength_nm=587.6,sensor_mm=[6.4,3.6],sensor_pixels=[4000,2250],
        sensor_type='design target monochrome CMOS, no commercial part selected',
        optimization='finite-conjugate axial seed only; stopped down from 1.3 to 0.8 mm after finite-pupil comparison',
        status='trial prescription, not full-field corrected or manufacturing released')
    (ROOT/'data/optics/final-prescription.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps(dict(parameters=p,filmZ=film,residual=r.fun.tolist()),indent=2))
