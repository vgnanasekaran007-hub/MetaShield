<div align="center">

# 🛡️ MetaShield

### Image Metadata Analyzer & Editor

**Analyze · Edit · Compare · Remove** hidden metadata from images — securely and privately.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-38BDF8?style=for-the-badge)]()

> A production-ready cybersecurity web application for digital forensics professionals, privacy-conscious users, and software developers.

</div>

---

## 📸 Screenshots

| Landing Page | Dashboard |
|:---:|:---:|
| ![Landing](https://raw.githubusercontent.com/vgnanasekaran007-hub/MetaShield/main/docs/landing.png) | ![Dashboard](https://raw.githubusercontent.com/vgnanasekaran007-hub/MetaShield/main/docs/dashboard.png) |

| Compare | History & Analytics |
|:---:|:---:|
| ![Compare](https://raw.githubusercontent.com/vgnanasekaran007-hub/MetaShield/main/docs/compare.png) | ![History](https://raw.githubusercontent.com/vgnanasekaran007-hub/MetaShield/main/docs/history.png) |

---

## ✨ Features

### 🔍 Metadata Analysis
- Extract **50+ EXIF fields** – camera model, lens, ISO, aperture, exposure, white balance, flash, focal length
- **GPS location** extraction with Leaflet.js interactive map + Google Maps link
- XMP, IPTC, ICC Profile, embedded thumbnail detection
- Raw EXIF tag viewer with all unknown tags

### ✏️ Metadata Editor
- Edit **Author, Copyright, Description, Software, Keywords, Title, Artist, Comment**
- Supports DateTime, UserComment, Windows XP metadata fields
- Downloads modified image instantly — original untouched

### 🧹 Metadata Cleaner
- Selectively remove: **EXIF · GPS · IPTC · XMP · Comments · Thumbnail · ICC Profile**
- Or **Remove All** metadata with one click
- Configurable JPEG/WebP output quality
- **Batch processing** — clean multiple images, download as ZIP

### 🔀 Side-by-Side Compare
- Upload two images and view a **color-coded diff**
- Status labels: `CHANGED` · `ADDED` · `REMOVED` · `SAME`
- Search and filter by diff status

### 📊 Visual Tools
- **RGB Histogram** — Chart.js visualization of channel distribution
- **Color Palette** — Extract 8 dominant colors via median-cut; click any swatch to copy hex
- **Image preview** with zoom (fullscreen), rotate, and download

### 📦 Export
- **JSON** — complete metadata as pretty-printed JSON
- **CSV** — two-column key/value spreadsheet
- **TXT** — formatted text report
- **PDF** — professionally styled report via ReportLab

### 📜 History & Analytics
- Every operation logged in **SQLite** (auto-created)
- Operations breakdown (pie chart)
- Daily uploads for last 14 days (line chart)
- Format distribution (donut chart)
- Search, filter, paginate history; delete individual records

### 🎨 UI/UX
- **Glassmorphism dark/light theme** with system preference respect
- Animated hero page with floating cards and scan-line effect
- Skeleton loading states, AOS scroll animations
- Toast notifications, SweetAlert2 confirmation dialogs
- Floating Action Button, ripple effects on buttons
- Fully **responsive** — desktop, tablet, mobile

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **pip**

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/vgnanasekaran007-hub/MetaShield.git
cd MetaShield

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the application
python app.py
```

### 🌐 Open in Browser

```
http://127.0.0.1:5000
```

> The SQLite database and upload/download folders are created automatically on first run.

---

## 📁 Project Structure

```
MetaShield/
├── app.py                      ← Flask application & all API routes
├── config.py                   ← Configuration constants
├── requirements.txt            ← Python dependencies
│
├── utils/
│   ├── metadata.py             ← EXIF extraction (Pillow + piexif + exifread)
│   ├── cleaner.py              ← Metadata removal (selective & batch)
│   ├── editor.py               ← Metadata field editing (piexif)
│   ├── compare.py              ← Side-by-side metadata diff
│   └── export.py               ← JSON / CSV / TXT / PDF export (ReportLab)
│
├── templates/
│   ├── index.html              ← Animated landing page
│   ├── dashboard.html          ← Main application (upload, view, edit, clean)
│   ├── compare.html            ← Two-image metadata comparison
│   └── history.html            ← History & analytics dashboard
│
└── static/
    ├── css/style.css           ← Full custom CSS (glassmorphism, dark/light)
    ├── js/app.js               ← Complete frontend JavaScript
    ├── uploads/                ← Uploaded images (runtime, not committed)
    └── downloads/              ← Processed outputs (runtime, not committed)
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload one or more images; returns metadata |
| `GET`  | `/metadata/<filename>` | Full metadata for an uploaded file |
| `POST` | `/edit` | Edit EXIF fields; returns download link |
| `POST` | `/remove` | Strip metadata (selective or all) |
| `POST` | `/batch_remove` | Batch clean multiple files → ZIP |
| `POST` | `/compare_meta` | Compare two images; returns diff |
| `GET`  | `/api/history` | Paginated history (JSON) |
| `GET`  | `/download/<filename>` | Download processed file |
| `GET`  | `/download_zip/<filename>` | Download batch ZIP |
| `POST` | `/delete/<id>` | Delete history record |
| `GET`  | `/export/<filename>/<fmt>` | Export metadata as `json/csv/txt/pdf` |
| `GET`  | `/analytics` | Chart data for history page |
| `GET`  | `/preview/<filename>` | Serve image preview |

### Example: Upload & get metadata
```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@photo.jpg"
```

### Example: Remove GPS only
```bash
curl -X POST http://localhost:5000/remove \
  -H "Content-Type: application/json" \
  -d '{"filename": "abc123.jpg", "options": ["gps"], "quality": 95}'
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + U` | Go to Upload section |
| `Ctrl + M` | Go to Metadata section |
| `Ctrl + E` | Go to Edit Metadata |
| `Ctrl + D` | Go to Clean Metadata |
| `Ctrl + B` | Toggle sidebar |
| `Ctrl + T` | Toggle dark / light theme |
| `F` | Fullscreen image preview |
| `Esc` | Close fullscreen |

---

## 🛡️ Security

| Feature | Detail |
|---------|--------|
| File validation | Extension allowlist: `jpg jpeg png tiff webp` |
| Size limit | 20 MB maximum per file |
| Filename sanitisation | `secure_filename()` + regex strip |
| Path traversal prevention | All filenames sanitised before disk operations |
| Rate limiting | 30 uploads / hour per IP (in-memory) |
| Local processing | No data ever sent to external servers |

---

## 🧩 Tech Stack

### Backend
| Library | Purpose |
|---------|---------|
| Flask 3.1 | Web framework |
| Pillow 11 | Image I/O, EXIF, histogram, color palette |
| piexif 1.1 | Structured EXIF read/write/edit |
| exifread 3.0 | Extended raw tag extraction |
| ReportLab 4.2 | PDF report generation |
| SQLite (stdlib) | Upload history persistence |

### Frontend
| Library | Purpose |
|---------|---------|
| Bootstrap 5.3 | Responsive grid & components |
| Chart.js 4.4 | Histogram, pie, line, donut charts |
| Leaflet.js 1.9 | Interactive GPS map |
| SweetAlert2 11 | Confirmation dialogs |
| AOS 2.3 | Scroll animations |
| Font Awesome 6 | Icons |
| Poppins + JetBrains Mono | Typography |

---

## 🗺️ Roadmap

- [ ] Steganography scanner
- [ ] Hidden text detector
- [ ] Duplicate image detection (perceptual hash)
- [ ] Metadata integrity checker
- [ ] Fake metadata detection
- [ ] QR code metadata export
- [ ] User authentication
- [ ] Docker deployment

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

## 👤 Author

**vgnanasekaran007**  
GitHub: [@vgnanasekaran007-hub](https://github.com/vgnanasekaran007-hub)

---

<div align="center">

Made with ❤️ using Flask · Pillow · Bootstrap 5

⭐ **Star this repo** if you found it useful!

</div>
