import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from sequential import trace
from evaluate import ROOT, OUT, load_design

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
    'axes.spines.right':False,'axes.labelcolor':'#58645c','text.color':'#28392f',
    'axes.edgecolor':'#b3bdb0','xtick.color':'#718071','ytick.color':'#718071',
    'figure.facecolor':'#f6f7f0','axes.facecolor':'#f6f7f0','savefig.facecolor':'#f6f7f0'})
r=json.loads((OUT/'results.json').read_text());p,s,film=load_design(ROOT/'data/optics/final-prescription.json')

# Geometric ray reach, with blank cells shown explicitly rather than interpolated.
c=np.load(OUT/'coverage.npz');mask=c['mask'];hits=c['hits'];image=np.zeros((100,152,4))
image[mask]=[.79,.80,.75,1];image[mask&(hits>0)]=[.21,.50,.39,1]
fig,ax=plt.subplots(figsize=(11.8,4.5),layout='constrained')
ax.imshow(image,origin='lower',extent=[-380,380,0,250],interpolation='none',aspect='equal')
books=json.loads((ROOT/'references/ikea-billy-oxberg/camera-render-input.json').read_text())['books']
for b in books:ax.plot([b['x1'],b['x1']],[0,b['height']],color='#f6f7f0',lw=.45)
ax.set(xlim=(-380,380),ylim=(0,260),xlabel='Across shelf X [mm]',ylabel='Height above shelf [mm]')
fig.suptitle('Sampled geometric reach: 61.4% of book-spine cells',fontsize=13)
ax.set_title('Green: at least one transmitted ray   |   Grey: no sampled ray reached the cell',color='#758273',fontsize=9,pad=12)
fig.savefig(OUT/'coverage-map.svg');fig.savefig(OUT/'coverage-map.png',dpi=160);plt.close(fig)

# All three spots share the same physical ruler, with a 7 mm character-sized box.
data=np.load(OUT/'field-responses.npz');indices=[17,16,15]
fig,axes=plt.subplots(1,3,figsize=(11.8,4.6),layout='constrained')
for ax,i in zip(axes,indices):
    f=r['fields'][i];w=data['weights'][i];v=w>0;points=data['points'][i,v,:2]-np.array(f['objectCentroidMm'])
    ax.scatter(points[:,0],points[:,1],s=2.4,c='#3f866b',alpha=.22,rasterized=True)
    ax.add_patch(Rectangle((-3.5,-3.5),7,7,fill=False,lw=1,ls='--',edgecolor='#ad945e'))
    ax.add_patch(Circle((0,0),f['objectD80Mm']/2,fill=False,lw=1.1,edgecolor='#bc6651'))
    ax.axhline(0,color='#ccd3c6',lw=.5);ax.axvline(0,color='#ccd3c6',lw=.5)
    ax.set(aspect='equal',xlim=(-12,12),ylim=(-12,12),xlabel='Spine-plane X offset [mm]',
        title=f"X = {abs(f['objectCentroidMm'][0]):.0f} mm, Y = 125 mm\nD80 {f['objectD80Mm']:.2f} mm | geom. MTFy {f['geometricMtfAtHalfCyclePerMmY']:.3f}")
axes[0].set_ylabel('Spine-plane Y offset [mm]')
fig.suptitle('Finite-pupil response footprints · same scale · dashed square 7 × 7 mm',fontsize=13)
fig.savefig(OUT/'response-spots.svg');fig.savefig(OUT/'response-spots.png',dpi=160);plt.close(fig)

# Actual optical surfaces and exact central-pixel paths, before the mirror.
def profile(surface,ys):
    if surface.radius==0:return np.full_like(ys,surface.z)
    rr=surface.radius
    return surface.z+rr-np.sign(rr)*np.sqrt(np.maximum(0,rr*rr-ys*ys))

fig,ax=plt.subplots(figsize=(11.8,4.2),layout='constrained')
for i,surf in enumerate(s):
    hh=surf.diameter/2 if surf.diameter else surf.height/2
    ys=np.linspace(-hh,hh,180)
    ax.plot(profile(surf,ys),ys,color='#537c8c' if surf.kind=='cylinder' else '#607468',lw=1.1)
    if surf.name=='STOP':
        ax.plot([surf.z,surf.z],[hh,5],color='#293d33',lw=2);ax.plot([surf.z,surf.z],[-5,-hh],color='#293d33',lw=2)
    if surf.n_after!=1 and i+1<len(s):
        nxt=s[i+1];height=min(hh,nxt.diameter/2 if nxt.diameter else nxt.height/2)
        yy=np.linspace(-height,height,180)
        ax.fill_betweenx(yy,profile(surf,yy),profile(nxt,yy),color='#aac5d1' if surf.kind=='cylinder' else '#a8baab',alpha=.45)
ax.plot([film,film],[-1.8,1.8],color='#4a4f69',lw=3)
origins=np.array([[0.,0.,film]]*5);pupil=np.array([[0,y,s[0].z] for y in [-.35,-.17,0,.17,.35]])
paths=trace(origins,pupil-origins,s,record=True)
for i in range(5):
    if not paths['valid'][i]:continue
    xyz=np.array([path[i] for path in paths['paths']]);ax.plot(xyz[:,2],xyz[:,1],color='#bc9255',lw=.8,alpha=.85)
    end=xyz[-1]+paths['d'][i]*15;ax.plot([xyz[-1,2],end[2]],[xyz[-1,1],end[1]],color='#bc9255',lw=.8)
ax.axhline(0,color='#adb9a9',lw=.6,ls='--')
ax.text(-9,7,'6-element fisheye\n11 refracting surfaces',ha='center',fontsize=9)
ax.text(6,10,'L1 · N-BK7\nR = ±15.679 mm',ha='center',fontsize=9)
ax.text(65,20,'L2 · N-BK7\nR = ±60.000 mm',ha='center',fontsize=9)
ax.set(xlim=(-21,87),ylim=(-20,25),xlabel='Optical Z [mm] · camera front vertex = 0 · towards M1 →',ylabel='Powered meridional coordinate [mm]',
       title='Actual surface section and traced rays · no thin-lens or imposed squeeze')
fig.savefig(OUT/'lens-section.svg');fig.savefig(OUT/'lens-section.png',dpi=160);plt.close(fig)
print('Saved coverage, finite-pupil footprints and physical lens-section figures.')
