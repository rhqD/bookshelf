"""Image-only mirror rectification. Input: the cropped reflected image PNG.

Uses mirror-frame curves for a plumb-line radial fit, then book-spine edges
for their vertical vanishing point. No scene, camera prescription, book list,
depth, reference texture, or title is read by this program.
"""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter,gaussian_filter1d,map_coordinates
from scipy.signal import find_peaks
from scipy.optimize import least_squares
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'references/ikea-billy-oxberg/mirror-rectification/mirror-crop.png'
OUT=ROOT/'references/ikea-billy-oxberg/image-based-rectification'

def frame_curve(gray,upper):
    h,w=gray.shape;sm=gaussian_filter1d(gray,2,axis=1)
    ridge=gaussian_filter1d(sm,5,axis=0)-gaussian_filter1d(sm,.8,axis=0)
    xs=np.arange(24,w-24,8);lo,hi=(2,int(h*.35)) if upper else (int(h*.76),h-2)
    ys=np.argmax(ridge[lo:hi,xs],axis=0)+lo
    weights=ridge[ys,xs];ok=(weights>35)&(ys>lo+1)&(ys<hi-1)
    xs,ys=xs[ok],ys[ok];t=(xs-(w-1)/2)/(w/2)
    A=np.c_[np.ones(len(t)),t*t,t**4]
    fit=least_squares(lambda p:A@p-ys,np.linalg.lstsq(A,ys,rcond=None)[0],loss='soft_l1',f_scale=1.2)
    ok=abs(A@fit.x-ys)<2
    return np.c_[xs[ok],ys[ok]].astype(float),fit.x

def undistort(points,p,cx,scale):
    cy,k1,k2,k3=p
    delta=points-np.array([cx,cy]);r2=np.sum(delta*delta,axis=-1)/(scale*scale)
    f=1+k1*r2+k2*r2*r2+k3*r2*r2*r2
    return delta*f[...,None]+np.array([cx,cy])

def fit_radial(top,bottom,w,h):
    cx=(w-1)/2;scale=w/2
    def residual(p):
        a=undistort(top,p,cx,scale)[:,1];b=undistort(bottom,p,cx,scale)[:,1]
        return np.r_[a-np.median(a),b-np.median(b)]
    r=least_squares(residual,[h*.63,.3,.1,.05],bounds=([-h,-1,-1,-1],[h*2,2,2,2]),loss='soft_l1',f_scale=.5,max_nfev=500)
    assert np.sqrt(np.mean(residual(r.x)**2))<2,'Mirror curve fit is not adequate.'
    return r.x,float(np.sqrt(np.mean(residual(r.x)**2)))

def tracks(gray):
    h,w=gray.shape
    smooth=gaussian_filter(gray,(.7,1.0))
    gx=gaussian_filter1d(np.gradient(smooth,axis=1),.7,axis=0)
    y0=int(h*.73)
    peaks,_=find_peaks(abs(gx[y0]),height=3.0,distance=10,prominence=2.3)
    found=[]
    for x0 in peaks:
        sign=np.sign(gx[y0,x0]);pieces=[]
        for direction,limit in [(1,int(h*.86)),(-1,int(h*.38))]:
            x=float(x0);slope=0.;pts=[];previous_y=y0
            for y in range(y0,limit,2*direction):
                prediction=x+slope*(y-previous_y)
                radius=10 if abs(y-y0)<12 else 5
                xx=np.arange(max(1,int(prediction)-radius),min(w-1,int(prediction)+radius+1))
                if len(xx)<3:break
                values=sign*gx[y,xx]-.10*abs(xx-prediction)
                xnew=float(xx[np.argmax(values)])
                confidence=float(sign*gx[y,int(xnew)])
                if y!=previous_y:slope=.7*slope+.3*(xnew-x)/(y-previous_y)
                x=xnew;previous_y=y
                if confidence>2.2:pts.append([x,float(y)])
            pieces+=pts
        a=np.unique(np.array(pieces),axis=0)
        if len(a)>55 and np.ptp(a[:,1])>h*.32:found.append(a)
    return found

def line(points):
    centre=np.mean(points,axis=0)
    _,_,vt=np.linalg.svd(points-centre,full_matrices=False)
    normal=vt[-1];c=-normal@centre
    return np.r_[normal,c],float(np.sqrt(np.mean(((points-centre)@normal)**2)))

def fit_vanishing(raw_tracks,p,w,h):
    cx=(w-1)/2;lines=[];kept=[];rms=[]
    for a in raw_tracks:
        l,e=line(undistort(a,p,cx,w/2))
        if e<1.5:lines.append(l);kept.append(a);rms.append(e)
    lines=np.array(lines)
    best=None;best_score=-1
    for i in range(len(lines)):
        for j in range(i):
            cross=np.cross(lines[i],lines[j])
            if abs(cross[2])<1e-8:continue
            vp=cross[:2]/cross[2]
            if not w*.25<vp[0]<w*.75 or not h*1.1<vp[1]<h*8:continue
            err=abs(lines[:,:2]@vp+lines[:,2]);inlier=err<5
            score=np.sum(np.maximum(0,1-err/5))
            if score>best_score:best=(vp,inlier);best_score=score
    assert best is not None,'No book-spine vanishing-point consensus.'
    vp,inlier=best
    result=least_squares(lambda v:lines[inlier,:2]@v+lines[inlier,2],vp,loss='soft_l1',f_scale=1)
    vp=result.x;errors=abs(lines[:,:2]@vp+lines[:,2]);inlier=errors<5
    assert inlier.sum()>=6,'Too few independently observed spine edges.'
    return vp,[a for a,k in zip(kept,inlier) if k],errors[inlier]

def rectify_coords(q,vp):
    den=vp[1]-q[...,1]
    return np.stack(((q[...,0]-vp[0])/den,1/den),axis=-1)

def invert_radial(q,p,cx,scale):
    cy,k1,k2,k3=p;delta=q-np.array([cx,cy]);ru=np.linalg.norm(delta,axis=-1)/scale
    r=ru.copy()
    for _ in range(25):
        r2=r*r
        f=r*(1+k1*r2+k2*r2*r2+k3*r2*r2*r2)-ru
        derivative=1+3*k1*r2+5*k2*r2*r2+7*k3*r2*r2*r2
        r=np.clip(r-f/np.maximum(derivative,.01),0,3)
    return delta*(r/np.maximum(ru,1e-30))[...,None]+np.array([cx,cy])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=DEFAULT);args=ap.parse_args()
    OUT.mkdir(exist_ok=True)
    image=np.array(Image.open(args.input).convert('RGB'));gray=image.mean(axis=2);h,w=gray.shape
    top,tp=frame_curve(gray,True);bottom,bp=frame_curve(gray,False)
    p,radial_rms=fit_radial(top,bottom,w,h)
    raw_tracks=tracks(gray);vp,edges,errors=fit_vanishing(raw_tracks,p,w,h)
    print('RADIAL',p,'frame fit rms',radial_rms,'VP',vp,'edges',len(edges),flush=True)
    overlay=Image.fromarray(image.copy());draw=ImageDraw.Draw(overlay)
    for a in [top,bottom]:
        for x,y in a[::2]:draw.ellipse((x-2,y-2,x+2,y+2),fill=(230,148,40))
    for a in edges:draw.line([tuple(v) for v in a[np.argsort(a[:,1])]],fill=(45,205,190),width=3)
    overlay.save(OUT/'detected-features.png')
    # Coordinate chart is defined by observed image edges, not real dimensions.
    edge_x=np.array([np.median(rectify_coords(undistort(a,p,(w-1)/2,w/2),vp)[:,0]) for a in edges])
    xmin,xmax=edge_x.min(),edge_x.max()
    # Mirror boundary gives a conservative observed-content crop. Do not mask
    # book silhouettes using scene data; retain observed tops/floor in the image.
    ys=np.array([np.median(undistort(top,p,(w-1)/2,w/2)[:,1]),np.median(undistort(bottom,p,(w-1)/2,w/2)[:,1])])
    ylo,yhi=1/(vp[1]-ys[0]),1/(vp[1]-ys[1])
    print('BOUNDS',xmin,xmax,ylo,yhi,flush=True)
    width=3040;height=1000
    edge_errors=[]
    for a in edges:
        u=rectify_coords(undistort(a,p,(w-1)/2,w/2),vp)[:,0]
        edge_errors.extend((u-np.median(u))*width/(xmax-xmin))
    xx=xmin+(np.arange(width)+.5)/width*(xmax-xmin)
    yy=ylo+(np.arange(height)+.5)/height*(yhi-ylo)
    rx,ry=np.meshgrid(xx,yy)
    qy=vp[1]-1/ry;qx=vp[0]+rx/ry
    source=invert_radial(np.stack((qx,qy),axis=-1),p,(w-1)/2,w/2)
    coords=[source[:,:,1],source[:,:,0]]
    valid=(source[:,:,0]>=0)&(source[:,:,0]<=w-1)&(source[:,:,1]>=0)&(source[:,:,1]<=h-1)
    t=(source[:,:,0]-(w-1)/2)/(w/2)
    upper=tp[0]+tp[1]*t*t+tp[2]*t**4;lower=bp[0]+bp[1]*t*t+bp[2]*t**4
    valid&=(source[:,:,1]>upper+3)&(source[:,:,1]<lower-3)
    corrected=np.stack([map_coordinates(image[:,:,c].astype(float),coords,order=1,mode='constant',cval=0,prefilter=False) for c in range(3)],axis=-1)
    corrected=np.uint8(np.clip(corrected,0,255)+.5);corrected[~valid]=[239,241,232]
    # Export source coordinates for a small reproducible selection of pixels.
    checks=[]
    for y in [250,500,750]:
        for x in [200,700,1200,1700,2200,2700]:
            if valid[y,x]:checks.append(dict(outputXY=[x,y],inputXY=source[y,x].tolist(),outputRGB=corrected[y,x].tolist()))
    (OUT/'pixel-sources.json').write_text(json.dumps(checks,indent=2)+'\n')
    rgba=np.dstack((corrected,np.uint8(valid)*255))
    Image.fromarray(rgba).save(OUT/'rectified.png')
    preview=Image.fromarray(corrected);preview.thumbnail((1920,1080));preview.save(OUT/'rectified-preview.jpg',quality=96)
    Image.fromarray(corrected[180:700,1100:1940]).save(OUT/'rectified-centre.png')
    sample=source[::25,::25];roundtrip=undistort(sample,p,(w-1)/2,w/2)
    expected=np.stack((qx,qy),axis=-1)[::25,::25]
    settings=dict(input=str(args.input.relative_to(ROOT)),sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        inputPixels=[w,h],outputPixels=[width,height],source='cropped reflected PNG pixels only',
        algorithm='frame plumb-line radial calibration; observed spine-edge vanishing point; projective rectification; bilinear source-pixel remapping',
        imageFeatures=dict(topFramePoints=len(top),bottomFramePoints=len(bottom),rawEdgeTracks=len(raw_tracks),acceptedSpineTracks=len(edges)),
        radial=dict(centreX=(w-1)/2,centreY=float(p[0]),coefficients=p[1:].tolist(),frameStraightnessRmsPx=radial_rms),
        vanishingPoint=vp.tolist(),vanishingPointLineResidualMedianPx=float(np.median(errors)),
        rectifiedEdgeRmsOutputPx=float(np.sqrt(np.mean(np.array(edge_errors)**2))),
        sourceRemapRoundtripMaxPx=float(np.linalg.norm(roundtrip-expected,axis=-1).max()),
        rectifiedBounds=[float(xmin),float(xmax),float(ylo),float(yhi)],
        assumptions=['horizontal mirror long edges are straight and parallel in the undistorted image','spine side edges are parallel in the book-spine plane','symmetric radial lens distortion','output vertical scale is a display choice; true physical aspect cannot be determined from one cropped image alone'],
        appearance='all visible image pixels are resampled from the PNG; outside-mirror pixels are transparent (neutral background in JPEG previews); observed book tops, gaps and floor are retained',
        rejectedInputs=['camera/lens prescription','3D book positions, heights and widths','linear sensor npz','reference book textures','known book titles'])
    (OUT/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(settings,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
