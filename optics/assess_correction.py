"""Assessment-only clean reference and blind OCR. Never imported by correction.

Book titles and clean textures are read here only AFTER the observation-only
reconstruction has been written. OCR receives images, no target vocabulary.
"""
import csv
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import map_coordinates
from correction import OUT, TRACE, ROOT, OW, OH, PPM, SW, SH, CACHE_TAG, geometry, display_object

TITLES=['书架设计','光学入门','空间与秩序','建筑的细节','阅读与生活','图像的语言','城市观察','时间简史','设计中的设计','认识材料','工程笔记','视觉与感知','数学之美','看见世界','科学的故事','摄影与光线','信息设计','自然的形状','机器视觉','造物手记','智能系统','人间草木','色彩研究','图书管理','纸上的风景','计算之道','未来的书房']


def clean_reference(books,labels):
    # Evaluation only. This texture file is NEVER read by the reconstruction.
    textures=np.load(TRACE/'book-textures.npz')['textures']
    xx=-380+(np.arange(OW)+.5)/PPM;yy=250-(np.arange(OH)+.5)/PPM
    x,y=np.meshgrid(xx,yy);reference=np.zeros((OH,OW),np.float32)
    for i,b in enumerate(books):
        valid=labels==i
        tx=np.clip(((x[valid]-b[0])/(b[1]-b[0])*256).astype(int),0,255)
        ty=np.clip(((1-y[valid]/b[2])*2048).astype(int),0,2047)
        albedo=(textures[i,ty,tx]/255.)**2.2
        lx=-250-x[valid];ly=420-y[valid];lz=-560.
        light=.25+.75*(-lz)/np.sqrt(lx*lx+ly*ly+lz*lz)
        reference[valid]=albedo*light
    return reference


def title_bounds(book,margin_x=.18):
    # A fixed central lane, 30%–84% of spine height, identical for every stage.
    left=int((book[0]+380+(book[1]-book[0])*margin_x)*PPM)
    right=int((book[1]+380-(book[1]-book[0])*margin_x)*PPM)
    top=int((250-book[2]*.84)*PPM);bottom=int((250-book[2]*.30)*PPM)
    return max(0,left),max(0,top),min(OW,right),min(OH,bottom)


def srgb(x):
    x=np.maximum(x,0)
    return np.uint8(np.clip(np.where(x<=.0031308,12.92*x,1.055*x**(1/2.4)-.055),0,1)*255+.5)


def save_ocr_crop(array,support,bounds,path):
    l,t,r,b=bounds;crop=srgb(array[t:b,l:r]).copy();mask=support[t:b,l:r]
    if np.any(mask):fill=int(np.median(crop[mask]))
    else:fill=220
    crop[~mask]=fill # Missing observations are blank, never fabricated letters.
    im=Image.fromarray(crop)
    im=im.resize((max(96,im.width*4),im.height*4),Image.Resampling.LANCZOS)
    im=ImageOps.expand(im,border=20,fill=fill)
    im.save(path)


def ocr(path):
    cmd=['tesseract',str(path),'stdout','--tessdata-dir',str(ROOT/'data/ocr'),
         '-l','chi_sim_vert','--oem','1','--psm','5',
         '-c','load_system_dawg=0','-c','load_freq_dawg=0']
    r=subprocess.run(cmd,text=True,capture_output=True,timeout=30)
    if r.returncode:raise RuntimeError(r.stderr)
    text=''.join(re.findall(r'[\u3400-\u9fffA-Za-z0-9]',r.stdout))
    return text


def edit_distance(a,b):
    prev=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        row=[i]
        for j,cb in enumerate(b,1):row.append(min(row[-1]+1,prev[j]+1,prev[j-1]+(ca!=cb)))
        prev=row
    return prev[-1]


def main():
    books,labels=geometry();reconstruction=np.load(OUT/'reconstruction.npz')
    clean=clean_reference(books,labels)
    display_object(clean,labels>=0,labels,OUT/'reference-evaluation-only.png')
    folders={stage:OUT/'crops'/stage for stage in ['raw','geometry','deconvolution','reference']}
    for p in folders.values():p.mkdir(parents=True,exist_ok=True)
    paths=[];rows=[]
    stages=dict(geometry=(reconstruction['geometry'],reconstruction['geometry_support'].astype(bool)),
                deconvolution=(reconstruction['deconvolution'],reconstruction['support']),
                reference=(clean,labels>=0))
    # Locate original sensor crops using physical operator support only.
    meta=np.load(OUT/f'operator-{CACHE_TAG}-meta.npz');moments=meta['moments'];gain=moments[:,0]
    cx=np.divide(moments[:,1],gain,out=np.zeros_like(gain),where=gain>0)
    cy=np.divide(moments[:,2],gain,out=np.zeros_like(gain),where=gain>0)
    observed=np.load(TRACE/'sensor-data.npz');linear=observed['linear'];working=linear.reshape(SH,2,SW,2).mean((1,3))
    display_gain=float(observed['gain']);raw=srgb(working*display_gain)
    lo=int(meta['lo']);hi=int(meta['hi']);cx=cx.reshape(hi-lo,SW);cy=cy.reshape(hi-lo,SW);gain=gain.reshape(hi-lo,SW)
    for i,book in enumerate(books):
        bounds=title_bounds(book)
        for stage,(array,support) in stages.items():
            path=folders[stage]/f'{i+1:02}.png';save_ocr_crop(array,support,bounds,path);paths.append((i,stage,path))
        match=(cx>=book[0])&(cx<=book[1])&(cy>=book[2]*.30)&(cy<=book[2]*.84)&(gain>gain.max()*.005)
        yy,xx=np.nonzero(match)
        if len(xx):
            l=max(0,int(xx.min())-3);r=min(SW,int(xx.max())+4)
            t=max(0,int(yy.min())+lo-3);b=min(SH,int(yy.max())+lo+4)
            crop=Image.fromarray(raw[t:b,l:r][:,::-1]) # Display correction only.
            crop.thumbnail((1200,1000));crop=crop.resize((crop.width*2,crop.height*2),Image.Resampling.LANCZOS)
            crop=ImageOps.expand(crop,20,fill=255)
        else:crop=Image.new('L',(100,300),255)
        path=folders['raw']/f'{i+1:02}.png';crop.save(path);paths.append((i,'raw',path))
        l,t,r,b=bounds;common=(stages['geometry'][1]&stages['deconvolution'][1])[t:b,l:r]
        data=dict(book=i+1,truth=TITLES[i],bounds=list(bounds),
            geometryTitleBandCoverage=float(stages['geometry'][1][t:b,l:r].mean()),
            deconvolutionTitleBandCoverage=float(stages['deconvolution'][1][t:b,l:r].mean()),
            images={k:f'crops/{k}/{i+1:02}.png' for k in folders})
        for stage in ['geometry','deconvolution']:
            error=(stages[stage][0]-clean)[t:b,l:r][common]
            data[stage+'CommonObservedRmse']=float(np.sqrt(np.mean(error**2))) if len(error) else None
        rows.append(data)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs=list(pool.map(lambda job: (job[0],job[1],ocr(job[2])),paths))
    for i,stage,text in outputs:
        rows[i][stage+'Ocr']=text
        rows[i][stage+'EditDistance']=edit_distance(text,TITLES[i])
        rows[i][stage+'Exact']=text==TITLES[i]
    totals={}
    length=sum(map(len,TITLES))
    for stage in folders:
        errors=sum(r[stage+'EditDistance'] for r in rows)
        totals[stage]=dict(exactTitles=sum(r[stage+'Exact'] for r in rows),books=27,
            characterEditErrors=errors,referenceCharacters=length,characterErrorRate=errors/length)
    result=dict(ocr='Tesseract chi_sim_vert (tessdata_fast), OEM1 PSM5, no custom vocabulary; same fixed central title band for all books',
        ocrSource='https://github.com/tesseract-ocr/tessdata_fast/blob/main/chi_sim_vert.traineddata',
        referenceUse='clean textures and title strings read only in this assessment process after reconstruction; OCR gets images only',
        maskHandling='unobserved crop pixels replaced by a uniform observed median, never characters; display uses explicit hatch',
        totals=totals,books=rows,
        caution='OCR output is an independent attempt, not a guarantee of book identity; compare clean-reference OCR as an engine sanity control')
    (OUT/'assessment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(totals,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
