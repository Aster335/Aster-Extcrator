"""Ana is akisi: .scs -> (GLB + OBJ + PNG) iceren zip."""
import io, os, re, struct, hashlib, zipfile, collections
import numpy as np
from PIL import Image as PILImage
from pygltflib import (GLTF2, Scene, Sampler, Buffer, BufferView, Accessor, Mesh, Primitive, Attributes, Node, Material,
                       PbrMetallicRoughness, TextureInfo, Texture, Image, ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT,
                       UNSIGNED_SHORT, UNSIGNED_INT)
from .archive import open_scs, LockedError, InvalidArchiveError
from .pmg import parse_pmg

PILImage.MAX_IMAGE_PIXELS = None
WHEEL_RE = re.compile(r'wheel|tire|tyre|lastik|jant|tekerlek|(^|[/_\\])(rim|hub|cant)([/_\\.]|$)', re.I)

class Model:
    def __init__(self, name, pieces, mats, key):
        self.name, self.pieces, self.mats, self.key = name, pieces, mats, key

def _is_wheel_shape(pieces):
    P = np.concatenate([p[0] for p in pieces]); ext = np.sort(P.max(0) - P.min(0))[::-1]
    return 0.55 <= ext[0] < 1.6 and ext[1] / ext[0] > 0.92 and 0.15 < ext[2] / ext[0] < 0.8

def _material_info(arc, mkey):
    """(shader, doku_anahtari, diffuse_rgb) dondurur."""
    t = arc.read(mkey).decode('latin1'); d = arc.dirname(mkey)
    sh = re.search(r'material\s*:\s*"([^"]+)"', t); sh = sh.group(1) if sh else ''
    tx = re.search(r'texture\[0\]\s*:\s*"([^"]+)"', t) or re.search(r'texture\s*:\s*"([^"]+)"', t)
    tex = None
    if tx:
        tob = arc.resolve(tx.group(1), d)
        if tob is not None:
            b = arc.read(tob)
            if b[:4] == bytes.fromhex('010ab170') or tx.group(1).lower().endswith('.tobj'):
                s = re.findall(rb'[\w/.\-]+\.(?:dds|tga|png|jpg)', b)
                if s: tex = arc.resolve(s[0].decode(), arc.dirname(tob))
                if tex is None:  # tobj yol icermiyorsa ayni adli dds'i dene
                    stem = tx.group(1).rsplit('.', 1)[0]; tex = arc.resolve(stem + '.dds', d)
            else: tex = tob
    dm = re.search(r'diffuse\s*:\s*\{([^}]+)\}', t); dv = None
    if dm:
        try: dv = [min(1.0, float(x)) for x in dm.group(1).split(',')][:3]
        except ValueError: pass
    return sh, tex, dv

def collect_models(arc, skip_wheels=True, progress=lambda f, m: None):
    keys = arc.model_keys(); pmds = {}
    if arc.kind == 'hashfs':   # adsiz pmd'leri icerikten bul
        for k in arc.all_keys():
            h = arc.peek(k, 64)
            if h[:4] == b'\x04\x00\x00\x00' and len(h) >= 64:
                v = struct.unpack('<16I', h)
                if 0 < v[1] < 300 and v[3] < 500 and v[5] < 50: pmds[k] = v
    seen, sig, out, skipped = set(), set(), [], 0
    for n, k in enumerate(keys):
        progress(n / max(1, len(keys)), 'Modeller okunuyor (%d/%d)' % (n + 1, len(keys)))
        b = arc.read(k); h = hashlib.md5(b).hexdigest()
        if h in seen: continue
        seen.add(h); pcs = parse_pmg(b)
        if not pcs: continue
        s = (tuple(len(p[0]) for p in pcs), tuple(len(p[3]) for p in pcs))
        if s in sig: continue
        sig.add(s); name = arc.display(k)
        if skip_wheels and (WHEEL_RE.search(name) or (k not in getattr(arc, 'names', {}) and arc.kind == 'hashfs' and _is_wheel_shape(pcs))):
            skipped += 1; continue
        mats = []; pd = arc.pmd_for(k)
        if pd is None and pmds:
            pc, parts = struct.unpack('<ii', b[4:12]); mm = max(p[4] for p in pcs)
            c = sorted([a for a, v in pmds.items() if v[5] == parts and v[1] > mm], key=lambda a: (pmds[a][3] != pc, pmds[a][1] - mm - 1))
            pd = arc.read(c[0]) if c else None
        if pd:
            names = re.findall(rb'[\w/.\-]+\.mat', pd)
            if pd[:4] == b'\x04\x00\x00\x00' and len(pd) >= 64:
                cnt = struct.unpack('<I', pd[4:8])[0]
                if 0 < cnt <= len(names): names = names[:cnt]
            mats = [arc.resolve(m.decode(), arc.dirname(k)) for m in names]
        out.append(Model(name, pcs, mats, k))
    return out, skipped

class TexStore:
    def __init__(self, arc, max_size): self.arc, self.max, self.png, self.names = arc, max_size, {}, {}
    def get(self, key):
        if key in self.png: return self.png[key]
        r = None
        try:
            im = PILImage.open(io.BytesIO(self.arc.read(key))); im.load(); im = im.convert('RGBA')
            if max(im.size) > self.max: im.thumbnail((self.max, self.max))
            o = io.BytesIO(); im.save(o, 'PNG'); r = o.getvalue()
        except Exception: r = None
        self.png[key] = r; return r
    def filename(self, key):
        if key not in self.names:
            base = os.path.splitext(os.path.basename(self.arc.display(key, 'tex_')))[0]
            n, i = base, 1
            while n in self.names.values(): i += 1; n = '%s_%d' % (base, i)
            self.names[key] = n
        return self.names[key] + '.png'

class MatCache:
    def __init__(self, arc, tex): self.arc, self.tex, self.c = arc, tex, {}
    def get(self, mkey):
        if mkey in self.c: return self.c[mkey]
        sh, tk, dv = '', None, None
        if mkey is not None:
            try: sh, tk, dv = _material_info(self.arc, mkey)
            except Exception: pass
        nm = os.path.splitext(os.path.basename(self.arc.display(mkey, 'mat_')))[0] if mkey is not None else 'malzeme'
        glass = 'glass' in sh.lower() or 'tintadd' in sh.lower() or nm.lower().startswith(('cam', 'glass'))
        png = None
        if tk is not None and not glass and self.tex.get(tk): png = tk
        self.c[mkey] = dict(name=nm, glass=glass, tex=png, diffuse=dv); return self.c[mkey]

def write_glb(models, mc, tex):
    g = GLTF2(); blob = bytearray(); g.scene = 0; g.scenes = [Scene(nodes=[])]
    g.samplers = [Sampler(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
    def add(arr, target, comp, typ, mn=None, mx=None):
        while len(blob) % 4: blob.append(0)
        bb = arr.tobytes(); g.bufferViews.append(BufferView(buffer=0, byteOffset=len(blob), byteLength=len(bb), target=target)); blob.extend(bb)
        g.accessors.append(Accessor(bufferView=len(g.bufferViews) - 1, componentType=comp, count=arr.shape[0], type=typ, min=mn, max=mx)); return len(g.accessors) - 1
    texidx, matidx = {}, {}
    def material(mkey):
        if mkey in matidx: return matidx[mkey]
        i = mc.get(mkey); pm = PbrMetallicRoughness(metallicFactor=0.0, roughnessFactor=0.6); m = Material(name=i['name'], pbrMetallicRoughness=pm, doubleSided=True)
        if i['diffuse'] and not i['glass']: pm.baseColorFactor = i['diffuse'] + [1.0]
        if i['tex'] is not None:
            if i['tex'] not in texidx:
                png = tex.get(i['tex'])
                while len(blob) % 4: blob.append(0)
                g.bufferViews.append(BufferView(buffer=0, byteOffset=len(blob), byteLength=len(png))); blob.extend(png)
                g.images.append(Image(bufferView=len(g.bufferViews) - 1, mimeType='image/png', name=tex.filename(i['tex'])))
                g.textures.append(Texture(source=len(g.images) - 1, sampler=0)); texidx[i['tex']] = len(g.textures) - 1
            pm.baseColorTexture = TextureInfo(index=texidx[i['tex']])
        if i['glass']: m.alphaMode = 'BLEND'; pm.baseColorFactor = [0.55, 0.7, 0.8, 0.35]
        g.materials.append(m); matidx[mkey] = len(g.materials) - 1; return matidx[mkey]
    for md in models:
        kids = []; stem = md.name.replace('/', '_')
        for i, (P, N, U, T, mi) in enumerate(md.pieces):
            mk = md.mats[mi] if mi < len(md.mats) else None
            if mk is not None and 'fakeshadow' in mc.get(mk)['name'].lower(): continue
            ia = T[:, [0, 2, 1]].reshape(-1).astype('<u2' if len(P) < 65535 else '<u4')
            at = add(P.astype('<f4'), ARRAY_BUFFER, FLOAT, 'VEC3', P.min(0).tolist(), P.max(0).tolist())
            an = add(N.astype('<f4'), ARRAY_BUFFER, FLOAT, 'VEC3'); au = add(U.astype('<f4'), ARRAY_BUFFER, FLOAT, 'VEC2')
            ix = add(ia, ELEMENT_ARRAY_BUFFER, UNSIGNED_SHORT if len(P) < 65535 else UNSIGNED_INT, 'SCALAR', [int(ia.min())], [int(ia.max())])
            g.meshes.append(Mesh(name='%s_p%d' % (stem, i), primitives=[Primitive(attributes=Attributes(POSITION=at, NORMAL=an, TEXCOORD_0=au), indices=ix, material=material(mk))]))
            g.nodes.append(Node(name='%s_p%d' % (stem, i), mesh=len(g.meshes) - 1)); kids.append(len(g.nodes) - 1)
        if kids: g.nodes.append(Node(name='model_' + stem, children=kids)); g.scenes[0].nodes.append(len(g.nodes) - 1)
    g.buffers = [Buffer(byteLength=len(blob))]; g.set_binary_blob(bytes(blob))
    r = g.save_to_bytes()
    return r if isinstance(r, (bytes, bytearray)) else b''.join(r)

def write_obj(md, mc, tex):
    """(obj_metni, mtl_metni) dondurur."""
    L = ['mtllib %s.mtl' % md.name.replace('/', '_')]; mtl = {}; vo = 0
    for i, (P, N, U, T, mi) in enumerate(md.pieces):
        mk = md.mats[mi] if mi < len(md.mats) else None; info = mc.get(mk)
        if 'fakeshadow' in info['name'].lower(): continue
        mname = '%s_%d' % (info['name'], mi); mtl[mname] = info
        L.append('o %s_p%d' % (md.name.replace('/', '_'), i)); L.append('usemtl ' + mname)
        L.extend('v %.5f %.5f %.5f' % (a, b, c) for a, b, c in P)
        L.extend('vt %.5f %.5f' % (u, 1 - v) for u, v in U)
        L.extend('vn %.4f %.4f %.4f' % (a, b, c) for a, b, c in N)
        F = T[:, [0, 2, 1]] + 1 + vo
        L.extend('f %d/%d/%d %d/%d/%d %d/%d/%d' % (a, a, a, b, b, b, c, c, c) for a, b, c in F); vo += len(P)
    M = []
    for n, i in mtl.items():
        M.append('newmtl ' + n); d = i['diffuse'] or [0.8, 0.8, 0.8]; M.append('Kd %.3f %.3f %.3f' % tuple(d))
        if i['glass']: M.append('d 0.35')
        if i['tex'] is not None: M.append('map_Kd ../textures/' + tex.filename(i['tex']))
    return '\n'.join(L) + '\n', '\n'.join(M) + '\n'

def convert(scs_path, out_zip, progress=lambda f, m: None, max_tex=2048, skip_wheels=True):
    """scs_path -> out_zip. LockedError / InvalidArchiveError firlatabilir. Sonuc ozeti (dict) dondurur."""
    progress(0.0, 'Dosya aciliyor'); arc = open_scs(scs_path)
    try:
        models, skipped = collect_models(arc, skip_wheels, lambda f, m: progress(0.05 + 0.35 * f, m))
        if not models: raise InvalidArchiveError('Dosyada cevrilebilir 3B model bulunamadi')
        tex = TexStore(arc, max_tex); mc = MatCache(arc, tex)
        stem = os.path.splitext(os.path.basename(scs_path))[0]
        progress(0.42, 'GLB hazirlaniyor')
        glb = write_glb(models, mc, tex)
        tmp = out_zip + '.tmp'
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr(zipfile.ZipInfo(stem + '.glb'), glb, zipfile.ZIP_STORED)
            for n, md in enumerate(models):
                progress(0.6 + 0.3 * n / len(models), 'OBJ yaziliyor (%d/%d)' % (n + 1, len(models)))
                o, m = write_obj(md, mc, tex); nm = md.name.replace('/', '_')
                z.writestr('obj/%s.obj' % nm, o); z.writestr('obj/%s.mtl' % nm, m)
            progress(0.92, 'Dokular yaziliyor')
            for key, fn0 in tex.names.items():
                fn = fn0 + '.png'
                if tex.png.get(key): z.writestr('textures/' + fn, tex.png[key], zipfile.ZIP_STORED)
        os.replace(tmp, out_zip); progress(1.0, 'Tamamlandi')
        return dict(models=len(models), wheels_skipped=skipped, textures=sum(1 for v in tex.png.values() if v), kind=arc.kind)
    finally: arc.close()
