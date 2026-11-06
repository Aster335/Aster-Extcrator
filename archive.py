"""SCS arsiv okuyucular: duz zip (bozuk yerel basliklara toleransli) ve hash tabanli (HashFS) .scs."""
import os, re, struct, zlib, zipfile, collections
from .cityhash import path_hash

class LockedError(Exception):
    """Dosya sifreli / kilitli."""
class InvalidArchiveError(Exception):
    """Dosya taninan bir .scs bicimi degil."""

class ZipArchive:
    kind = 'zip'
    def __init__(self, path):
        self.f = open(path, 'rb')
        try: self.z = zipfile.ZipFile(path)
        except Exception as e: raise InvalidArchiveError(str(e))
        self.info = {i.filename: i for i in self.z.infolist() if not i.is_dir()}
        enc = [n for n, i in self.info.items() if i.flag_bits & 1]
        keyfiles = [n for n in enc if n.lower().endswith(('.pmg', '.pmd', '.mat', '.dds', '.tobj'))]
        if keyfiles or (self.info and len(enc) * 2 >= len(self.info)): raise LockedError('sifreli zip')
        self.low = {n.lower(): n for n in self.info}
        self.base = collections.defaultdict(list)
        for n in self.info: self.base[os.path.basename(n).lower()].append(n)
    def close(self): self.f.close(); self.z.close()
    def read(self, key):
        i = self.info[key]; self.f.seek(i.header_offset)
        h = self.f.read(30); nl, el = struct.unpack('<HH', h[26:30]); self.f.seek(i.header_offset + 30 + nl + el)
        raw = self.f.read(i.compress_size)
        if i.compress_type == 8: return zlib.decompress(raw, -15)
        if i.compress_type == 0: return raw
        raise InvalidArchiveError('desteklenmeyen sikistirma')
    def peek(self, key, n=64): return self.read(key)[:n]
    def model_keys(self): return [n for n in self.info if n.lower().endswith('.pmg')]
    def display(self, key, prefix='model_'): return key[:-4] if key.lower().endswith('.pmg') else key
    def resolve(self, ref, relto=''):
        ref = ref.strip().replace('\\', '/')
        for c in (ref.lstrip('/'), (relto + '/' + ref) if relto else ref, (relto + '/' + os.path.basename(ref)) if relto else ref):
            if c.lower() in self.low: return self.low[c.lower()]
        b = self.base.get(os.path.basename(ref).lower())
        return b[0] if b else None
    def dirname(self, key): return os.path.dirname(key)
    def pmd_for(self, key):
        k = self.resolve(key[:-4] + '.pmd')
        return self.read(k) if k and k.lower() == key[:-4].lower() + '.pmd' else None
    def all_keys(self): return list(self.info)

class HashFSArchive:
    kind = 'hashfs'
    def __init__(self, path):
        self.f = open(path, 'rb'); h = self.f.read(20)
        if h[:4] != b'SCS#' or h[8:12] != b'CITY': raise InvalidArchiveError('SCS# degil')
        ver = struct.unpack('<H', h[4:6])[0]
        if ver != 1: raise InvalidArchiveError('HashFS surum %d desteklenmiyor' % ver)
        cnt, start = struct.unpack('<II', h[12:20]); self.f.seek(start)
        self.E = {}
        for _ in range(cnt):
            a, off, fl, crc, sz, csz = struct.unpack('<QQIIII', self.f.read(32)); self.E[a] = (off, fl, sz, csz)
        self.names = {}
        self._dirnames()
    def close(self): self.f.close()
    def read(self, key):
        off, fl, sz, csz = self.E[key]; self.f.seek(off); b = self.f.read(csz)
        return zlib.decompress(b) if fl & 2 else b
    def peek(self, key, n=64):
        off, fl, sz, csz = self.E[key]; self.f.seek(off)
        if fl & 2: return zlib.decompressobj().decompress(self.f.read(min(csz, 4096)), n)
        return self.f.read(min(n, csz))
    def _dirnames(self):
        """Dizin girdileri varsa tum dosya adlarini onlardan al."""
        todo = [''];
        while todo:
            d = todo.pop(); k = path_hash(d)
            if k not in self.E or not self.E[k][1] & 1: continue
            for line in self.read(k).decode('utf-8', 'ignore').splitlines():
                line = line.strip()
                if not line: continue
                if line.startswith('*'): todo.append((d + '/' + line[1:]).strip('/'))
                else: self.names[path_hash((d + '/' + line).strip('/'))] = (d + '/' + line).strip('/')
    def model_keys(self):
        return [k for k, e in self.E.items() if not e[1] & 1 and e[2] > 16 and self.peek(k, 4)[1:4] == b'gmP']
    def display(self, key, prefix='m_'):
        n = self.names.get(key)
        if n: return n[:-4] if n.lower().endswith('.pmg') else n
        return '%s%06x' % (prefix, key & 0xffffff)
    def resolve(self, ref, relto=''):
        ref = ref.strip().replace('\\', '/')
        for c in (ref.lstrip('/'), (relto + '/' + ref) if relto else ref, (relto + '/' + os.path.basename(ref)) if relto else ref):
            k = path_hash(c)
            if k in self.E and not self.E[k][1] & 1: return k
        return None
    def dirname(self, key): return os.path.dirname(self.names.get(key, ''))
    def pmd_for(self, key):
        n = self.names.get(key)
        if n:
            k = path_hash(n[:-4] + '.pmd')
            if k in self.E: return self.read(k)
        return None
    def all_keys(self): return [k for k, e in self.E.items() if not e[1] & 1]

def open_scs(path):
    with open(path, 'rb') as f: head = f.read(8)
    if head[:4] == b'SCS#': return HashFSArchive(path)
    if head[:2] == b'PK' or zipfile.is_zipfile(path): return ZipArchive(path)
    raise InvalidArchiveError('taninmayan dosya bicimi')
