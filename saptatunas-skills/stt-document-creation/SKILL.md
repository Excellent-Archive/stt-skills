---
name: stt-document-creation
description: Membuat dokumen/laporan PT Sapta Tunas Teknologi (laporan harian/mingguan proyek, laporan helpdesk, berita acara, notulen) dengan mengisi file template laporan memakai data dari aplikasi internal (MCP/API Gateway — task proyek, tiket helpdesk) dan export chat WhatsApp. Gunakan saat diminta "buatkan laporan", "isi template", atau merangkum data/chat menjadi dokumen.
version: 1.1.0
author: PT Excellent Infotama Kreasindo
license: Proprietary
metadata:
  hermes:
    tags: [saptatunas, document, report, template, whatsapp, docx]
    related_skills: [stt-data-source, stt-email-triage, stt-helpdesk-response]
---

# STT Document Creation

Mengubah data aplikasi internal dan percakapan WhatsApp tim/klien menjadi laporan rapi sesuai template resmi Sapta Tunas.

## Kapan dipakai
- "Buatkan laporan mingguan proyek X dari chat WA"
- "Isi template laporan helpdesk bulan Oktober"
- "Buat berita acara / notulen dari diskusi di grup"
- Jadwal rutin, mis. setiap Jumat 16.00 WIB untuk laporan mingguan

## Jenis dokumen, template, dan sumber data
Template disimpan di `~/stt-data/templates/` atau diambil dari aplikasi internal (sumber `template_laporan` / tool MCP DMS). Sesuaikan nama file dengan template asli Sapta Tunas:

| Dokumen | File template | Sumber utama (aplikasi internal) | Sumber pelengkap (WA) |
|---|---|---|---|
| Laporan Harian/Mingguan Proyek | `laporan-proyek.docx` | Task proyek: `tugas_proyek` | Grup WA proyek |
| Laporan Helpdesk/Support | `laporan-helpdesk.docx` | Tiket: `tiket` | Grup WA support klien |
| Berita Acara (BA/BAST) | `berita-acara.docx` | Task berstatus selesai + data pelanggan | Chat konfirmasi pekerjaan selesai |
| Notulen Rapat | `notulen.docx` | (kalender/rapat bila ada di MCP) | Chat/rangkuman rapat |

Contoh template teks ada di `templates/contoh-laporan-proyek.md` sebagai acuan nama field.

## Langkah
1. **Pastikan parameter**: jenis dokumen, nama proyek/klien (dan ID proyek di aplikasi bila ada), periode (tanggal mulai–akhir), serta grup WA yang relevan. Bila salah satu tidak jelas, tanyakan satu kali sebelum mulai.
2. **Siapkan template**. Bila template resmi ada di aplikasi internal, ambil versi terbaru dulu:
   ```bash
   S=~/.hermes/skills/stt-data-source/scripts
   python3 $S/api_fetch.py template_laporan --grep "laporan proyek"   # dapatkan download_url, lalu unduh ke ~/stt-data/templates/
   python3 $S/fill_template.py --list ~/stt-data/templates/laporan-proyek.docx
   ```
3. **Ambil data dari aplikasi internal** (MCP bila tersedia, selain itu API Gateway):
   ```bash
   python3 $S/api_fetch.py tugas_proyek --param project_id=PRJ-019 \
     --since 2026-10-28 --until 2026-11-03 --out ~/stt-data/output/task-proyek-x.json
   # untuk laporan helpdesk:
   python3 $S/api_fetch.py tiket --param customer="Klien A" \
     --since 2026-10-01 --until 2026-10-31 --out ~/stt-data/output/tiket-oktober.json
   ```
   Dari data ini ambil angka yang pasti: jumlah task selesai/berjalan, persentase progres, jumlah tiket per status/prioritas, rata-rata waktu respons.
4. **Ambil data chat** sebagai pelengkap (konteks, kendala, keputusan yang tidak tercatat di aplikasi):
   ```bash
   python3 $S/parse_wa_export.py ~/stt-data/whatsapp/grup-proyek-x.txt \
     --since 2026-10-28 --until 2026-11-03 --no-system --out ~/stt-data/output/chat-proyek-x.json
   ```
5. **Gabungkan dan ekstrak isi**, kelompokkan per topik. Angka dan status mengikuti aplikasi internal. Bila chat menyebut hal yang bertentangan (mis. task "done" di aplikasi tapi di WA masih ada kendala), cantumkan di bagian Kendala/Catatan dengan kedua sumbernya.
   - Pekerjaan selesai (ada kata: selesai, done, sudah, beres, aman, OK, berhasil)
   - Pekerjaan berjalan / progres (sedang, proses, on progress, lanjut)
   - Kendala/isu (error, gagal, kendala, belum bisa, tertunda)
   - Rencana berikutnya (besok, minggu depan, akan, rencana, jadwal)
   - Keputusan & persetujuan (setuju, approve, ACC, deal, oke lanjut)
   - Permintaan klien
   Setiap poin: kalimat ringkas + sumber, mis. `(Task #412)` atau `(WA, 30 Okt 14.05, Nama)`.
6. **Susun JSON data** dengan kunci sama persis dengan field template. Contoh:
   ```json
   {
     "nama_proyek": "Implementasi Mail Server Klien A",
     "periode": "28 Oktober – 3 November 2026",
     "tanggal_laporan": "4 November 2026",
     "disusun_oleh": "Hermes Agent – Tim STT",
     "ringkasan": "Instalasi selesai 90%, tersisa migrasi mailbox divisi Finance.",
     "pekerjaan_selesai": ["Instalasi server (29 Okt)", "Konfigurasi DNS & SPF (30 Okt)"],
     "pekerjaan_berjalan": ["Migrasi mailbox Finance (60%)"],
     "kendala": ["Akses VPN klien terputus 31 Okt, sudah normal 1 Nov"],
     "rencana_berikutnya": ["Migrasi Finance 5 Nov", "UAT 7 Nov"],
     "catatan": ""
   }
   ```
7. **Isi template**:
   ```bash
   python3 ~/.hermes/skills/stt-data-source/scripts/fill_template.py ~/stt-data/templates/laporan-proyek.docx \
     --data ~/stt-data/output/data-laporan.json \
     --out "~/stt-data/output/Laporan-Proyek-KlienA-2026-W45.docx"
   ```
   Exit code `2` berarti ada field `[PERLU KONFIRMASI]`.
8. **Serahkan** dokumen ke user beserta:
   - daftar field yang masih perlu konfirmasi,
   - 3–5 poin ringkasan isi,
   - sumber yang dipakai (aplikasi/endpoint dan grup WA) serta sumber yang gagal diakses,
   - catatan bila ada info yang saling bertentangan.
9. **Unggah ke aplikasi internal** (DMS/proyek) hanya bila diminta dan setelah PM menyetujui isi dokumen, lewat tool MCP atau sumber API bertipe write dengan `--confirm`.

## Gaya penulisan
- Bahasa Indonesia baku, kalimat pendek, tanpa bahasa chat ("udh", "gpp", "wkwk").
- Ubah percakapan jadi kalimat pasif/netral: "Konfigurasi DNS telah diselesaikan pada 30 Oktober 2026."
- Angka dan tanggal konsisten; persentase hanya jika disebut di chat.
- Nama file output: `<Jenis>-<Klien/Proyek>-<Periode>.docx`, tanpa spasi.

## Aturan
- Jangan mengarang progres, angka, atau persetujuan yang tidak ada di sumber data.
- Laporan untuk klien tidak boleh memuat data internal (catatan internal, nilai kontrak, data pelanggan lain).
- Jangan menyalin nomor HP, password, atau data pribadi dari chat ke dokumen.
- Dokumen resmi (BA/BAST, laporan ke klien) selalu berstatus **DRAFT** sampai disetujui PM.
- Jangan mengubah file template asli; selalu tulis ke `~/stt-data/output/`.
