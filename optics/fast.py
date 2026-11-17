"""Numba implementation checked against the independent NumPy tracer."""
import math
import numpy as np
from numba import njit, prange, literal_unroll
from layout import BASELINE, packed
BASELINE_PACK=packed(BASELINE)


def pack(surfaces):
    return np.array([[s.z,s.radius,s.n_before,s.n_after,
        {'sphere':0,'cylinder':1,'plane':2}[s.kind],s.diameter,s.width,s.height] for s in surfaces],float)


@njit(cache=True)
def one_ray(x,y,z,dx,dy,dz,surfaces):
    ll=math.sqrt(dx*dx+dy*dy+dz*dz);dx/=ll;dy/=ll;dz/=ll
    power=1.
    for i in range(len(surfaces)):
        zv,r,n1,n2,kind,diam,width,height=surfaces[i]
        if kind==2 or r==0:
            if abs(dz)<1e-12:return x,y,z,dx,dy,dz,0.,False,i
            t=(zv-z)/dz
            if t < -1e-8:return x,y,z,dx,dy,dz,0.,False,i
            hx=x+t*dx;hy=y+t*dy;hz=z+t*dz;nx=0.;ny=0.;nz=1.
        else:
            cz=zv+r;vz=z-cz
            a=dy*dy+dz*dz;bb=2*(y*dy+vz*dz);cc=y*y+vz*vz-r*r
            if kind==0:
                a+=dx*dx;bb+=2*x*dx;cc+=x*x
            disc=bb*bb-4*a*cc
            if disc<0 or a<1e-20:return x,y,z,dx,dy,dz,0.,False,i
            root=math.sqrt(disc);tt1=(-bb-root)/(2*a);tt2=(-bb+root)/(2*a)
            t=1e30
            if tt1>=-1e-8 and (z+tt1*dz-cz)*r<=1e-8:t=tt1
            if tt2>=-1e-8 and (z+tt2*dz-cz)*r<=1e-8:t=min(t,tt2)
            if t>1e29:return x,y,z,dx,dy,dz,0.,False,i
            hx=x+t*dx;hy=y+t*dy;hz=z+t*dz
            nx=hx if kind==0 else 0.;ny=hy;nz=hz-cz
            ll=math.sqrt(nx*nx+ny*ny+nz*nz);nx/=ll;ny/=ll;nz/=ll
        if diam>0:
            if hx*hx+hy*hy>(diam*.5)**2:return hx,hy,hz,dx,dy,dz,0.,False,i
        elif abs(hx)>width*.5 or abs(hy)>height*.5:
            return hx,hy,hz,dx,dy,dz,0.,False,i
        x=hx;y=hy;z=hz
        if n1!=n2:
            dot=dx*nx+dy*ny+dz*nz
            if dot>0:nx=-nx;ny=-ny;nz=-nz;dot=-dot
            ci=max(0.,min(1.,-dot));eta=n1/n2;sin2=eta*eta*(1-ci*ci)
            if sin2>1:return x,y,z,dx,dy,dz,0.,False,-i-1
            ct=math.sqrt(max(0.,1-sin2));a=eta*ci-ct
            dx=eta*dx+a*nx;dy=eta*dy+a*ny;dz=eta*dz+a*nz
            ll=math.sqrt(dx*dx+dy*dy+dz*dz);dx/=ll;dy/=ll;dz/=ll
            rs=((n1*ci-n2*ct)/(n1*ci+n2*ct+1e-30))**2
            rp=((n1*ct-n2*ci)/(n1*ct+n2*ci+1e-30))**2
            power*=1-(rs+rp)/2
    return x,y,z,dx,dy,dz,power,True,999


@njit(cache=True,parallel=True)
def trace_batch(origins,directions,surfaces):
    out=np.zeros((len(origins),9))
    for k in prange(len(origins)):
        r=one_ray(origins[k,0],origins[k,1],origins[k,2],directions[k,0],directions[k,1],directions[k,2],surfaces)
        for j in literal_unroll((0,1,2,3,4,5,6,7,8)):out[k,j]=r[j]
    return out


@njit(cache=True)
def box_hit(x,y,z,dx,dy,dz,bounds):
    origins=(x,y,z);dirs=(dx,dy,dz);lo=0.;hi=1e30;face=-1
    for axis in range(3):
        a=bounds[axis*2];b=bounds[axis*2+1];o=origins[axis];d=dirs[axis]
        if abs(d)<1e-12:
            if o<a or o>b:return 1e30,-1
        else:
            u=(a-o)/d;v=(b-o)/d;ff=axis*2
            if u>v:u,v=v,u;ff+=1
            if u>lo:lo=u;face=ff
            hi=min(hi,v)
            if lo>hi:return 1e30,-1
    if lo<1e-7:return 1e30,-1
    return lo,face


@njit(cache=True)
def environment(x,y,z,dx,dy,dz,books,textures):
    # Primitive diffuse scene; returns radiance and book-front coordinates only.
    best=1e30;face=-1;bid=-1;normal=0
    for i in range(len(books)):
        b=books[i];bounds=(b[0],b[1],0.,b[2],60.,260.)
        t,f=box_hit(x,y,z,dx,dy,dz,bounds)
        if t<best:best=t;face=f;bid=i
    # Opaque internal cabinet panels. Front glass is outside the imaging path.
    walls=((-380.,0,0),(380.,0,1),(0.,1,2),(328.,1,3),(260.,2,5))
    origins=(x,y,z);dirs=(dx,dy,dz)
    for position,axis,ff in walls:
        aa=int(axis);dd=dirs[aa]
        if abs(dd)>1e-12:
            t=(position-origins[aa])/dd
            if t>1e-7 and t<best:
                hx=x+t*dx;hy=y+t*dy;hz=z+t*dz
                if -380.01<=hx<=380.01 and -.01<=hy<=328.01 and -.01<=hz<=260.01:
                    best=t;face=int(ff);bid=-1
    if best>1e29:return .6,-1,0.,0.,1e30
    hx=x+best*dx;hy=y+best*dy;hz=z+best*dz
    albedo=.80
    if bid>=0:
        if face==4:
            b=books[bid]
            u=(hx-b[0])/(b[1]-b[0]);v=1-hy/b[2]
            px=min(textures.shape[2]-1,max(0,int(u*textures.shape[2])))
            py=min(textures.shape[1]-1,max(0,int(v*textures.shape[1])))
            albedo=(textures[bid,py,px]/255.)**2.2
        elif face==3:
            albedo=.73+.025*math.sin(hx*30)+.015*math.sin(hz*24)
        else:albedo=.2+.02*(bid%6)
    # Broad front room light + ambient fill, no arbitrary sharpening or denoising.
    lx=-250-hx;ly=420-hy;lz=-500-hz;ll=math.sqrt(lx*lx+ly*ly+lz*lz)
    normals=((-1.,0.,0.),(1.,0.,0.),(0.,-1.,0.),(0.,1.,0.),(0.,0.,-1.),(0.,0.,1.))
    nn=normals[face];diffuse=max(0.,(nn[0]*lx+nn[1]*ly+nn[2]*lz)/ll)
    if bid<0:diffuse=abs((nn[0]*lx+nn[1]*ly+nn[2]*lz)/ll)
    luminance=albedo*(.25+.75*diffuse)
    return luminance,bid if face==4 else -1,hx,hy,best


@njit(cache=True)
def scene_ray(ox,oy,oz,dx,dy,dz,books,textures,layout=BASELINE_PACK):
    # Optical frame → the shelf frame. Constants match the main 3D model.
    x=layout[0]+ox;y=layout[1]+layout[4]*oy+layout[7]*oz;z=layout[2]+layout[5]*oy+layout[8]*oz
    wx=dx;wy=layout[4]*dy+layout[7]*dz;wz=layout[5]*dy+layout[8]*dz
    ny=layout[13];nz=layout[14]
    my=layout[10];mz=layout[11]
    denom=wy*ny+wz*nz
    tm=1e30
    if abs(denom)>1e-12:
        t=((my-y)*ny+(mz-z)*nz)/denom
        qx=x+t*wx;qy=y+t*wy;qz=z+t*wz
        u=(qy-my)*layout[16]+(qz-mz)*layout[17]
        if t>1e-7 and abs(qx)<layout[18]+1 and abs(u)<layout[19]+1:tm=t
    lum,bid,hx,hy,ts=environment(x,y,z,wx,wy,wz,books,textures)
    if tm<ts:
        if abs(qx)>layout[18] or abs(u)>layout[19]:return .008,-1,0.,0.
        ry=wy-2*denom*ny;rz=wz-2*denom*nz
        ll,bid,hx,hy,_=environment(qx+wx*1e-7,qy+ry*1e-7,qz+rz*1e-7,wx,ry,rz,books,textures)
        return .92*ll,bid,hx,hy
    return lum,bid,hx,hy


@njit(cache=True,parallel=True)
def render_rows(y0,y1,width,height,surfaces,film_z,bounds,samples,books,textures,layout=BASELINE_PACK):
    image=np.zeros((y1-y0,width))
    # Store hit counts per row, then reduce without races outside the parallel loop.
    hits=np.zeros((y1-y0,100,152),np.int32)
    half_hits=np.zeros((y1-y0,100,152),np.int32)
    pass_counts=np.zeros((y1-y0,3),np.int64)
    nr=len(bounds);maxr=math.sqrt(3.2**2+1.8**2)
    for yy in prange(y0,y1):
        row=yy-y0
        film_y=((yy+.5)/height-.5)*3.6
        for xx in range(width):
            film_x=((xx+.5)/width-.5)*6.4
            rr=math.sqrt(film_x*film_x+film_y*film_y)
            a=min(nr-1.000001,rr/maxr*(nr-1));j=int(a);a-=j
            qmin=bounds[j,0]*(1-a)+bounds[j+1,0]*a
            qmax=bounds[j,1]*(1-a)+bounds[j+1,1]*a
            qtan=bounds[j,2]*(1-a)+bounds[j+1,2]*a
            ux=film_x/rr if rr>1e-12 else 1.;uy=film_y/rr if rr>1e-12 else 0.
            area=(qmax-qmin)*2*qtan
            # Cranley rotation per pixel breaks coherent quadrature banding.
            hsh=(xx*73856093 ^ yy*19349663)&0x7fffffff
            shift1=(hsh%100003)/100003.;shift2=((hsh//100003)%100019)/100019.
            value=0.
            for ss in range(len(samples)):
                u=(samples[ss,0]+shift1)%1.;v=(samples[ss,1]+shift2)%1.
                qr=qmin+u*(qmax-qmin);qt=(v*2-1)*qtan
                px=qr*ux-qt*uy;py=qr*uy+qt*ux
                rx=px-film_x;ry=py-film_y;rz=surfaces[0,0]-film_z
                length=math.sqrt(rx*rx+ry*ry+rz*rz);cos4=(rz/length)**4
                ox,oy,oz,dx,dy,dz,power,valid,reason=one_ray(film_x,film_y,film_z,rx,ry,rz,surfaces)
                pass_counts[row,0]+=1
                if valid:
                    pass_counts[row,1]+=1
                    lum,bid,hx,hy=scene_ray(ox,oy,oz,dx,dy,dz,books,textures,layout)
                    value+=lum*power*cos4
                    if bid>=0 and 0<=hy<=250 and abs(hx)<=380:
                        pass_counts[row,2]+=1
                        col=min(151,max(0,int((hx+380)/5)))
                        line=min(99,max(0,int(hy/2.5)))
                        hits[row,line,col]+=1
                        if ss<len(samples)//2:half_hits[row,line,col]+=1
            image[row,xx]=value/len(samples)*area/(surfaces[0,0]-film_z)**2
    return image,np.sum(hits,axis=0),np.sum(pass_counts,axis=0),np.sum(half_hits,axis=0),pass_counts[:,2]
