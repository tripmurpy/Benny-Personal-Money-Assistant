# Benny Cash AI Response Output Standard

Dokumen ini adalah sumber standar output AI Benny Cash di Telegram. Targetnya adalah personal finance assistant yang ringkas dan natural, bukan SQL reporting bot.

## Prinsip utama

Setiap respons mengikuti urutan:

```text
ANSWER FIRST -> CONTEXT -> OPTIONAL DETAIL -> ACTION
```

- Jawaban utama muncul paling awal.
- SQL, validasi, query database, dan proses internal tidak ditampilkan pada respons normal.
- Panjang dan struktur mengikuti intent user.
- Semua nominal, periode, jumlah, persentase, dan insight harus didukung data.
- Output tidak memakai emotikon sesuai aturan produk.

Format lama berikut dilarang:

```text
ANALISIS KEUANGAN

Pertanyaan:
...

Ringkasan:
...

Hasil:
...

Catatan:
...
```

## Arsitektur

```text
User Message
    -> Intent Understanding
    -> Generate SQL
    -> SQL Validation / Guardrail
    -> Database Snapshot
    -> SQL Result
    -> Response Formatter
    -> Structured Output
    -> Telegram Renderer
    -> Final Response
```

| Komponen | Tanggung jawab |
| --- | --- |
| AI | Memahami maksud user dan membuat SQL read-only. |
| SQL tool | Mengambil data secara aman dari snapshot milik user. |
| Response formatter | Memilih response type dan fakta penting dari hasil query. |
| Telegram renderer | Menentukan urutan visual, format Rupiah, bold, detail, dan pemotongan pesan. |

LLM tidak mengendalikan visual akhir. Formatter dan renderer aplikasi membentuk output secara deterministik.

## Structured output

Kontrak minimum:

```json
{
  "response_type": "financial_summary",
  "title": "Ringkasan Keuangan",
  "primary_value": 995670,
  "currency": "IDR",
  "details": []
}
```

Response type aktif:

| Response type | Digunakan untuk |
| --- | --- |
| `financial_summary` | Satu total atau metrik utama. |
| `transaction_list` | Daftar transaksi beserta nominal dan waktu. |
| `category_breakdown` | Beberapa kategori dan nominalnya. |
| `ranking` | Item atau kategori terbesar, tertinggi, atau terbanyak. |
| `comparison` | Perbandingan dua nilai atau periode. |
| `generic_answer` | Hasil finansial yang tidak cocok dengan tipe di atas. |

`trend`, `budget_status`, `financial_insight`, dan `goal_progress` baru boleh diaktifkan setelah query, data pembanding, serta renderer-nya benar-benar tersedia. Keberadaan nama response type bukan bukti fitur aktif.

Aturan field:

- `response_type` hanya memakai tipe yang didukung renderer.
- `title` menyatakan maksud jawaban tanpa mengulang pertanyaan user.
- `primary_value` memakai nilai mentah; renderer yang memformat Rupiah.
- Field tanpa dukungan data dikosongkan, bukan dikarang.
- Action button tidak ditampilkan sampai callback aplikasi tersedia.

## Hierarki visual

Urutan tampilan:

1. Judul singkat.
2. Jawaban atau angka utama.
3. Konteks pendukung.
4. Insight yang terbukti.
5. Detail bila dibutuhkan.
6. Action yang benar-benar tersedia.

Contoh summary:

```text
Ringkasan Keuangan

Rp995.670

3 transaksi pada Mei-Agustus 2026.
```

Contoh ranking:

```text
Pengeluaran Terbesar

Kategori: Makanan
Total pengeluaran: Rp842.500
```

Contoh transaction list:

```text
Daftar Transaksi

1. ChatGPT Plus
   Rp349.000
   15 Agustus 2026

2. ChatGPT Plus
   Rp349.000
   15 Juli 2026
```

Pertanyaan sederhana harus tetap singkat:

```text
Saldo Saat Ini

Rp2.898.000
```

## Aturan wajib

1. Jawab pertanyaan utama terlebih dahulu.
2. Buat angka utama mudah ditemukan.
3. Jangan mengulang pertanyaan user.
4. Jangan menjelaskan SQL kecuali diminta.
5. Jangan menyebut query read-only atau snapshot pada respons normal.
6. Jangan memakai heading `Pertanyaan`, `Ringkasan`, `Hasil`, dan `Catatan` sebagai template laporan.
7. Insight maksimal dua kalimat dan harus didukung data.
8. Format Rupiah konsisten, misalnya `Rp995.670`.
9. Gunakan bold Telegram hanya untuk informasi utama.
10. Respons sederhana tetap pendek; respons kompleks boleh memakai list, breakdown, ranking, atau comparison.
11. Jika data tidak cukup, katakan langsung bahwa data belum cukup.
12. Jangan menampilkan detail teknis backend.
13. Jangan menampilkan action yang belum didukung aplikasi.
14. Pesan panjang dipotong tanpa menghilangkan judul konteks pada lanjutan.

## Data tidak cukup

```text
Data Belum Ditemukan

Tidak ada transaksi yang cocok dengan permintaanmu.
```

Jangan mengganti data yang hilang dengan asumsi, estimasi, atau insight generik.

## Definition of done

Respons sesuai standar jika:

- jawaban utama terlihat pada bagian awal;
- response type sesuai intent dan bentuk data;
- tidak ada detail SQL atau proses backend pada respons normal;
- semua fakta dapat ditelusuri ke hasil database;
- renderer, bukan LLM, mengendalikan visual Telegram;
- output sederhana tetap pendek;
- output tidak memakai emotikon;
- user merasa berbicara dengan personal finance assistant, bukan membaca laporan query.
