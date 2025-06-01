# 📋 Panduan Penggunaan UI Faculty Finder

## 🔍 Overview

**UI Faculty Finder** adalah aplikasi web berbasis Python yang dirancang untuk melakukan crawling, penyimpanan, dan pencarian data dosen Universitas Indonesia secara otomatis dan interaktif.

### Fitur Utama
- **Web Crawling Otomatis**: Menggunakan algoritma BFS (Breadth-First Search) untuk mengumpulkan data dosen
- **Database Management**: Penyimpanan data terstruktur menggunakan SQLite
- **Search Engine**: Antarmuka web interaktif untuk pencarian data dosen
- **Real-time Access**: Akses langsung melalui web browser

---

## 📁 Struktur Proyek

```
ui_faculty-finder/
├── app.py                    # Entry point aplikasi utama
├── config.py                 # Konfigurasi crawling
├── requirements.txt          # Dependensi Python
├── crawler/                  # Modul Web Crawler
│   ├── bfs_crawler.py       # Implementasi algoritma BFS
│   └── url_utils.py         # Utility untuk URL processing
├── database/                 # Modul Database
│   ├── database.py          # Koneksi dan operasi SQLite
│   └── models.py            # Data models untuk dosen
├── search/                   # Modul Search Engine
│   ├── indexer.py           # Indexing untuk pencarian
│   └── search_engine.py     # Logic pencarian data
└── data/                     # Folder Database
    └── ui_faculty.db        # Database SQLite

```

---

## ⚙️ Persiapan Environment

### Prasyarat Sistem
- **Python**: Versi 3.7 atau lebih tinggi
- **Koneksi Internet**: Diperlukan untuk proses crawling
- **Web Browser**: Chrome, Firefox, Safari, atau Edge

### Verifikasi Python
```bash
python --version
# atau
python3 --version
```

### Instalasi Dependencies
```bash
# Navigasi ke direktori proyek
cd ui_faculty-finder

# Install semua dependensi
pip install -r requirements.txt
```

---

## 🚀 Menjalankan Aplikasi

### 1. Eksekusi Aplikasi
```bash
python app.py
```

### 2. Proses Otomatis yang Berjalan

#### Phase 1: Data Crawling
- Sistem akan memulai proses crawling menggunakan algoritma BFS
- Mengumpulkan data dosen dari website resmi Universitas Indonesia
- Progress akan ditampilkan di terminal

#### Phase 2: Database Operations
- Data hasil crawling disimpan ke database SQLite
- Struktur data dioptimalkan untuk pencarian cepat
- Database tersimpan di `data/ui_faculty.db`

#### Phase 3: Web Server Activation
- Flask web server akan aktif secara otomatis
- Aplikasi siap diakses melalui web browser

### 3. Akses Web Interface

Setelah melihat pesan berikut di terminal:
```
* Running on http://127.0.0.1:5000
* Debug mode: off
```

**Klik langsung pada link yang muncul** atau buka browser dan navigasi ke:
```
http://localhost:5000
```

---

## 🌐 Menggunakan Web Interface

### Fitur Pencarian
1. **Search Bar**: Masukkan nama dosen yang ingin dicari
2. **Filter Options**: Gunakan filter berdasarkan fakultas atau departemen
3. **Real-time Results**: Hasil pencarian muncul secara real-time
4. **Detail View**: Klik pada hasil untuk melihat informasi lengkap dosen

### Navigasi Web
- **Home**: Halaman utama pencarian
- **Browse**: Jelajahi semua data dosen
- **About**: Informasi tentang aplikasi
- **Statistics**: Statistik data yang tersimpan

---

## 🔧 Konfigurasi dan Customization

### Mengubah Port Server
Edit file `app.py` pada bagian:
```python
if __name__ == '__main__':
    app.run(debug=False, port=5000)  # Ubah port di sini
```

### Update Database
Untuk memperbarui data dosen:
```bash
# Hapus database lama (opsional)
rm data/ui_faculty.db

# Jalankan ulang aplikasi
python app.py
```

---

## 📊 Monitoring dan Logs

### Terminal Output
- **Crawling Progress**: Persentase dan jumlah data yang berhasil di-crawl
- **Database Status**: Konfirmasi penyimpanan data
- **Server Status**: Informasi web server dan port yang digunakan

### Log Files
Log aplikasi tersimpan di:
- Console output untuk real-time monitoring
- Error logs untuk troubleshooting

---

## 🛠️ Troubleshooting

| **Masalah** | **Solusi** |
|-------------|------------|
| **ModuleNotFoundError** | Jalankan `pip install -r requirements.txt` |
| **Port 5000 already in use** | Ubah port di `app.py` atau kill proses yang menggunakan port 5000 |
| **No data found** | Pastikan koneksi internet stabil selama crawling |
| **Database error** | Hapus file `data/ui_faculty.db` dan jalankan ulang aplikasi |
| **Web page not loading** | Periksa firewall atau antivirus yang mungkin memblokir localhost |

### Command Troubleshooting
```bash
# Cek port yang sedang digunakan
netstat -an | grep :5000

# Kill proses di port 5000 (MacOS/Linux)
lsof -ti:5000 | xargs kill -9

# Kill proses di port 5000 (Windows)
netstat -ano | findstr :5000
taskkill /PID <PID_NUMBER> /F
```

---

## 📋 Spesifikasi Teknis

### Technology Stack
- **Backend**: Python 3.x, Flask Framework
- **Database**: SQLite3
- **Frontend**: HTML5, CSS3, JavaScript
- **Crawling**: Custom BFS implementation with BeautifulSoup
- **Search**: Full-text search with indexing

### Performance
- **Crawling Speed**: ~50-100 pages per minute
- **Database Size**: ~10-50MB untuk data lengkap UI
- **Search Response**: <500ms untuk query sederhana
- **Memory Usage**: ~100-200MB during operation

---
