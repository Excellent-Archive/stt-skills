---
name: stt-data-source
description: Mengambil dan menyatukan sumber data PT Sapta Tunas Teknologi — aplikasi internal (lewat MCP atau API Gateway), file export chat WhatsApp (.txt), dan file template laporan (.docx/.md) — menjadi data terstruktur. Dipakai sebagai langkah pertama oleh skill stt-email-triage, stt-document-creation, dan stt-helpdesk-response.
version: 1.1.0
author: PT Excellent Infotama Kreasindo
license: Proprietary
metadata:
  hermes:
    tags: [saptatunas, data-source, mcp, api-gateway, whatsapp, template]
    related_skills: [stt-email-triage, stt-document-creation, stt-helpdesk-response]
---

# STT Data Source

Skill dasar untuk tiga use case Sapta Tunas (Triage Email, Document Creation, Helpdesk Fast Response). Tugasnya mengambil data dari sumber yang tepat dan mengubahnya menjadi data terstruktur, **tanpa mengarang isi**.

## Jenis sumber dan urutan prioritas

| # | Sumber | Cara akses | Kapan dipakai |
|---|---|---|---|
| 1 | **Aplikasi internal via MCP** | Tool MCP yang terpasang di agent (mis. server `stt-internal`) | Pilihan utama bila tool-nya tersedia: data paling baru, akses sudah diatur |
| 2 | **Aplikasi internal via API Gateway** | `scripts/api_fetch.py` + `~/stt-data/sources.json` | Bila aplikasi belum punya MCP, atau tool MCP tidak menyediakan data yang dibutuhkan |
| 3 | **File export WhatsApp (.txt)** | `scripts/parse_wa_export.py` | Riwayat percakapan grup/klien yang tidak tercatat di aplikasi |
| 4 | **File template laporan** | `scripts/fill_template.py` | Format dokumen resmi (bisa juga diunduh dari aplikasi internal) |

Aturan memilih:
- Untuk data yang sama, **aplikasi internal (1–2) adalah sumber resmi**. Chat WhatsApp (3) dipakai sebagai konteks tambahan.
- Bila aplikasi dan chat saling bertentangan (mis. status tiket "closed" tapi pelanggan masih komplain di WA), **jangan pilih salah satu diam-diam**. Laporkan keduanya beserta sumbernya.
- Bila sumber 1 dan 2 gagal (error, timeout, tidak ada akses), lanjutkan dengan sumber file dan tulis jelas bahwa data aplikasi tidak bisa diambil.

## Bentuk data standar

Semua sumber dinormalisasi ke bentuk yang sama agar bisa digabung dan diurutkan:

```json
{
  "timestamp": "2026-11-03T10:30:00",
  "date": "2026-11-03",
  "time": "10:30",
  "sender": "nama pengirim / pelanggan / assignee",
  "text": "isi pesan / subjek tiket / judul task",
  "ref_id": "nomor tiket / id task (null untuk WA)",
  "status": "status di aplikasi (null untuk WA)",
  "url": "link ke aplikasi bila ada",
  "source": "api:tiket | mcp:stt-internal.list_tickets | grup-support.txt"
}
```
Field tambahan (mis. `prioritas`, `solusi`, `progres`) boleh ada. Saat mengambil dari MCP, petakan hasil tool ke bentuk ini juga dan isi `source` dengan `mcp:<server>.<tool>`.

## Lokasi file

| Isi | Lokasi default |
|---|---|
| Config sumber API | `~/stt-data/sources.json` (salin dari `sources.example.json`) |
| Export chat WhatsApp | `~/stt-data/whatsapp/*.txt` |
| Template laporan | `~/stt-data/templates/` |
| Hasil olahan | `~/stt-data/output/` |

---

## 1. Aplikasi internal via MCP

1. Lihat tool MCP yang tersedia di agent. Server internal Sapta Tunas didaftarkan di config Hermes, contoh:
   ```yaml
   # ~/.hermes/config.yaml (sesuaikan dengan format versi Hermes yang terpasang)
   mcp_servers:
     stt-internal:
       url: "https://mcp.saptatunas.com/mcp"
       headers:
         Authorization: "Bearer ${STT_MCP_TOKEN}"
   ```
2. Pilih tool yang sesuai kebutuhan (cari pelanggan, daftar tiket, task proyek, dsb.). Baca deskripsi tool dan isi parameter sesempit mungkin (rentang tanggal, ID proyek, status).
3. Tool yang **mengubah data** (membuat/mengubah/menghapus tiket, mengirim pesan, mengunggah dokumen) hanya dijalankan sesuai aturan write di bawah.
4. Simpan hasil yang sudah dinormalisasi ke `~/stt-data/output/<nama>.json` bila akan dipakai untuk dokumen.

## 2. Aplikasi internal via API Gateway

Endpoint didaftarkan di `~/stt-data/sources.json`. Token **tidak** ditulis di file, tapi di environment variable (mis. `STT_API_TOKEN`) yang dibaca script.

```bash
S=~/.hermes/skills/stt-data-source/scripts
python3 $S/api_fetch.py --list                                    # daftar sumber
python3 $S/api_fetch.py tiket --param status=open --since 2026-11-01
python3 $S/api_fetch.py tugas_proyek --param project_id=PRJ-019 --out ~/stt-data/output/task.json
python3 $S/api_fetch.py pelanggan --param q="Klien A" --raw       # respons mentah untuk cek field
```

Opsi: `--param nama=nilai` (query string atau pengisi `{placeholder}` di path), `--since/--until`, `--grep`, `--raw`, `--out`.

Menambah sumber baru: tambahkan entri di `sources`, isi `path`, `items_path` (lokasi array data dalam respons), `pagination` (`none | page | offset | cursor`), dan `map` (field standar → field di respons, pakai titik untuk field bertingkat seperti `customer.name`). Jalankan `--raw` dulu untuk melihat struktur respons.

### Operasi write (membuat/mengubah data)
Sumber dengan `"write": true` (mis. `buat_tiket`, `update_tiket`) berjalan sebagai **dry run** dulu:
```bash
python3 $S/api_fetch.py buat_tiket --body tiket.json            # tampilkan rencana, belum dikirim (exit 3)
python3 $S/api_fetch.py buat_tiket --body tiket.json --confirm  # benar-benar dikirim
```
`--confirm` hanya dipakai bila (a) user/PIC sudah menyetujui, atau (b) skill use case menyatakan tindakan itu boleh otomatis. Aturan yang sama berlaku untuk tool MCP yang mengubah data.

## 3. File export WhatsApp

```bash
python3 $S/parse_wa_export.py ~/stt-data/whatsapp/grup-support.txt \
  --since 2026-11-01 --until 2026-11-04 \
  --grep "error|gagal|down|tidak bisa" \
  --out ~/stt-data/output/wa-support.json
```
Opsi: `--since/--until`, `--sender`, `--grep`, `--no-system`, `--stats`, `--monthfirst`, `--format jsonl|json|csv`.

Aturan membaca chat:
- `<Media tidak disertakan>` / `image omitted` → `has_media`, jangan ditafsirkan.
- Pesan yang dihapus otomatis dibuang.
- Satu masalah bisa tersebar di banyak pesan. Kelompokkan berdasarkan topik dan waktu sebelum menyimpulkan.

## 4. Template laporan

Template bisa dari folder lokal atau dari aplikasi internal (sumber `template_laporan` / tool MCP DMS). Bila diunduh dari aplikasi, simpan dulu ke `~/stt-data/templates/`.

```bash
python3 $S/fill_template.py --list ~/stt-data/templates/laporan-mingguan.docx
python3 $S/fill_template.py ~/stt-data/templates/laporan-mingguan.docx \
  --data ~/stt-data/output/data-laporan.json \
  --out ~/stt-data/output/Laporan-Mingguan-2026-W45.docx
```
Placeholder ditulis `{{nama_field}}`. Field yang kosong menjadi `[PERLU KONFIRMASI: nama_field]` (exit 2). Nilai list ditulis sebagai baris berpoin.

## Menggabungkan sumber

Gabungkan file JSON hasil tiap sumber lalu urutkan per `timestamp`, misalnya:
```bash
jq -s 'add | sort_by(.timestamp)' ~/stt-data/output/tiket.json ~/stt-data/output/wa-support.json > ~/stt-data/output/gabungan.json
```

## Prinsip
1. Fakta hanya dari sumber data. Jika tidak ada, tulis `[PERLU KONFIRMASI]`.
2. Setiap temuan penting menyebut sumbernya: `(Helpdesk #T-1023)`, `(WA grup Support, 3 Nov 16.10)`.
3. Token, password, OTP, nomor HP, dan data pribadi tidak boleh muncul di laporan, rekap, atau balasan. Samarkan bila perlu (`08xx-xxxx-1234`).
4. Hanya ambil data yang dibutuhkan tugas saat ini. Jangan menarik seluruh database.
5. Tanggal ditulis format Indonesia: `4 November 2026`, jam `WIB`.
