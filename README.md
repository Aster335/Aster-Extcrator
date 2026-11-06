# Aster Extractor

Euro Truck Simulator 2 / American Truck Simulator `.scs` mod dosyalarındaki 3B modelleri **GLB**, **OBJ** ve **PNG** olarak çıkaran, çok basit arayüzlü Windows uygulaması.

## Kullanım
1. Uygulamayı aç.
2. **Dosya yükle** ile `.scs` dosyasını seç.
3. Dosya şifreliyse **"Dosya kilitli"** hatası görürsün, işlem durur.
4. Değilse işlem başlar. Bitince masaüstünde `.scs` ile aynı adda bir zip oluşur:

```
arac.zip
├── arac.glb          tüm modeller tek dosyada
├── obj/              her model için .obj + .mtl
└── textures/         PNG dokular
```

Dosyadaki tüm 3B modeller çevrilir. **Tekerlekler atlanır** (dosya adında `wheel`, `lastik`, `jant`, `tire`, `rim`, `hub` geçenler; adı gizlenmiş modlarda yuvarlak/disk biçimli modeller).

## Desteklenenler
- Düz zip tabanlı `.scs` (bozuk yerel başlıklı olanlar dahil)
- Hash tabanlı `.scs` (`SCS#`, sürüm 1)
- PMG model sürümleri 0x10, 0x13, 0x14, 0x15
- Şifreli zip → "Dosya kilitli" (şifre kırılmaz)

Sol paneldeki **Eski SCS / Yeni SCS** seçimi bilgi amaçlıdır; dosya türü otomatik algılanır.

## Kaynaktan çalıştırma
```
pip install -r requirements.txt
python main.py
```
Komut satırı: `python -m aster_extractor.cli arac.scs cikti.zip`

## .exe üretme
GitHub'da **Actions → Windows exe → Run workflow** çalıştır; bittiğinde `AsterExtractor-windows` çıktısından `AsterExtractor.exe` indirilir.
Elle: `pip install pyinstaller` ve `pyinstaller --onefile --windowed --name AsterExtractor main.py`

## Notlar
- Büyük modlarda (yüzlerce MB) işlem birkaç dakika sürebilir ve RAM kullanır.
- Dokular en fazla 2048 piksele küçültülür.
- Gövde boyası gibi oyunda renkle verilen yüzeyler beyaz görünebilir; modelin kendi dokusu yoksa bu normaldir.
