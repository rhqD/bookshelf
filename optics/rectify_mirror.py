"""Rectify the current no-cylinder mirror image onto the book-spine plane.

Reads only the observed sensor image, numeric lens prescription and geometry.
The texture/title reference is not read, rendered or supplied to reconstruction.
"""
import hashlib
import json
import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.ndimage import map_coordinates
from PIL import Image
from sequential import (ROOT,normalize,reflect_points,to_local,to_shelf,
                        object_to_film,M,N,TANGENT)
from evaluate import load_design

OUT=ROOT/'references/ikea-billy-oxberg/mirror-rectification'
TRACE=ROOT/'references/ikea-billy-oxberg/sequential-trace'
OUT.mkdir(exist_ok=True)


def project(real,surfaces,film):
    virtual=to_local(reflect_points(real))
    result=object_to_film(virtual,np.zeros((len(real),2)),surfaces,film,continuation=True,record=True)
    # The front surface's direction towards the unfolded object determines M1.
    # Record only a small surface sequence, not scene textures.
    origin=to_shelf(result['paths'][1]);world_virtual=to_shelf(virtual)
    direction=normalize(world_virtual-origin)
    distance=((M-origin)@N)/(direction@N)
    q=origin+distance[:,None]*direction
    valid=result['valid']&(distance>0)&(abs(q[:,0])<=290)&(abs((q-M)@TANGENT)<=26)
    px=(result['film'][:,0]/6.4+.5)*4000-.5
    py=(result['film'][:,1]/3.6+.5)*2250-.5
    valid&=(px>=0)&(px<4000)&(py>=0)&(py<2250)
    return px,py,valid


def encode(linear,gain):
    v=np.maximum(0,linear*gain)
    v=np.where(v<=.0031308,12.92*v,1.055*v**(1/2.4)-.055)
    return np.uint8(np.clip(v,0,1)*255+.5)


def main():
    prescription=ROOT/'data/optics/current-prescription.json'
    p,surfaces,film=load_design(prescription)
    assert not any(s.kind=='cylinder' for s in surfaces)
    measured=np.load(TRACE/'current-no-cylinders-data.npz')
    observed=measured['linear'];gain=float(measured['gain'])
    gx=np.linspace(-380,380,161);gy=np.linspace(0,250,81)
    points=np.array([[x,y,60.] for y in gy for x in gx])
    print('Tracing calibration points',len(points),flush=True)
    px,py,valid=project(points,surfaces,film)
    assert valid.all(),f'Invalid central calibration rays: {int((~valid).sum())}'
    mx=RectBivariateSpline(gy,gx,px.reshape(len(gy),len(gx)),kx=3,ky=3)
    my=RectBivariateSpline(gy,gx,py.reshape(len(gy),len(gx)),kx=3,ky=3)
    rng=np.random.default_rng(3417)
    test=np.c_[rng.uniform(-379,379,120),rng.uniform(1,249,120),np.full(120,60.)]
    tx,ty,tv=project(test,surfaces,film)
    error=np.hypot(mx.ev(test[:,1],test[:,0])-tx,my.ev(test[:,1],test[:,0])-ty)
    assert tv.all() and error.max()<.15,'Calibration interpolation not accurate enough.'
    ppm=4;width=760*ppm;height=250*ppm
    xx=-380+(np.arange(width)+.5)/ppm;yy=250-(np.arange(height)+.5)/ppm
    wx,wy=np.meshgrid(xx,yy)
    mapx=mx.ev(wy.ravel(),wx.ravel()).reshape(height,width)
    mapy=my.ev(wy.ravel(),wx.ravel()).reshape(height,width)
    flat=map_coordinates(observed,[mapy,mapx],order=1,mode='constant',cval=0,prefilter=False)
    source=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
    mask=np.zeros((height,width),bool)
    for b in source:
        mask|=(wx>=b['x0']+.35)&(wx<=b['x1']-.35)&(wy<=b['height'])
    image=np.repeat(encode(flat,gain)[:,:,None],3,axis=2)
    image[~mask]=[239,241,232]
    Image.fromarray(image).save(OUT/'rectified.png')
    preview=Image.fromarray(image);preview.thumbnail((1920,1080));preview.save(OUT/'rectified-preview.jpg',quality=96)
    # A genuine crop of the same source image; only a horizontal mirror flip.
    roi=(max(0,int(px.min())-25),max(0,int(py.min())-25),min(4000,int(px.max())+26),min(2250,int(py.max())+26))
    raw=Image.fromarray(encode(observed,gain)).convert('RGB')
    crop=raw.crop(roi).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    crop.save(OUT/'mirror-crop.png')
    crop.thumbnail((1920,1080));crop.save(OUT/'mirror-crop-preview.jpg',quality=96)
    # A close view at the centre, from fixed physical coordinates, not titles.
    close_bounds=(-105.,105.,80.,195.)
    l=int((close_bounds[0]+380)*ppm);r=int((close_bounds[1]+380)*ppm)
    t=int((250-close_bounds[3])*ppm);b=int((250-close_bounds[2])*ppm)
    Image.fromarray(image[t:b,l:r]).save(OUT/'rectified-centre.png')
    settings=dict(variant='current camera + M1, no external cylinders',method='book-spine-plane inverse ray calibration + bicubic coordinate-map interpolation + bilinear image resampling',
        planeShelfZMm=60,planeWidthMm=760,planeHeightMm=250,
        sourcePixels=[4000,2250],outputPixels=[width,height],outputPixelMm=1/ppm,
        calibrationGrid=[len(gx),len(gy)],heldOutChecks=120,
        heldOutRmsErrorNativePixels=float(np.sqrt(np.mean(error**2))),heldOutMaxErrorNativePixels=float(error.max()),
        originalSourceCropPixels=list(roi),display='same display gain and transfer curve as the original; no sharpening, generative fill or reference-texture input',
        inputs=['current-no-cylinders-data.npz linear observation','current-prescription.json numerical surfaces','M1 plane','book geometry only'],
        interpolation='bilinear intensity interpolation; magnifies existing samples only',
        masked='book tops, gaps and areas outside the defined spine plane',
        limitations=['fixed aligned spine plane Z=60 mm; changed depth/pose requires recalibration','single chief ray represents each object point; finite-pupil blur is retained in the observed image','stretching pixels does not increase optical resolution','synthetic monochrome input, not a real photograph'],
        sourceHashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [prescription,TRACE/'current-no-cylinders-data.npz']})
    (OUT/'rectification-settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
    np.savez_compressed(OUT/'coordinate-map.npz',source_x=mapx.astype('float32'),source_y=mapy.astype('float32'),mask=mask)
    print(json.dumps(settings,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
