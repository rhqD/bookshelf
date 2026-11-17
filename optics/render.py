"""Render the monochrome sensor by integrating exact sequential lens rays."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.stats import qmc
from numba import set_num_threads
from sequential import ROOT, trace, camera_surfaces
from evaluate import load_design, OUT
from fast import pack, render_rows
from layout import active_layout, packed


def books_and_textures():
    source=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
    books=np.array([[b['x0']+.35,b['x1']-.35,b['height']] for b in source])
    cache=OUT/'book-textures.npz'
    if cache.exists():return books,np.load(cache)['textures']
    titles=json.loads((ROOT/'data/example-book-titles.json').read_text())
    palette=[91,128,192,115,213,102,109,173,111,161,205,104]
    font_path='/System/Library/Fonts/STHeiti Medium.ttc'
    title_font=ImageFont.truetype(font_path,64)
    index_font=ImageFont.truetype(font_path,36)
    small_font=ImageFont.truetype(font_path,25)
    textures=[]
    rng=np.random.default_rng(813)
    for i,b in enumerate(source):
        ww=int((b['x1']-b['x0']-.7)*8);hh=int(b['height']*8)
        base=palette[i%len(palette)]
        im=Image.new('L',(ww,hh),base);draw=ImageDraw.Draw(im);ink=236 if base<170 else 28
        chars=titles[i];span=len(chars)*73
        top=hh*.39-span/2
        for k,ch in enumerate(chars):draw.text((ww/2,top+k*73),ch,font=title_font,anchor='mt',fill=ink)
        draw.text((ww/2,17*8),f'{i+1:02d}',font=index_font,anchor='mm',fill=ink)
        draw.line((ww*.25,hh-49*8,ww*.75,hh-49*8),fill=ink,width=2)
        for k,ch in enumerate('示例书'):draw.text((ww/2,hh-35*8+k*30),ch,font=small_font,anchor='mt',fill=ink)
        draw.line((3,0,3,hh),fill=min(255,base+12),width=3)
        draw.line((ww-3,0,ww-3,hh),fill=max(0,base-15),width=3)
        arr=np.array(im.resize((256,2048),Image.Resampling.LANCZOS),float)
        arr=np.clip(arr+rng.normal(0,.6,arr.shape),0,255).astype('uint8')
        textures.append(arr)
    textures=np.array(textures);np.savez_compressed(cache,textures=textures)
    return books,textures


def pupil_bounds(surfaces,film_z):
    # Bound the real camera exit pupil, not an imposed imaging aperture. The
    # cylindrical elements still clip/refract every final sample individually.
    camera=[s for s in surfaces if s.name.startswith('CAM') or s.name=='STOP']
    maximum=np.hypot(3.2,1.8);bounds=[]
    qq=np.linspace(-1.4,1.4,71)
    pupil=np.array([[x,y,camera[0].z] for y in qq for x in qq])
    for rr in np.linspace(0,maximum,97):
        origins=np.repeat([[rr,0.,film_z]],len(pupil),axis=0)
        r=trace(origins,pupil-origins,camera)
        selected=pupil[r['valid']]
        if len(selected):
            bounds.append([selected[:,0].min()-.065,selected[:,0].max()+.065,max(abs(selected[:,1]))+.065])
        else:bounds.append([-1.4,1.4,1.4])
    return np.array(bounds)


def display(linear,gain=None):
    if gain is None:gain=.65/max(float(np.percentile(linear,99.5)),1e-12)
    value=np.maximum(0,linear*gain)
    value=np.where(value<=.0031308,12.92*value,1.055*value**(1/2.4)-.055)
    return np.uint8(np.clip(value,0,1)*255+.5),gain


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--width',type=int,default=4000);ap.add_argument('--spp',type=int,default=64);ap.add_argument('--name');ap.add_argument('--control',action='store_true');ap.add_argument('--stop',type=float);ap.add_argument('--prescription');ap.add_argument('--gain-from');args=ap.parse_args()
    set_num_threads(8)
    active=ROOT/'data/optics/current-prescription.json'
    source=Path(args.prescription) if args.prescription else (ROOT/'data/optics/final-prescription.json' if args.control else active if active.exists() else ROOT/'data/optics/final-prescription.json')
    p,s,film=load_design(source)
    if args.stop is not None:
        p['stop']=args.stop
        for ss in s:
            if ss.name=='STOP':ss.diameter=args.stop
    if args.control:s=[ss for ss in s if ss.kind!='cylinder']
    if not args.name:args.name='sensor' if any(ss.kind=='cylinder' for ss in s) else 'current-no-cylinders'
    books,textures=books_and_textures();bounds=pupil_bounds(s,film)
    np.save(OUT/(args.name+'-pupil-bounds.npy'),bounds)
    samples=qmc.Sobol(2,scramble=True,seed=481).random_base2(int(np.ceil(np.log2(args.spp))))[:args.spp]
    width=args.width;height=width*9//16;image=np.zeros((height,width));hits=np.zeros((100,152),np.int64);half_hits=hits.copy();counts=np.zeros(3,np.int64);row_spine_hits=np.zeros(height,np.int64);start=time.time()
    surfaces=pack(s);layout=json.loads(source.read_text()).get('layout',active_layout());scene_layout=packed(layout)
    for y in range(0,height,48):
        im,hh,cc,hhalf,srows=render_rows(y,min(y+48,height),width,height,surfaces,film,bounds,samples,books,textures,scene_layout)
        image[y:y+len(im)]=im;row_spine_hits[y:y+len(im)]=srows;hits+=hh;half_hits+=hhalf;counts+=cc
        print(f'{args.name} rows {min(y+48,height)}/{height}; {time.time()-start:.1f}s; lens pass {counts[1]}/{counts[0]}',flush=True)
    shared_gain=None
    if args.gain_from:shared_gain=float(np.load(args.gain_from)['gain'])
    if args.control and (OUT/'sensor-data.npz').exists():
        shared_gain=float(np.load(OUT/'sensor-data.npz')['gain'])
    result,gain=display(image,shared_gain)
    Image.fromarray(result).save(OUT/(args.name+'-raw.png'))
    Image.fromarray(result[:,::-1]).save(OUT/(args.name+'-corrected.png'))
    thumb=Image.fromarray(result[:,::-1]);thumb.thumbnail((1920,1080));thumb.save(OUT/(args.name+'-preview.jpg'),quality=94)
    raw_thumb=Image.fromarray(result);raw_thumb.thumbnail((1920,1080));raw_thumb.save(OUT/(args.name+'-raw.jpg'),quality=94)
    np.savez_compressed(OUT/(args.name+'-data.npz'),linear=image.astype('float32'),hits=hits,half_hits=half_hits,rowSpineHits=row_spine_hits,counts=counts,gain=gain,bounds=bounds)
    (OUT/(args.name+'-render.json')).write_text(json.dumps(dict(layout=layout,prescription=str(source),width=width,height=height,samplesPerPixel=args.spp,rays=int(counts[0]),lensPass=int(counts[1]),spineHits=int(counts[2]),displayGain=gain,elapsedSeconds=time.time()-start,optics='exact sphere/cylinder intersections, vector Snell refraction, Fresnel, finite real stop, finite M1',scene='analytic cabinet and book boxes, synthetic monochrome printed textures, diffuse direct + ambient lighting',excluded=['diffraction wave propagation','broadband chromatic aberration','sensor shot/read noise','surface manufacturing errors','stray multi-reflection ghosts'],imageCorrection='horizontal digital mirror flip only; no image squeeze, perspective rectification, denoise or sharpen'),indent=2)+'\n')
    print('DONE',args.name,counts.tolist(),'seconds',time.time()-start,flush=True)


if __name__=='__main__':main()
