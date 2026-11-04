---
name: stt-helpdesk-response
description: Respons cepat helpdesk PT Sapta Tunas Teknologi — menjawab pertanyaan/keluhan pelanggan di WhatsApp/Telegram dalam hitungan menit, mengecek data pelanggan dan riwayat tiket di aplikasi internal (MCP/API Gateway), mencari solusi dari tiket dan chat WhatsApp yang pernah terselesaikan, membuat tiket, dan mengeskalasi ke teknisi bila perlu.
version: 1.1.0
author: PT Excellent Infotama Kreasindo
license: Proprietary
metadata:
  hermes:
    tags: [saptatunas, helpdesk, support, whatsapp, telegram, ticket]
    related_skills: [stt-data-source, stt-email-triage, stt-document-creation]
---

# STT Helpdesk Fast Response

Tujuan: pelanggan mendapat balasan pertama yang berguna dalam ≤ 5 menit, dan masalah yang sudah pernah terjadi bisa diselesaikan tanpa menunggu teknisi.

## Kapan dipakai
- Ada pesan masuk dari pelanggan di kanal helpdesk (WhatsApp/Telegram)
- Tim meminta "bantu jawab pertanyaan klien ini"
- Email yang diteruskan dari `stt-email-triage` berkategori INSIDEN/PERMINTAAN

## Langkah
1. **Pahami pesan**: siapa pelanggan, layanan apa, gejala apa, sejak kapan, berapa user terdampak. Pesan pertama pelanggan sering tidak lengkap; jangan tunggu lengkap untuk membalas.
2. **Kenali pelanggan** dari aplikasi internal (MCP bila tersedia, selain itu API Gateway). Langkah ini harus cepat; bila lebih dari ±30 detik atau gagal, lewati dan lanjut ke langkah 3.
   ```bash
   S=~/.hermes/skills/stt-data-source/scripts
   python3 $S/api_fetch.py pelanggan --param q="<nama/nomor/email pelanggan>" --timeout 15
   python3 $S/api_fetch.py tiket --param customer="<ID pelanggan>" --param status=open --timeout 15
   ```
   Dari sini didapat: level SLA, layanan yang dipakai, dan apakah sudah ada tiket terbuka untuk masalah yang sama.
3. **Buat tiket dan balas cepat (acknowledge)** dalam ≤ 5 menit, walaupun solusi belum ada.
   - Sudah ada tiket terbuka untuk masalah yang sama → pakai nomor itu, jangan buat duplikat.
   - Belum ada → buat tiket di aplikasi helpdesk (`buat_tiket` / tool MCP). Pembuatan tiket **boleh otomatis**:
     ```bash
     python3 $S/api_fetch.py buat_tiket --body tiket-baru.json --confirm
     ```
   - Aplikasi helpdesk tidak bisa diakses → pakai nomor sementara `STT-YYYYMMDD-NNN` dan catat untuk diinput belakangan.
4. **Cari kasus serupa**, mulai dari tiket yang sudah selesai di aplikasi internal (ada field solusi), lalu dari riwayat WhatsApp:
   ```bash
   python3 $S/api_fetch.py tiket --param status=closed --grep "<kata kunci gejala>" 
   python3 $S/parse_wa_export.py ~/stt-data/whatsapp/*.txt \
     --grep "<kata kunci gejala, mis. 'tidak bisa kirim|bounce|relay'>" --no-system --format jsonl
   ```
   Untuk WA, baca pesan di sekitar temuan (± 30 menit) untuk melihat **solusi yang benar-benar berhasil** (ada konfirmasi "sudah bisa", "aman", "berhasil", "terima kasih sudah normal"). Bila tersedia knowledge base/FAQ internal lewat MCP, cek juga.
5. **Tentukan jalur**:
   | Kondisi | Tindakan |
   |---|---|
   | Kasus serupa ditemukan + solusinya bisa dilakukan pelanggan sendiri (restart aplikasi, clear cache, cek password, setting di HP) | Berikan langkah solusi, maksimal 5 langkah |
   | Butuh akses server / perubahan konfigurasi / data pelanggan | Eskalasi ke teknisi, jangan beri perintah server ke pelanggan |
   | Banyak user / layanan produksi mati (P1) | Eskalasi segera ke PIC + kabari pelanggan bahwa tim sudah bergerak |
   | Tidak ada referensi, informasi kurang | Ajukan maks. 3 pertanyaan klarifikasi |
   | Di luar layanan Sapta Tunas | Sampaikan dengan sopan, arahkan ke pihak yang tepat |

   Prioritas mengikuti level SLA di CRM: pelanggan premium/kritis naik satu tingkat.
6. **Lengkapi tiket** dengan field: `no_tiket, waktu_masuk, pelanggan, kanal, kategori, prioritas, ringkasan, status, pic, waktu_respon_pertama, waktu_selesai, solusi`. Tambahan catatan ke tiket sendiri (`update_tiket`) boleh otomatis; **mengubah status atau menutup tiket butuh persetujuan teknisi/PIC**. Bila aplikasi tidak bisa diakses, simpan sementara di log/Task workspace. Data ini dipakai `stt-document-creation` untuk laporan helpdesk.
7. **Follow-up**: bila sudah ditangani, tanyakan konfirmasi ke pelanggan; tutup tiket hanya setelah pelanggan mengonfirmasi atau 1×24 jam tanpa balasan, dan setelah PIC menyetujui.

## Template balasan

**Acknowledge (balasan pertama)**
```
Halo Bapak/Ibu <nama>, terima kasih sudah menghubungi Helpdesk Sapta Tunas 🙏
Laporan Anda kami catat dengan nomor tiket *<nomor tiket>*.
Kami sedang mengecek masalah <ringkasan singkat>. Update berikutnya paling lambat <estimasi>.
```

**Solusi mandiri**
```
Untuk masalah <ringkasan>, silakan coba langkah berikut:
1. ...
2. ...
3. ...
Jika masih belum berhasil, mohon kirimkan screenshot pesan error-nya ya, Bapak/Ibu.
```

**Eskalasi**
```
Kasus ini perlu pengecekan langsung oleh teknisi kami. Tiket *STT-...* sudah kami teruskan
ke <tim/PIC> dan akan ditindaklanjuti paling lambat <estimasi>. Kami kabari kembali segera.
```

**Pesan eskalasi internal (ke grup teknisi)**
```
🚨 [P1/P2/P3] Tiket STT-20261104-007
Pelanggan: <nama/perusahaan> · Kanal: WhatsApp
Gejala: <ringkasan>
Sejak: <waktu> · Terdampak: <jumlah user/layanan>
Sudah dicoba: <langkah yang sudah dilakukan>
SLA pelanggan: <level dari CRM, bila ada>
Referensi kasus serupa: <nomor tiket lama / tanggal & grup WA, bila ada>
```

## Target waktu
| Prioritas | Respons pertama | Update berkala | Target selesai |
|---|---|---|---|
| P1 Kritis | ≤ 5 menit | tiap 30 menit | ≤ 4 jam |
| P2 Tinggi | ≤ 5 menit | tiap 2 jam | ≤ 1 hari kerja |
| P3 Normal | ≤ 15 menit | harian | ≤ 3 hari kerja |

## Aturan
- Gaya: ramah, sopan, ringkas; panggil "Bapak/Ibu"; hindari istilah teknis berlebihan.
- Jangan meminta pelanggan mengirim password atau OTP. Bila mereka mengirimnya, minta segera menggantinya.
- Jangan menjanjikan waktu yang lebih cepat dari tabel target.
- Jangan menjalankan perintah ke server klien dari skill ini; tindakan teknis lewat teknisi.
- Jangan menyebut nama atau masalah pelanggan lain saat mengutip kasus serupa.
- Data internal dari CRM/aplikasi (nilai kontrak, catatan internal, data pelanggan lain) tidak boleh disampaikan ke pelanggan.
- Lambatnya aplikasi internal tidak boleh menunda balasan pertama; balas dulu, lengkapi data sesudahnya.
