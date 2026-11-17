"""Comparable object-plane plots, fixed physical axes and a shared colour scale."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from optimize_layout import OUT,density,FILM
from layout import BASELINE

def main():
    validation=json.loads((OUT/'validation.json').read_text())
    fig,axes=plt.subplots(2,1,figsize=(11.8,7.4),layout='constrained')
    fig.patch.set_facecolor('#f3f5ed')
    for ax,name,title in zip(axes,['before','after'],['Before','Optimized']):
        data=np.load(OUT/(name+'-density.npz'))
        z=np.ma.array(data['density'],mask=~data['mask'])
        image=ax.imshow(z,extent=[-379.65,379.65,0,250],origin='lower',cmap='cividis',vmin=0,vmax=4,aspect='equal',interpolation='nearest')
        ax.set_facecolor('#e5e9dd');ax.set_ylabel('Height above shelf (mm)');ax.set_xlabel('Across shelf (mm)')
        ax.set_title(f"{title}  |  minimum {validation[name]['minPxPerMm']:.3f} px/mm",loc='left',fontsize=12)
        pt=validation[name]['worstPointMm'];ax.plot(pt[0],pt[1],marker='o',ms=6,mfc='none',mec='#e34d34',clip_on=False)
    fig.colorbar(image,ax=axes,shrink=.9,label='Native sensor pixels / spine mm, most compressed direction')
    fig.savefig(OUT/'density-comparison.png',dpi=160,facecolor=fig.get_facecolor());plt.close(fig)
    pts=np.array([[0,50,60.],[0,125,60.],[-350,125,60.],[350,125,60.]])
    samples={}
    for name,l,f in [('before',BASELINE,FILM),('after',validation['after']['layout'],validation['after']['filmZMm'])]:
        d=density(pts,l,f)
        samples[name]=[dict(pointMm=p.tolist(),minPxPerMm=float(v),char8mmMinDirectionPx=float(v*8)) for p,v in zip(pts,d['density'])]
    validation['representativePoints']=samples
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')

if __name__=='__main__':main()
