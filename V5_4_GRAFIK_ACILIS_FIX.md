# V5.4 Grafik Açılış Fix

- Grafik artık `components.html` içinde CDN üzerinden JS indirmiyor.
- `streamlit-lightweight-charts-v5==0.2.0` Streamlit component'i kullanılıyor.
- Component frontend bundle'ı Python paketinin içinde gelir; CDN/iframe yükleme problemi kaldırıldı.
- VWAP ve tarama mantığı değiştirilmedi.
