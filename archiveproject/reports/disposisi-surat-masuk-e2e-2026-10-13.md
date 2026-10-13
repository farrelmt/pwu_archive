# Laporan uji alur surat masuk dan disposisi online Direksi

**Tanggal:** 13 Oktober 2026 (Asia/Jakarta)  
**Aplikasi:** Sistem Arsip PWU, modul Surat Masuk/Disposisi  
**Jenis uji:** Integrasi HTTP Django dari pembuatan surat masuk sampai status `SELESAI`  
**Kode uji:** `disposisi/test_workflow_e2e.py`  
**Hasil uji utama:** LULUS (1 skenario end-to-end)

## Tujuan dan cakupan

Membuktikan bahwa Sekretaris dapat membuat surat masuk yang ditujukan ke `DIREKSI`, memilih metode disposisi online, lalu meneruskan proses secara berurutan ke Direktur Utama, Sekretaris untuk peninjauan, Direktur, dua penerima tindak lanjut, dan akhirnya Sekretaris untuk persetujuan penyelesaian. Uji juga memastikan bahwa langkah berikutnya belum bisa dilakukan sebelum prasyaratnya terpenuhi.

Skenario menggunakan permintaan HTTP pada URL aplikasi melalui Django test client, lima akun uji dengan peran terpisah, surat PDF uji, dan basis data uji `test_pwu_archive_db`. Penyimpanan berkas dan email menggunakan backend dalam memori. Basis data aplikasi utama tidak menerima surat atau akun uji dari skenario ini. Kode yang diuji adalah working tree lokal pada tanggal laporan, termasuk perubahan yang belum di-commit; hasil ini belum membuktikan versi yang sedang dijalankan oleh server produksi.

## Data uji

| Objek | Nilai |
| --- | --- |
| Nomor surat | `E2E/DIREKSI/001` |
| Tujuan surat | `DIREKSI` |
| Metode | `ONLINE` |
| Pengunggah dan penyetuju akhir | Akun uji `sekretaris` |
| Pengisi arahan pertama | Akun uji `direktur_utama` |
| Pengisi arahan kedua | Akun uji `direktur_umum` |
| Penerima tindak lanjut | `kadiv_akuntansi`, `kadiv_keuangan` |
| Tenggat penerima | Tujuh hari setelah tanggal uji |

## Urutan dan hasil

| Langkah | Pelaku dan tindakan | Hasil yang diperiksa |
| --- | --- | --- |
| 1 | Sekretaris mengirim formulir surat masuk dengan dokumen PDF dan tujuan `DIREKSI` | Tercipta surat baru, dokumen tersimpan, halaman detail terbuka, status `DIBUAT` |
| 2 | Sekretaris memilih metode `ONLINE` | Jenis `ONLINE`, status `DIAJUKAN` |
| 3 | Direktur mencoba membuka editor sebelum giliran | HTTP 403; Direktur belum bisa mengisi |
| 4 | Sekretaris mencoba membagikan disposisi sebelum isi Direksi lengkap | Tetap `DIAJUKAN`; penerima belum terbentuk |
| 5 | Direktur Utama mengirim arahan dan tanda tangan digital | Arahan tersimpan di `isi_disposisi_dirut`, tanggal tanda tangan terisi, status masih `DIAJUKAN` |
| 6 | Direktur mencoba mengisi sebelum peninjauan Sekretaris | HTTP 403 |
| 7 | Sekretaris meninjau dan meneruskan arahan Direktur Utama | `dirut_reviewed_by` tercatat sebagai Sekretaris |
| 8 | Direktur mengirim arahan dan tanda tangan digital | Arahan tersimpan di `isi_disposisi_direktur`, tanggal tanda tangan terisi, status `DIISI`, isi Direksi dinyatakan lengkap |
| 9 | Sekretaris membagikan kepada Akuntansi dan Keuangan | Dua penerima terbentuk, status `DIBAGIKAN` |
| 10 | Sekretaris mencoba menyetujui selesai sebelum penerima bekerja | Tetap `DIBAGIKAN` |
| 11 | Akuntansi menerima, mengisi tindak lanjut, tenggat, dan hasil akhir | Waktu penerimaan dan penyelesaian, pelaku, dan hasil tersimpan; status tetap `DIBAGIKAN` karena Keuangan belum selesai |
| 12 | Keuangan menerima dan mengisi tindak lanjut, tenggat, dan hasil akhir | Data penerima tersimpan; status menjadi `VERIFIKASI` |
| 13 | Sekretaris menyetujui penyelesaian | Status `SELESAI`; halaman detail menampilkan tindakan `Batalkan Selesai` |
| 14 | Uji memeriksa jejak audit | Tepat dua log isi Direksi, dua log penerimaan, dua log aktivitas penerima, satu log penyelesaian oleh Sekretaris, dan satu activity log `COMPLETION_APPROVED` |

## Bukti eksekusi

Perintah uji utama:

```text
docker --context default compose run --rm --no-deps \
  -v /home/itpwu/pwu_archive/archiveproject:/app \
  -v /tmp/pwu_e2e_empty.env:/app/.env:ro \
  web python manage.py test disposisi.test_workflow_e2e --noinput -v 1
```

Hasil: `Ran 1 test in 3.078s` dan `OK`. Django melaporkan `System check identified no issues (0 silenced)`. Basis data uji dibuat dan dihapus oleh test runner.

Uji pertama berhasil melewati seluruh perubahan status dan pemeriksaan log, lalu gagal pada pemeriksaan teks halaman terakhir karena uji mengharapkan label model `Disposisi Telah Selesai`, sedangkan halaman menampilkan `Selesai`. Pemeriksaan uji disesuaikan dengan label antarmuka yang benar dan uji ulang lulus. Ini adalah koreksi pada uji, bukan perubahan pada kode aplikasi.

Suite regresi modul dijalankan dengan `python manage.py test disposisi --noinput -v 1` di container dan working tree yang sama. Hasil akhir: **74 tes, 291.052 detik, OK**; system check juga tanpa masalah. Pada pelaksanaan pertama, satu tes editor lama gagal karena masih mengharapkan teks tooltip dan nama variabel JavaScript dari antarmuka sebelumnya. Asersinya diperbarui agar memeriksa kontrol tanda tangan yang saat ini dirender. Tes tersebut lulus saat dijalankan sendiri, lalu seluruh 74 tes lulus pada pelaksanaan ulang. Tidak ada perubahan kode aplikasi untuk menyelesaikan kegagalan tes itu.

## Batasan

- Uji ini mencakup alur disposisi **online** ke kedua Direksi. Disposisi offline, penolakan, revisi arahan, pembatalan selesai, dan unduhan PDF tidak dijalankan dalam skenario end-to-end ini; beberapa di antaranya mempunyai uji terpisah pada suite disposisi.
- Interaksi diperiksa melalui Django test client, bukan browser nyata. Karena itu, perilaku JavaScript, tampilan responsif, serta pengiriman email ke alamat luar tidak dibuktikan oleh uji ini.
- Berkas sumber uji adalah PDF kecil sintetis yang lolos validasi unggahan aplikasi; isi PDF nyata dan kualitas hasil cetak tidak dinilai.
- `DIREKSI` pada aplikasi menjalankan urutan Direktur Utama → peninjauan Sekretaris → Direktur. “Menerima” setelah pembagian berlaku pada dua kepala divisi penerima tindak lanjut.
