"""Aster Extractor - cok basit arayuz (Tkinter)."""
import os, sys, threading, queue, traceback
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from .archive import LockedError, InvalidArchiveError
from .pipeline import convert
from . import __version__

BG, SIDE, SIDE_SEL, FG, MUTED, ACCENT, OK, ERR = '#17181c', '#101114', '#262932', '#e8e9ee', '#8b8f9c', '#4f8cff', '#3ecf8e', '#ff5d5d'

def desktop_dir():
    """Masaustu klasoru (OneDrive'a tasinmis olsa da bulunur)."""
    if sys.platform == 'win32':
        try:
            import ctypes
            buf = ctypes.c_wchar_p()
            # FOLDERID_Desktop = B4BFCC3A-DB2C-424C-B029-7FE99A87C641
            g = (ctypes.c_ubyte * 16)(*bytes.fromhex('3accbfb42cdb4c42b0297fe99a87c641'))
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(buf)) == 0 and buf.value:
                return buf.value
        except Exception: pass
    d = os.path.join(os.path.expanduser('~'), 'Desktop')
    if not os.path.isdir(d): os.makedirs(d, exist_ok=True)
    return d

def unique_path(d, stem):
    p = os.path.join(d, stem + '.zip'); n = 2
    while os.path.exists(p): p = os.path.join(d, '%s (%d).zip' % (stem, n)); n += 1
    return p

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Aster Extractor'); self.geometry('620x380'); self.minsize(560, 340); self.configure(bg=BG)
        self.mode = tk.StringVar(value='yeni'); self.q = queue.Queue(); self.busy = False
        side = tk.Frame(self, bg=SIDE, width=170); side.pack(side='left', fill='y'); side.pack_propagate(False)
        tk.Label(side, text='ASTER\nEXTRACTOR', bg=SIDE, fg=FG, font=('Segoe UI', 13, 'bold'), justify='left').pack(anchor='w', padx=18, pady=(22, 26))
        self.btn = {}
        for key, text in (('eski', 'Eski SCS'), ('yeni', 'Yeni SCS')):
            b = tk.Label(side, text=text, bg=SIDE, fg=FG, font=('Segoe UI', 11), anchor='w', padx=18, pady=10, cursor='hand2')
            b.pack(fill='x'); b.bind('<Button-1>', lambda e, k=key: self.set_mode(k)); self.btn[key] = b
        tk.Label(side, text='v' + __version__, bg=SIDE, fg=MUTED, font=('Segoe UI', 8)).pack(side='bottom', anchor='w', padx=18, pady=12)
        self.main = tk.Frame(self, bg=BG); self.main.pack(side='left', fill='both', expand=True, padx=34, pady=30)
        self.title_lbl = tk.Label(self.main, bg=BG, fg=FG, font=('Segoe UI', 17, 'bold'), anchor='w'); self.title_lbl.pack(fill='x')
        self.sub_lbl = tk.Label(self.main, bg=BG, fg=MUTED, font=('Segoe UI', 10), anchor='w', justify='left', wraplength=380); self.sub_lbl.pack(fill='x', pady=(6, 22))
        self.action = tk.Button(self.main, text='Dosya yükle', command=self.pick, bg=ACCENT, fg='white', activebackground='#6aa0ff', activeforeground='white',
                                relief='flat', font=('Segoe UI', 11, 'bold'), padx=22, pady=10, cursor='hand2', bd=0)
        self.action.pack(anchor='w')
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('A.Horizontal.TProgressbar', troughcolor=SIDE_SEL, background=ACCENT, bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT, thickness=8)
        self.bar = ttk.Progressbar(self.main, style='A.Horizontal.TProgressbar', mode='determinate', maximum=100)
        self.msg = tk.Label(self.main, bg=BG, fg=MUTED, font=('Segoe UI', 9), anchor='w'); 
        self.set_mode('yeni'); self.idle(); self.after(80, self.poll)

    def set_mode(self, k):
        self.mode.set(k)
        for key, b in self.btn.items(): b.configure(bg=SIDE_SEL if key == k else SIDE)
    # ---- ekranlar
    def _reset(self):
        self.bar.pack_forget(); self.msg.pack_forget(); self.action.pack_forget()
    def idle(self):
        self._reset(); self.busy = False
        self.title_lbl.configure(text='SCS dosyası seç', fg=FG)
        self.sub_lbl.configure(text='Modun .scs dosyasını yükle. İçindeki tüm 3B modeller (tekerlekler hariç) masaüstüne zip olarak kaydedilir.', fg=MUTED)
        self.action.configure(text='Dosya yükle', command=self.pick, state='normal'); self.action.pack(anchor='w')
    def working(self, name):
        self._reset(); self.busy = True
        self.title_lbl.configure(text='İşleminiz yapılıyor...', fg=FG)
        self.sub_lbl.configure(text='Lütfen bekleyiniz.\n' + name, fg=MUTED)
        self.bar['value'] = 0; self.bar.pack(fill='x', pady=(4, 8)); self.msg.configure(text=''); self.msg.pack(fill='x')
    def done(self, path, info):
        self._reset(); self.busy = False
        self.title_lbl.configure(text='İşleminiz gerçekleşti', fg=OK)
        self.sub_lbl.configure(text='Masaüstüne kaydedildi:\n%s\n\n%d model, %d doku.' % (os.path.basename(path), info['models'], info['textures']), fg=MUTED)
        self.action.configure(text='Yeniden dosya seç', command=self.pick, state='normal'); self.action.pack(anchor='w')
    def fail(self, title, detail=''):
        self._reset(); self.busy = False
        self.title_lbl.configure(text=title, fg=ERR); self.sub_lbl.configure(text=detail, fg=MUTED)
        self.action.configure(text='Yeniden dosya seç', command=self.pick, state='normal'); self.action.pack(anchor='w')
    # ---- is
    def pick(self):
        if self.busy: return
        p = filedialog.askopenfilename(title='SCS dosyası seç', filetypes=[('SCS mod dosyası', '*.scs'), ('Tüm dosyalar', '*.*')])
        if p: self.start(p)
    def start(self, path):
        out = unique_path(desktop_dir(), os.path.splitext(os.path.basename(path))[0])
        self.working(os.path.basename(path))
        threading.Thread(target=self._work, args=(path, out), daemon=True).start()
    def _work(self, path, out):
        try:
            info = convert(path, out, lambda f, m: self.q.put(('p', f, m)))
            self.q.put(('ok', out, info))
        except LockedError: self.q.put(('err', 'Dosya kilitli', 'Bu mod dosyası şifreli. Şifresi olmadan açılamaz.'))
        except InvalidArchiveError as e: self.q.put(('err', 'Dosya okunamadı', str(e)))
        except MemoryError: self.q.put(('err', 'Bellek yetmedi', 'Bu dosya için yeterli RAM yok.'))
        except Exception as e:
            self.q.put(('err', 'Bir hata oluştu', '%s: %s' % (type(e).__name__, e))); traceback.print_exc()
    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == 'p': self.bar['value'] = m[1] * 100; self.msg.configure(text=m[2])
                elif m[0] == 'ok': self.done(m[1], m[2])
                else: self.fail(m[1], m[2])
        except queue.Empty: pass
        self.after(80, self.poll)

def main():
    App().mainloop()
