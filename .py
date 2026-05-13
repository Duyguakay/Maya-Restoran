import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import datetime, timedelta

# .env veya pass.env dosyasını yükle
# Eğer dosya adın tam olarak 'pass.env' ise aşağıdaki satırı kullan:
load_dotenv(dotenv_path="pass.env")

app = Flask(__name__)
# Şifreleri ve gizli anahtarı dosyadan çekiyoruz
app.secret_key = os.getenv("SECRET_KEY", "varsayilan_anahtar")

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"), 
        database=os.getenv("DB_NAME", "RestoranDB")
    )

@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # 1. Tüm masaları 1'den 24'e kadar getir
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_ID ASC")
    masalar = cursor.fetchall()
    
    # 2. Bugünün rezervasyonlarını çek
    simdi = datetime.now()
    bugun_bas = simdi.replace(hour=0, minute=0, second=0, microsecond=0)
    bugun_bit = simdi.replace(hour=23, minute=59, second=59, microsecond=0)
    
    cursor.execute("""
        SELECT Masa_ID, Tarih FROM REZERVASYON 
        WHERE Tarih BETWEEN %s AND %s
    """, (bugun_bas, bugun_bit))
    gunluk_rezler = cursor.fetchall()

    # 3. Anlık Renk Hesaplama (Sarı, Yeşil, Gri)
    for m in masalar:
        m['durum'] = 'bos' # Varsayılan: Gri
        for r in gunluk_rezler:
            if r['Masa_ID'] == m['Masa_ID']:
                rez_vakti = r['Tarih']
                
                # DOLU (SARI): Rezervasyona 1 saat kaldıysa veya şu an içindeysek
                if simdi >= rez_vakti - timedelta(hours=1) and simdi <= rez_vakti + timedelta(hours=2):
                    m['durum'] = 'dolu'
                    break 
                
                # REZERVE (YEŞİL): Bugün daha ileri bir saatteyse
                elif rez_vakti > simdi:
                    m['durum'] = 'rezerve'
    
    cursor.close()
    db.close()
    return render_template('index.html', masalar=masalar, sayfa='genel')

@app.route('/musteriler')
def musteriler_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MUSTERI ORDER BY Musteri_ID DESC")
    tum_musteriler = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('musteri.html', musteriler=tum_musteriler, sayfa='musteri')

@app.route('/masalar')
def masalar_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_ID ASC")
    tum_masalar = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('masalar.html', masalar=tum_masalar, sayfa='masa')

@app.route('/rezervasyon-olustur', methods=['POST'])
def rezervasyon_olustur():
    ad = request.form.get('ad')
    soyad = request.form.get('soyad')
    telefon = request.form.get('telefon')
    tarih = request.form.get('tarih')
    saat = request.form.get('saat')
    kisi_sayisi = request.form.get('kisi_sayisi')
    masa_id = request.form.get('masa_id')

    # Tarih ve saati birleştir
    tarih_saat_str = f"{tarih} {saat}:00"
    yeni_rez_zamani = datetime.strptime(tarih_saat_str, '%Y-%m-%d %H:%M:%S')

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        # 5 SAAT KURALI KONTROLÜ
        baslangic = yeni_rez_zamani - timedelta(hours=5)
        bitis = yeni_rez_zamani + timedelta(hours=5)
        
        cursor.execute("""
            SELECT Tarih FROM REZERVASYON 
            WHERE Masa_ID = %s AND Tarih BETWEEN %s AND %s
        """, (masa_id, baslangic, bitis))
        
        if cursor.fetchone():
            flash("Dikkat: Bu masa için 5 saatlik zaman diliminde başka bir kayıt var!", "danger")
            return redirect(url_for('musteriler_listesi'))

        # Kayıt İşlemleri
        cursor.execute("INSERT INTO MUSTERI (Ad, Soyad, Telefon) VALUES (%s, %s, %s)", (ad, soyad, telefon))
        musteri_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO REZERVASYON (Tarih, Kisi_Sayisi, Musteri_ID, Masa_ID) 
            VALUES (%s, %s, %s, %s)
        """, (yeni_rez_zamani, kisi_sayisi, musteri_id, masa_id))
        
        db.commit()
        flash("Rezervasyon başarıyla oluşturuldu ve masanız ayrıldı!", "success")
        
    except Exception as e:
        db.rollback()
        flash(f"Sistem Hatası: {str(e)}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('musteriler_listesi'))

if __name__ == '__main__':
    app.run(debug=True)