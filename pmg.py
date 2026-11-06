"""PMG model ayristiricilari: surum 0x10, 0x13, 0x14, 0x15 (ETS2/ATS).
Her parca: (konum, normal, uv, ucgen_indeksleri, malzeme_no)."""
import struct,numpy as np,os
def _try(b,po,pc):
    out=[]
    if po<64 or po+pc*100>len(b): return None
    for i in range(pc):
        o=po+i*100
        edges,nv,uvmask,uvw,mat=struct.unpack('<5i',b[o:o+20])
        stride,pos,nor,uv,col,fac,tan,bi,bw,idxo=struct.unpack('<10i',b[o+60:o+100])
        if not(0<nv<2_000_000 and 0<edges<6_000_000 and edges%3==0 and 0<=mat<500 and 8<=stride<=200): return None
        if pos<0 or pos+stride*(nv-1)+12>len(b) or idxo<0 or idxo+edges*2>len(b): return None
        P=np.ndarray((nv,3),'<f4',b,pos,(stride,4)).copy()
        if not np.isfinite(P).all() or np.abs(P).max()>1e4: return None
        T=np.frombuffer(b,'<u2',edges,idxo).reshape(-1,3).astype(np.uint32)
        if T.max()>=nv: return None
        N=np.ndarray((nv,3),'<f4',b,nor,(stride,4)).copy() if nor!=-1 and nor+stride*(nv-1)+12<=len(b) else np.zeros((nv,3),'f4')
        n=np.linalg.norm(N,axis=1,keepdims=True); N=np.where(n>1e-6,N/np.maximum(n,1e-6),0).astype('f4')
        U=np.ndarray((nv,2),'<f4',b,uv,(stride,4)).copy() if uv!=-1 and uv+stride*(nv-1)+8<=len(b) else np.zeros((nv,2),'f4')
        if not np.isfinite(U).all(): U=np.zeros((nv,2),'f4')
        out.append((P,N,U,T,mat))
    return out
def parse_gen(b):
    pc=struct.unpack('<i',b[4:8])[0]
    for o in range(60,120,4):
        po=struct.unpack('<i',b[o:o+4])[0]
        r=_try(b,po,pc)
        if r: return r
    return None
def _try72(b):
    pc=struct.unpack('<i',b[4:8])[0]
    if not(0<pc<500): return None
    hdr=struct.unpack('<15i',b[36:96]); po=hdr[3]
    if po<64 or po+pc*72>len(b): return None
    out=[]
    for i in range(pc):
        v=struct.unpack('<18i',b[po+i*72:po+i*72+72]); edges,nv,mat=v[0],v[1],v[3]
        if not(0<nv<2_000_000 and 0<edges<6_000_000 and edges%3==0 and 0<=mat<500): return None
        if min(v[8],v[9],v[10],v[14])<0 or v[8]+nv*12>len(b) or v[9]+nv*12>len(b) or v[10]+nv*8>len(b) or v[14]+edges*2>len(b): return None
        P=np.frombuffer(b,'<f4',nv*3,v[8]).reshape(-1,3).copy(); N=np.frombuffer(b,'<f4',nv*3,v[9]).reshape(-1,3).copy(); U=np.frombuffer(b,'<f4',nv*2,v[10]).reshape(-1,2).copy()
        if not np.isfinite(P).all() or np.abs(P).max()>1e4: return None
        T=np.frombuffer(b,'<u2',edges,v[14]).reshape(-1,3).astype(np.uint32)
        if T.max()>=nv: return None
        if not np.isfinite(N).all(): N=np.zeros_like(N)
        if not np.isfinite(U).all(): U=np.zeros_like(U)
        out.append((P,N,U,T,mat))
    return out
_old=parse_gen
def parse_gen(b):
    r=_old(b)
    return r if r else _try72(b)
def _try104(b,po,pc):
    if pc<=0 or po<64 or po+pc*104>len(b): return None
    R=[struct.unpack('<26i',b[po+i*104:po+i*104+104]) for i in range(pc)]
    idxbase=min(r[22] for r in R)
    if not(0<idxbase<=len(b)): return None
    out=[]
    for i,r in enumerate(R):
        edges,nv,mat=r[0],r[1],r[5]; pos,nor,uv,idxo=r[16],r[17],r[18],r[22]
        if not(0<nv<2_000_000 and 0<edges<6_000_000 and edges%3==0 and 0<=mat<500 and pos>0 and idxo>0): return None
        nxt=R[i+1][16] if i+1<pc else idxbase
        if nxt<=pos: return None
        stride=(nxt-pos)//nv
        if stride<24 or stride>200 or pos+stride*(nv-1)+12>len(b) or idxo+edges*2>len(b): return None
        P=np.ndarray((nv,3),'<f4',b,pos,(stride,4)).copy()
        if not np.isfinite(P).all() or np.abs(P).max()>1e4: return None
        T=np.frombuffer(b,'<u2',edges,idxo).reshape(-1,3).astype(np.uint32)
        if T.max()>=nv: return None
        N=np.ndarray((nv,3),'<f4',b,nor,(stride,4)).copy(); n=np.linalg.norm(N,axis=1,keepdims=True); N=np.where(n>1e-6,N/np.maximum(n,1e-6),0).astype('f4')
        U=np.ndarray((nv,2),'<f4',b,uv,(stride,4)).copy()
        if not np.isfinite(N).all(): N=np.zeros_like(N)
        if not np.isfinite(U).all(): U=np.zeros_like(U)
        out.append((P,N,U,T,mat))
    return out
_old2=parse_gen
def parse_gen(b):
    r=_old2(b)
    if r: return r
    pc=struct.unpack('<i',b[4:8])[0]
    for o in range(60,100,4):
        r=_try104(b,struct.unpack('<i',b[o:o+4])[0],pc)
        if r: return r
    return None


def parse_pmg(b):
    """PMG baytlarini parcalara ayirir; taninmazsa None. Bos modeller icin []."""
    if len(b) < 16 or b[1:4] != b'gmP': return None
    if struct.unpack('<i', b[4:8])[0] == 0: return []
    try: return parse_gen(b)
    except Exception: return None
