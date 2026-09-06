# V6.2 Hızlı Tarama Motoru

Tarama/formasyon kuralları değiştirilmeden veri katmanı hızlandırıldı.

## Değişiklikler
- Aynı Python süreci içinde günlük ve intraday veriler RAM cache ile tekrar kullanılır.
- Üçgen 4h için çekilmiş 60m/1y veri, aynı çalışmadaki Düşen Trend 1h/6mo taramasında yeniden Yahoo'dan çekilmez; gerekli son 6 aylık bölüme kırpılarak kullanılır.
- GitHub Actions ilk gerçek taramada `veri_onbellek` klasörünü Türkiye tarihi anahtarıyla cache'e kaydeder.
- Aynı gün sonraki otomatik taramalarda günlük/MAX geçmişler GitHub cache'ten gelir; tekrar tam geçmiş indirme azalır.
- Piyasa cache'i yalnız gerçek tarama yapıldığında kaydedilir; 5 dakikalık saat kontrolleri büyük cache üretmez.
- `auto_scan.py` her fazın süresini loga yazar.

## GitHub'a yüklenecek dosyalar
1. `vwap_core.py`
2. `auto_scan.py`
3. `.github/workflows/bist-auto-scan.yml`

`app.py`, Telegram secrets ve site ayar merkezi değişmez.
