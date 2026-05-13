import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import datetime, timedelta

load_dotenv(dotenv_path="pass.env")
app = Flask(__name__)
app.secret_key = "maya_ozel_anahtar"

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
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_ID ASC")
    masalar = cursor.fetchall()
    simdi = datetime.now()
    bugun_bas = simdi.replace(hour=0, minute=0, second=0)
    bugun_bit = simdi.replace(hour=23, minute=59, second=59)
    cursor.execute("SELECT Masa_ID, Tarih FROM REZERVASYON WHERE Tarih BETWEEN %s AND %s", (bugun_bas, bugun_bit))
    gunluk_rezler = cursor.fetchall()
    for m in masalar:
        m['durum'] = 'bos'
        for r in gunluk_rezler:
            if r['Masa_ID'] == m['Masa_ID']:
                if simdi >= r['Tarih'] - timedelta(hours=1) and simdi <= r['Tarih'] + timedelta(hours=2):
                    m['durum'] = 'dolu'
                elif r['Tarih'] > simdi:
                    m['durum'] = 'rezerve'
    cursor.close()
    db.close()
    return render_template('index.html', masalar=masalar, sayfa='genel')

@app.route('/masalar')
def masalar_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_ID ASC")
    masalar = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('masalar.html', masalar=masalar, sayfa='masa')

@app.route('/musteriler')
def musteriler_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MUSTERI ORDER BY Musteri_ID DESC")
    musteriler = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('musteri.html', musteriler=musteriler, sayfa='musteri')

@app.route('/menu')
def menu_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM URUN ORDER BY Urun_Id ASC")
    urunler = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('menu.html', urunler=urunler, sayfa='menu')
@app.route('/siparisler')
def siparis_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    # Aktif siparişleri çek
    cursor.execute("SELECT s.*, m.Konum FROM SIPARIS s JOIN MASA m ON s.Masa_Id = m.Masa_Id")
    siparisler = cursor.fetchall()
    
    # Ürünleri (Menüyü) çek - HTML'deki seçim kutusu için
    cursor.execute("SELECT * FROM URUN ORDER BY Urun_Adi ASC")
    urunler = cursor.fetchall()
    
    cursor.close()
    db.close()
    return render_template('siparisler.html', siparisler=siparisler, urunler=urunler, sayfa='siparis')


@app.route('/rezervasyon_guncelle/<int:id>', methods=['POST'])
def rezervasyon_guncelle(id):
    yeni_tarih = request.form.get('tarih')
    yeni_saat = request.form.get('saat')
    yeni_masa = request.form.get('masa_id')
    tarih_saat_str = f"{yeni_tarih} {yeni_saat}:00"
    db = get_db()
    cursor = db.cursor()
    try:
        sql = "UPDATE REZERVASYON SET Tarih = %s, Masa_ID = %s WHERE Musteri_ID = %s"
        cursor.execute(sql, (tarih_saat_str, yeni_masa, id))
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('musteriler_listesi'))

@app.route('/musteri_sil/<int:id>', methods=['POST'])
def musteri_sil(id):
    db = get_db()
    cursor = db.cursor()
    try:
        # ÖNEMLİ: Önce REZERVASYON (bağımlı tablo) silinmeli
        cursor.execute("DELETE FROM REZERVASYON WHERE Musteri_ID = %s", (id,))
        # Sonra MUSTERI (ana tablo) silinmeli
        cursor.execute("DELETE FROM MUSTERI WHERE Musteri_ID = %s", (id,))
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        cursor.close()
        db.close()
    return redirect(url_for('musteriler_listesi'))
# Fiyatı Otomatik Hesaplayan Yardımcı Fonksiyon (Route değil, normal fonksiyon)
def adisyon_hesapla(siparis_id, db, cursor):
    sql_hesapla = """
        SELECT SUM(u.Fiyat * sd.Adet) as Toplam_Tutar
        FROM SIPARIS_DETAY sd
        JOIN URUN u ON sd.Urun_Id = u.Urun_Id
        WHERE sd.Siparis_Id = %s
    """
    cursor.execute(sql_hesapla, (siparis_id,))
    sonuc = cursor.fetchone()
    
    # Eğer ürün varsa Toplam_Tutar'ı al, yoksa 0 yap
    yeni_tutar = sonuc['Toplam_Tutar'] if sonuc['Toplam_Tutar'] else 0
    
    # Ana SIPARIS tablosundaki Tutar'ı güncelle
    cursor.execute("UPDATE SIPARIS SET Tutar = %s WHERE Siparis_Id = %s", (yeni_tutar, siparis_id))


# Arayüzden Ürün Eklediğimiz Rota
@app.route('/urune_ekle', methods=['POST'])
def urune_ekle():
    siparis_id = request.form.get('siparis_id')
    urun_id = request.form.get('urun_id')
    adet = int(request.form.get('adet', 1))
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # 1. Ürünü SIPARIS_DETAY tablosuna ekle
        cursor.execute("INSERT INTO SIPARIS_DETAY (Siparis_Id, Urun_Id, Adet) VALUES (%s, %s, %s)", (siparis_id, urun_id, adet))
        
        # 2. Toplam tutarı yeniden hesapla ve SIPARIS tablosunu güncelle
        adisyon_hesapla(siparis_id, db, cursor)
        
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        cursor.close()
        db.close()
        
    return redirect(url_for('siparis_listesi'))
if __name__ == '__main__':
    app.run(debug=True)