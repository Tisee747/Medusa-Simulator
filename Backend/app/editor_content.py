"""Additional student guidance displayed in the editor.

The wording in this module is intentionally separate from evaluator logic. It
must not change test input, expected results, scoring, or animation behavior.
"""

from __future__ import annotations

from app.questions.registry import canonical_question_code


EDITOR_GUIDES: dict[str, dict[str, tuple[str, ...]]] = {
    "E01_TRAFFIC": {
        "steps": (
            "Bacalah warna lampu yang diberikan melalui input.",
            "Tentukan tindakan kendaraan sesuai warna lampu tersebut.",
            "Tampilkan satu jawaban dengan penulisan yang tepat.",
        ),
        "rules": (
            "MERAH berarti BERHENTI, KUNING berarti HATI_HATI, dan HIJAU berarti JALAN.",
            "Warna selain ketiga warna tersebut harus menghasilkan TIDAK_VALID.",
            "Jangan menampilkan kalimat penjelasan, hasil debug, atau baris tambahan.",
        ),
    },
    "E02_PARKING": {
        "steps": (
            "Bacalah jenis kendaraan dan lama parkirnya.",
            "Tentukan tarif per jam sesuai jenis kendaraan.",
            "Hitung dan tampilkan total biaya parkir.",
        ),
        "rules": (
            "Tarif MOTOR adalah 2000 per jam, MOBIL 5000 per jam, dan TRUK 8000 per jam.",
            "Hasil akhir harus berupa satu bilangan tanpa Rp atau tanda titik ribuan.",
        ),
    },
    "M01_PARKING_LOOP": {
        "steps": (
            "Bacalah data kendaraan berulang kali dengan perulangan while.",
            "Hitung biaya setiap kendaraan dan tambahkan ke jumlah keseluruhan.",
            "Hentikan perulangan ketika pengguna menulis SELESAI.",
        ),
        "rules": (
            "Tarif MOTOR adalah 2000 per jam, MOBIL 5000 per jam, dan TRUK 8000 per jam.",
            "SELESAI hanya menjadi tanda bahwa sesi telah berakhir dan tidak diikuti jumlah jam.",
            "Tampilkan total biaya satu kali setelah perulangan selesai.",
        ),
    },
    "M02_PACKAGE_SORT": {
        "steps": (
            "Bacalah seluruh berat paket yang diberikan.",
            "Urutkan berat paket dari nilai terkecil hingga terbesar di dalam fungsi urutkan_paket().",
            "Tampilkan hasil urutan tersebut dalam satu baris.",
        ),
        "rules": (
            "Semua data berat harus tetap ada, termasuk jika terdapat beberapa paket dengan berat yang sama.",
            "Jumlah angka pada hasil harus sama dengan jumlah data awal.",
        ),
    },
    "M03_PARKING_SESSION_TOTAL": {
        "steps": (
            "Bacalah kendaraan satu per satu sampai pengguna menulis SELESAI.",
            "Tampilkan jenis kendaraan dan biaya parkirnya pada setiap transaksi.",
            "Tampilkan TOTAL dan jumlah seluruh biaya pada baris terakhir.",
        ),
        "rules": (
            "Tarif MOTOR adalah 2000 per jam, MOBIL 5000 per jam, dan TRUK 8000 per jam.",
            "Urutan baris hasil harus sama dengan urutan kendaraan pada input.",
            "Jangan menambahkan baris kosong, hasil debug, atau kalimat lain.",
        ),
    },
    "M04_PACKAGE_DATA_ANALYSIS": {
        "steps": (
            "Bacalah setiap paket di dalam data.",
            "Hitung dan cari keenam informasi yang diminta pada soal.",
            "Kembalikan seluruh hasil dalam satu dictionary.",
        ),
        "rules": (
            "Jika dua paket memiliki berat terbesar yang sama, pilih paket yang muncul lebih dahulu.",
            "Daftar kategori harus diurutkan sesuai abjad dan tidak boleh berisi kategori yang sama lebih dari satu kali.",
            "Daftar lolos harus mengikuti urutan paket pada data awal.",
            "Jika package_dicari tidak ditemukan, isi ditemukan dengan TIDAK_ADA.",
        ),
    },
    "H01_RIVER_BFS": {
        "steps": (
            "Periksalah apakah keadaan di kedua sisi sungai tetap aman.",
            "Bentuk keadaan baru setelah satu penyeberangan.",
            "Gunakan BFS untuk mencoba perjalanan yang paling pendek terlebih dahulu.",
        ),
        "rules": (
            "Serigala tidak boleh ditinggal bersama domba tanpa gembala.",
            "Domba tidak boleh ditinggal bersama rumput tanpa gembala.",
            "Perahu hanya membawa gembala dan paling banyak satu penumpang.",
        ),
    },
    "H02_RIVER_RECURSION": {
        "steps": (
            "Periksa apakah keadaan saat ini sudah sama dengan tujuan.",
            "Coba satu penyeberangan yang aman.",
            "Panggil cari_jalur() kembali dari keadaan baru sampai tujuan tercapai.",
        ),
        "rules": (
            "Fungsi cari_jalur() harus benar-benar memanggil dirinya sendiri.",
            "Gunakan kondisi dasar agar pemanggilan rekursif dapat berhenti.",
            "Gunakan hanya token SENDIRI, SERIGALA, DOMBA, dan RUMPUT.",
        ),
    },
    "H03_RESCUE_PATH_CHECK": {
        "steps": (
            "Mulailah dari posisi start dan masukkan posisi tersebut ke visited_path.",
            "Ikuti setiap arah secara berurutan dan periksa posisi tujuan berikutnya.",
            "Hentikan perjalanan pada kejadian pertama, kemudian kembalikan hasilnya.",
        ),
        "rules": (
            "Robot berhenti ketika keluar dari papan, menabrak dinding, atau mencapai target.",
            "Posisi di luar papan dan posisi dinding tidak boleh dimasukkan ke visited_path.",
            "Jika semua arah telah dijalankan tetapi target belum tercapai, gunakan status BELUM_SAMPAI.",
        ),
    },
    "H04_RESCUE_BFS": {
        "steps": (
            "Masukkan posisi awal ke dalam antrean.",
            "Periksa posisi yang paling dekat terlebih dahulu dan simpan arah yang digunakan untuk mencapainya.",
            "Catat posisi yang sudah diperiksa agar tidak dimasukkan ke antrean berulang kali.",
        ),
        "rules": (
            "Rute harus aman dan memiliki jumlah langkah paling sedikit.",
            "Jangan menambahkan langkah setelah robot mencapai target.",
            "Kembalikan None hanya jika target benar-benar tidak dapat dicapai.",
        ),
    },
    "X01_RESCUE_RL": {
        "steps": (
            "Hitung Q-value baru dari pengalaman yang diperoleh robot.",
            "Gunakan epsilon untuk menentukan apakah robot mencoba tindakan acak.",
            "Jika tidak mencoba tindakan acak, pilih tindakan dengan Q-value terbesar.",
        ),
        "rules": (
            "Reward adalah nilai hadiah atau hukuman setelah robot melakukan tindakan.",
            "Alpha menentukan seberapa besar pengalaman baru memengaruhi nilai lama.",
            "Gamma menentukan seberapa penting perkiraan reward pada keadaan berikutnya.",
            "Epsilon menentukan peluang robot mencoba tindakan acak.",
        ),
    },
    "X02_RESCUE_BEST_ROUTE": {
        "steps": (
            "Periksa semua pilihan rute dari urutan pertama hingga terakhir.",
            "Abaikan rute yang tidak aman atau tidak mencapai target dengan tepat.",
            "Pilih rute aman dengan jumlah langkah paling sedikit.",
        ),
        "rules": (
            "Sebuah rute tidak dapat dipilih jika memiliki arah selain UP, DOWN, LEFT, atau RIGHT.",
            "Sebuah rute tidak dapat dipilih jika keluar dari papan, menabrak dinding, tidak mencapai target, atau masih bergerak setelah mencapai target.",
            "Jika dua rute sama pendek, pilih rute yang muncul lebih dahulu.",
            "Jangan mengubah isi maupun urutan candidates.",
        ),
    },
}


def get_editor_guide(question_code: str) -> dict[str, tuple[str, ...]]:
    return EDITOR_GUIDES.get(canonical_question_code(question_code), {"steps": (), "rules": ()})
