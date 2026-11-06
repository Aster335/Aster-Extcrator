"""Komut satirindan kullanim:  python -m aster_extractor.cli arac.scs cikti.zip"""
import sys
from .pipeline import convert
from .archive import LockedError, InvalidArchiveError

def main():
    if len(sys.argv) != 3: print(__doc__); return 2
    try:
        print(convert(sys.argv[1], sys.argv[2], lambda f, m: print('\r%3d%% %-40s' % (f * 100, m[:40]), end='', flush=True)))
    except LockedError: print('Dosya kilitli.'); return 1
    except InvalidArchiveError as e: print('Dosya okunamadi:', e); return 1
if __name__ == '__main__': sys.exit(main())
