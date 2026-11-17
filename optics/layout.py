"""A single explicit shelf-frame layout, shared by search, tracing and rendering."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASELINE=dict(camera=[0.,280.,230.],pitch_deg=4.085616779974877,
    mirror=[0.,299.1461871009169,23.531496332069093],tilt_deg=40.42254843239384,
    mirror_size=[580.,52.],sensor_mm=[6.4,3.6],sensor_pixels=[4000,2250])

def geometry(layout):
    c=np.array(layout['camera'],float);m=np.array(layout['mirror'],float)
    a=np.radians(layout['pitch_deg']);t=np.radians(layout['tilt_deg'])
    f=np.array([0.,np.sin(a),-np.cos(a)]);u=np.array([0.,np.cos(a),np.sin(a)])
    b=np.stack(([1.,0.,0.],u,f),axis=1)
    n=np.array([0.,np.sin(t),-np.cos(t)]);tangent=np.array([0.,np.cos(t),np.sin(t)])
    return c,b,m,n,tangent

def active_layout():
    p=ROOT/'data/optics/current-layout.json'
    return json.loads(p.read_text()) if p.exists() else BASELINE.copy()

def packed(layout):
    c,b,m,n,t=geometry(layout)
    return np.r_[c,b[:,1],b[:,2],m,n,t,np.array(layout['mirror_size'])/2]
