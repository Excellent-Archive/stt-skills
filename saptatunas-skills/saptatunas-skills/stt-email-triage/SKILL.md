---
name: stt-email-triage
description: Triage email masuk PT Sapta Tunas Teknologi — klasifikasi kategori dan prioritas, cocokkan dengan data pelanggan dan tiket di aplikasi internal (MCP/API Gateway) serta riwayat chat WhatsApp, tentukan PIC, siapkan draft balasan, lalu kirim rekap ke Telegram. Gunakan saat diminta memeriksa inbox, merekap email, atau memilah email yang perlu ditindaklanjuti.
version: 1.1.0
author: PT Excellent Infotama Kreasindo
license: Proprietary
metadata:
  hermes:
    tags: [saptatunas, email, triage, zimbra, imap, telegram]
    related_skills: [stt-data-source, stt-helpdesk-response, stt-document-creation]
---

# STT Email Triage

Memilah email masuk agar tim Sapta Tunas langsung tahu mana yang harus dikerjakan dulu dan oleh siapa.

## Kapan dipakai
- "Cek email masuk hari ini", "rekap inbox", "ada email penting?"
- Jadwal rutin (routine/cron), mis. setiap pagi 08.00 WIB dan siang 13.00 WIB
- Saat ada email baru di mailbox support

## Input
Ambil data mengikuti urutan prioritas di skill `stt-data-source` (MCP → API Gateway → file).

1. **Email** yang belum dibaca atau sejak triage terakhir, dari salah satu:
   - tool MCP mail/aplikasi internal (bila tersedia), atau
   - endpoint mail di API Gateway (tambahkan di `sources.json` bila ada), atau
   - IMAP mailbox (Zimbra/mail server klien) lewat tool email agent.
   Jangan menandai email sebagai sudah dibaca kecuali diminta.
2. **Data pelanggan** dari aplikasi internal: cocokkan alamat/domain pengirim untuk mengetahui nama perusahaan, level SLA, dan account manager.
   ```bash
   S=~/.hermes/skills/stt-data-source/scripts
   python3 $S/api_fetch.py pelanggan --param q="<domain pengirim>"
   ```
3. **Tiket terbuka** milik pelanggan yang sama, untuk tahu apakah email ini lanjutan masalah lama:
   ```bash
   python3 $S/api_fetch.py tiket --param customer="<nama/ID pelanggan>" --param status=open
   ```
4. **Riwayat WhatsApp** sebagai konteks tambahan: apakah masalah yang sama sedang dibahas di grup WA.
   ```bash
   python3 $S/parse_wa_export.py ~/stt-data/whatsapp/*.txt \
     --since <7 hari terakhir> --grep "<nama klien|nama proyek|kata kunci subjek>"
   ```
   Bila aplikasi internal tidak bisa diakses, lanjutkan dengan email + WA saja dan beri catatan di rekap: "data CRM/tiket tidak tersedia".

## Langkah
1. **Baca** pengirim, subjek, isi, lampiran (nama file saja), dan thread sebelumnya. Kenali pelanggan dari data CRM.
2. **Klasifikasi kategori** (pilih satu):
   | Kategori | Contoh |
   |---|---|
   | `INSIDEN` | Sistem down, error, layanan tidak bisa diakses |
   | `PERMINTAAN` | Minta akses, instalasi, perubahan konfigurasi, data |
   | `PROYEK` | Update progres, jadwal, BAST, laporan proyek |
   | `KOMERSIAL` | Penawaran, PO, invoice, tagihan, kontrak |
   | `INFO` | Pemberitahuan, newsletter, notifikasi otomatis |
   | `SPAM/PHISHING` | Link mencurigakan, pengirim palsu, minta kredensial |
3. **Tentukan prioritas**:
   - `P1 Kritis` — layanan produksi klien mati / banyak user terdampak / ada kata "urgent", "down", "tidak bisa login semua". Target respons ≤ 15 menit.
   - `P2 Tinggi` — satu fungsi penting terganggu, ada tenggat ≤ 1 hari kerja. Target ≤ 1 jam.
   - `P3 Normal` — permintaan biasa, pertanyaan. Target ≤ 1 hari kerja.
   - `P4 Rendah` — INFO, FYI, newsletter. Tidak perlu balasan.
   Naikkan satu tingkat bila: (a) pelanggan berlevel SLA premium/kritis di CRM, atau (b) sudah ada tiket terbuka / keluhan WA untuk masalah yang sama yang belum selesai.
4. **Tentukan PIC**: pakai account manager dari CRM bila ada, selain itu pakai tabel routing di bawah.
5. **Hubungkan ke tiket** untuk INSIDEN dan PERMINTAAN:
   - Sudah ada tiket terbuka → cantumkan nomornya di rekap dan draft balasan.
   - Belum ada → buat tiket baru lewat `buat_tiket` (API) atau tool MCP helpdesk. Pembuatan tiket **boleh otomatis** (pencatatan internal). Mengubah status atau menutup tiket tetap butuh persetujuan.
6. **Siapkan draft balasan** untuk P1–P3 (lihat format). **Jangan kirim email otomatis**; draft menunggu persetujuan manusia.
7. **Kirim rekap** ke Telegram/WhatsApp tim sesuai format.

## Routing PIC (isi sesuai struktur Sapta Tunas)
| Kategori | PIC | Kanal eskalasi |
|---|---|---|
| INSIDEN | `[Nama PIC Support]` | Telegram grup Support |
| PERMINTAAN | `[Nama PIC Helpdesk]` | Telegram grup Support |
| PROYEK | `[Nama PM]` | Telegram grup PM |
| KOMERSIAL | `[Nama PIC Sales/Finance]` | Telegram pribadi |
| SPAM/PHISHING | `[Admin IT]` | Laporkan, jangan klik link |

## Format rekap (Telegram)
```
📬 Rekap Email — Rabu, 4 November 2026 08.00 WIB
Total: 12 | P1: 1 | P2: 3 | P3: 5 | P4: 3

🔴 P1 — INSIDEN
1. [Klien A · SLA Premium] Email server tidak bisa kirim keluar
   Dari: budi@klienA.co.id · 07.42
   Tiket: STT-20261104-003 (baru dibuat) · terkait #T-1019 (open sejak 1 Nov)
   Konteks WA: dikeluhkan juga di grup "Support Klien A" 3 Nov 16.10
   PIC: [Nama] · Draft balasan: siap ✅

🟠 P2 — ...
🟡 P3 — ...
⚪ P4 — 3 email info (tanpa tindakan)
⚠️ Dicurigai phishing: 1 (lihat detail)
```

## Format draft balasan
```
Subjek: Re: <subjek asli> [Tiket STT-YYYYMMDD-NNN]

Yth. Bapak/Ibu <nama>,

Terima kasih atas informasinya. Kami sudah menerima laporan terkait <ringkasan 1 kalimat>
dan saat ini sedang ditangani oleh tim <tim>. Kami akan memberikan update
paling lambat <estimasi sesuai prioritas>.

<Pertanyaan klarifikasi bila data kurang, maks. 3 poin>

Salam,
Tim Support PT Sapta Tunas Teknologi
```

## Aturan
- Jangan pernah membalas, meneruskan, atau menghapus email tanpa persetujuan.
- Data dari aplikasi internal (kontrak, nilai tagihan, catatan internal pelanggan) hanya untuk rekap internal, tidak dimasukkan ke draft balasan ke pelanggan.
- Jangan membuka link atau lampiran dari email berkategori SPAM/PHISHING.
- Jangan menyalin password, OTP, atau data pribadi ke rekap Telegram.
- Bila ragu antara dua kategori/prioritas, pilih yang lebih tinggi dan beri catatan "perlu cek".
- Email yang butuh dokumen (laporan, BAST, berita acara) → sarankan memakai skill `stt-document-creation`.
