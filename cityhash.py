"""SCS'in kullandigi CityHash64 (saf Python). Hash tabanli .scs arsivlerinde dosya yollarini cozmek icin gerekir."""
import struct
M = (1 << 64) - 1
K0, K1, K2, K3 = 0xc3a5c85c97cb3127, 0xb492b66fbe98f273, 0x9ae16a3b2f90404f, 0xc949d7c7509e6557

def _f64(s, i): return struct.unpack_from('<Q', s, i)[0]
def _f32(s, i): return struct.unpack_from('<I', s, i)[0]
def _rot(v, n): return v if n == 0 else ((v >> n) | (v << (64 - n))) & M
def _sm(v): return v ^ (v >> 47)
def _h16(u, v):
    k = 0x9ddfea08eb382d69
    a = ((u ^ v) * k) & M; a ^= a >> 47
    b = ((v ^ a) * k) & M; b ^= b >> 47
    return (b * k) & M
def _h0_16(s, n):
    if n > 8:
        a = _f64(s, 0); b = _f64(s, n - 8)
        return _h16(a, _rot((b + n) & M, n)) ^ b
    if n >= 4:
        a = _f32(s, 0)
        return _h16((n + (a << 3)) & M, _f32(s, n - 4))
    if n > 0:
        a, b, c = s[0], s[n >> 1], s[n - 1]
        y = (a + (b << 8)) & 0xffffffff; z = (n + (c << 2)) & 0xffffffff
        return (_sm(((y * K2) & M) ^ ((z * K3) & M)) * K2) & M
    return K2
def _h17_32(s, n):
    a = (_f64(s, 0) * K1) & M; b = _f64(s, 8)
    c = (_f64(s, n - 8) * K2) & M; d = (_f64(s, n - 16) * K0) & M
    return _h16((_rot((a - b) & M, 43) + _rot(c, 30) + d) & M,
                (a + _rot(b ^ K3, 20) - c + n) & M)
def _weak(w, x, y, z, a, b):
    a = (a + w) & M
    b = _rot((b + a + z) & M, 21)
    c = a
    a = (a + x + y) & M
    b = (b + _rot(a, 44)) & M
    return (a + z) & M, (b + c) & M
def _weak_s(s, i, a, b): return _weak(_f64(s, i), _f64(s, i + 8), _f64(s, i + 16), _f64(s, i + 24), a, b)
def _h33_64(s, n):
    z = _f64(s, 24)
    a = (_f64(s, 0) + (n + _f64(s, n - 16)) * K0) & M
    b = _rot((a + z) & M, 52); c = _rot(a, 37)
    a = (a + _f64(s, 8)) & M; c = (c + _rot(a, 7)) & M
    a = (a + _f64(s, 16)) & M
    vf = (a + z) & M; vs = (b + _rot(a, 31) + c) & M
    a = (_f64(s, 16) + _f64(s, n - 32)) & M; z = _f64(s, n - 8)
    b = _rot((a + z) & M, 52); c = _rot(a, 37)
    a = (a + _f64(s, n - 24)) & M; c = (c + _rot(a, 7)) & M
    a = (a + _f64(s, n - 16)) & M
    wf = (a + z) & M; ws = (b + _rot(a, 31) + c) & M
    r = _sm(((vf + ws) * K2 + (wf + vs) * K0) & M)
    return (_sm((r * K0 + vs) & M) * K2) & M

def city64(data):
    s = data if isinstance(data, (bytes, bytearray)) else data.encode()
    n = len(s)
    if n <= 32: return _h0_16(s, n) if n <= 16 else _h17_32(s, n)
    if n <= 64: return _h33_64(s, n)
    x = _f64(s, n - 40)
    y = (_f64(s, n - 16) + _f64(s, n - 56)) & M
    z = _h16((_f64(s, n - 48) + n) & M, _f64(s, n - 24))
    v = _weak_s(s, n - 64, n, z)
    w = _weak_s(s, n - 32, (y + K1) & M, x)
    x = (x * K1 + _f64(s, 0)) & M
    n2 = (n - 1) & ~63; i = 0
    while True:
        x = (_rot((x + y + v[0] + _f64(s, i + 8)) & M, 37) * K1) & M
        y = (_rot((y + v[1] + _f64(s, i + 48)) & M, 42) * K1) & M
        x ^= w[1]
        y = (y + v[0] + _f64(s, i + 40)) & M
        z = (_rot((z + w[0]) & M, 33) * K1) & M
        v = _weak_s(s, i, (v[1] * K1) & M, (x + w[0]) & M)
        w = _weak_s(s, i + 32, (z + w[1]) & M, (y + _f64(s, i + 16)) & M)
        z, x = x, z
        i += 64; n2 -= 64
        if n2 == 0: break
    return _h16((_h16(v[0], w[0]) + _sm(y) * K1 + z) & M, (_h16(v[1], w[1]) + x) & M)

def path_hash(p):
    return city64(p.strip('/').encode('utf-8'))
