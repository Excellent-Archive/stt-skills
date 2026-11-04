# Skill Hermes — SaptaTunas Use Case (v1.1)

| Skill | Use case |
|---|---|
| `stt-data-source` | Dasar: ambil data dari aplikasi internal (MCP / API Gateway), export WhatsApp (.txt), dan template laporan |
| `stt-email-triage` | Triage Email |
| `stt-document-creation` | Document Creation |
| `stt-helpdesk-response` | Helpdesk fast response |

Urutan sumber data: **MCP → API Gateway → file (WA .txt / template)**. Aplikasi internal dianggap sumber resmi, chat WA sebagai konteks tambahan.

## Instalasi (server care.saptatunas.com)
```bash
unzip saptatunas-skills.zip
cp -r saptatunas-skills/stt-* ~/.hermes/skills/
chmod +x ~/.hermes/skills/stt-data-source/scripts/*.py
pip install python-docx        # untuk template .docx (script API tidak butuh paket tambahan)

mkdir -p ~/stt-data/{whatsapp,templates,output}
cp ~/.hermes/skills/stt-data-source/sources.example.json ~/stt-data/sources.json
```
Atau upload tiap folder lewat menu **Skills** di workspace Anshin/Paperclip.

## Setup integrasi aplikasi internal

**API Gateway**
1. Edit `~/stt-data/sources.json`: ganti `base_url`, `path`, `items_path`, `pagination`, dan `map` sesuai API Sapta Tunas. Endpoint di contoh (`/crm/v1/customers`, `/helpdesk/v1/tickets`, `/pm/v1/projects/{project_id}/tasks`, `/dms/v1/templates`) hanya contoh.
2. Simpan token di environment agent, bukan di file JSON:
   ```bash
   echo 'STT_API_TOKEN=xxxxx' >> ~/.hermes/.env    # atau mekanisme secret Anshin
   ```
3. Cek: `python3 ~/.hermes/skills/stt-data-source/scripts/api_fetch.py tiket --raw` untuk melihat struktur respons asli, lalu sesuaikan `map`.

**MCP**
Daftarkan server MCP internal di config Hermes (contoh ada di `stt-data-source/SKILL.md`), restart gateway, lalu pastikan tool-nya muncul di agent. Bila ada tool MCP untuk data yang sama, agent akan memakainya lebih dulu daripada API.

## Hak tulis (write) yang dipakai skill
| Tindakan | Otomatis? |
|---|---|
| Membuat tiket baru, menambah catatan di tiket | Ya |
| Mengubah status / menutup tiket | Butuh persetujuan PIC |
| Mengirim email/balasan ke pelanggan via email | Butuh persetujuan (hanya draft) |
| Mengunggah dokumen ke aplikasi internal | Butuh persetujuan PM |

Ubah tabel ini di SKILL.md masing-masing bila SOP Sapta Tunas berbeda.

## Sebelum testing
- Isi tabel **Routing PIC** di `stt-email-triage/SKILL.md`.
- Sesuaikan nama file template di `stt-document-creation/SKILL.md`.
- Pastikan agent punya akses mailbox (MCP/API/IMAP) dan kanal Telegram/WhatsApp.

## Uji cepat
```bash
S=~/.hermes/skills/stt-data-source/scripts
python3 $S/api_fetch.py --list
python3 $S/api_fetch.py tiket --since 2026-11-01
python3 $S/parse_wa_export.py ~/stt-data/whatsapp/*.txt --stats
python3 $S/fill_template.py --list ~/stt-data/templates/<template>.docx
```
