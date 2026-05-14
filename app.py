import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import datetime

load_dotenv(dotenv_path="pass.env")
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "maya_ozel_anahtar")

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"), 
        database=os.getenv("DB_NAME", "RestoranDB")
    )

# ================= 1. GENEL BAKIŞ VE REZERVASYON =================
@app.route('/')
def index():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_Id ASC")
    masalar = cursor.fetchall()
    
    simdi = datetime.now()
    bugun_bas = simdi.replace(hour=0, minute=0, second=0, microsecond=0)
    bugun_bit = simdi.replace(hour=23, minute=59, second=59, microsecond=0)
    
    cursor.execute("SELECT Masa_Id FROM REZERVASYON WHERE Tarih BETWEEN %s AND %s", (bugun_bas, bugun_bit))
    dolu_masalar = [r['Masa_Id'] for r in cursor.fetchall()]
    db.close()
    return render_template('index.html', masalar=masalar, gunluk_dolu_masalar=dolu_masalar)

@app.route('/rezervasyon-olustur', methods=['POST'])
def rezervasyon_olustur():
    ad, soyad, telefon = request.form.get('ad'), request.form.get('soyad'), request.form.get('telefon')
    tarih, saat = request.form.get('tarih'), request.form.get('saat')
    kisi_sayisi, masa_id = request.form.get('kisi_sayisi'), request.form.get('masa_id')
    tarih_saat = f"{tarih} {saat}:00"
    
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO MUSTERI (Ad, Soyad, Telefon) VALUES (%s, %s, %s)", (ad, soyad, telefon))
        musteri_id = cursor.lastrowid
        cursor.execute("INSERT INTO REZERVASYON (Tarih, Kisi_Sayisi, Musteri_Id, Masa_Id) VALUES (%s, %s, %s, %s)", 
                       (tarih_saat, kisi_sayisi, musteri_id, masa_id))
        db.commit()
        flash("Rezervasyon başarıyla oluşturuldu!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Rezervasyon Hatası: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for('index'))

# ================= 2. MENÜ & ÜRÜNLER =================
@app.route('/menu')
def menu_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM URUN ORDER BY Urun_Id DESC")
    urunler = cursor.fetchall()
    db.close()
    return render_template('menu.html', urunler=urunler)

@app.route('/urun-ekle', methods=['POST'])
def urun_ekle():
    ad = request.form.get('urun_adi')
    fiyat = request.form.get('fiyat')
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # AUTO_INCREMENT HATA ÇÖZÜMÜ: En büyük ID'yi bulup kendimiz 1 ekliyoruz.
        cursor.execute("SELECT MAX(Urun_Id) as max_id FROM URUN")
        sonuc = cursor.fetchone()
        yeni_id = (sonuc['max_id'] or 0) + 1
        
        cursor.execute("INSERT INTO URUN (Urun_Id, Urun_Adi, Fiyat) VALUES (%s, %s, %s)", (yeni_id, ad, fiyat))
        db.commit()
        flash(f"'{ad}' menüye başarıyla eklendi!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Ürün eklenirken hata oluştu: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for('menu_listesi'))

@app.route('/urun-guncelle/<int:id>', methods=['POST'])
def urun_guncelle(id):
    yeni_fiyat = request.form.get('fiyat')
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE URUN SET Fiyat = %s WHERE Urun_Id = %s", (yeni_fiyat, id))
        db.commit()
        flash("Ürün fiyatı güncellendi! (💾)", "success")
    except Exception as e:
        db.rollback()
        flash("Fiyat güncellenemedi.", "danger")
    finally:
        db.close()
    return redirect(url_for('menu_listesi'))

@app.route('/urun-sil/<int:id>', methods=['POST'])
def urun_sil(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM URUN WHERE Urun_Id = %s", (id,))
        db.commit()
        flash("Ürün başarıyla silindi!", "success")
    except mysql.connector.Error as err:
        db.rollback()
        if err.errno == 1451:
            flash("HATA: Bu ürün bir adisyonda kullanıldığı için silinemez!", "danger")
        else:
            flash(f"Silme hatası: {err}", "danger")
    finally:
        db.close()
    return redirect(url_for('menu_listesi'))

# ================= 3. SİPARİŞLER =================
@app.route('/siparisler')
def siparis_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT Siparis_Id, Tutar as Toplam_Tutar, Masa_Id FROM SIPARIS")
    siparisler = cursor.fetchall()
    for s in siparisler:
        cursor.execute("""
            SELECT sd.Detay_Id, sd.Adet, sd.Ara_Toplam, u.Urun_Adi, u.Fiyat 
            FROM SIPARIS_DETAY sd 
            JOIN URUN u ON sd.Urun_Id = u.Urun_Id 
            WHERE sd.Siparis_Id = %s
        """, (s['Siparis_Id'],))
        s['Kalemler'] = cursor.fetchall()
    db.close()
    return render_template('siparisler.html', siparisler=siparisler)

@app.route('/siparis-adet-guncelle/<int:detay_id>', methods=['POST'])
def siparis_adet_guncelle(detay_id):
    yeni_adet = int(request.form.get('adet'))
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT sd.Siparis_Id, u.Fiyat FROM SIPARIS_DETAY sd JOIN URUN u ON sd.Urun_Id = u.Urun_Id WHERE sd.Detay_Id = %s", (detay_id,))
        bilgi = cursor.fetchone()
        if bilgi:
            yeni_ara_toplam = yeni_adet * bilgi['Fiyat']
            cursor.execute("UPDATE SIPARIS_DETAY SET Adet = %s, Ara_Toplam = %s WHERE Detay_Id = %s", (yeni_adet, yeni_ara_toplam, detay_id))
            cursor.execute("UPDATE SIPARIS SET Tutar = (SELECT SUM(Ara_Toplam) FROM SIPARIS_DETAY WHERE Siparis_Id = %s) WHERE Siparis_Id = %s", (bilgi['Siparis_Id'], bilgi['Siparis_Id']))
            db.commit()
    finally:
        db.close()
    return redirect(url_for('siparis_listesi'))

# ================= 4. MÜŞTERİLER (GÜNCELLENDİ) =================
@app.route('/musteriler')
def musteriler_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MUSTERI ORDER BY Musteri_Id DESC")
    musteriler = cursor.fetchall()
    db.close()
    return render_template('musteri.html', musteriler=musteriler)

@app.route('/musteri-sil/<int:id>', methods=['POST'])
def musteri_sil(id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM REZERVASYON WHERE Musteri_Id = %s", (id,))
        cursor.execute("DELETE FROM MUSTERI WHERE Musteri_Id = %s", (id,))
        db.commit()
        flash("Müşteri ve bağlı rezervasyonlar silindi!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Hata: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for('musteriler_listesi'))

@app.route('/rezervasyon-guncelle/<int:id>', methods=['POST'])
def rezervasyon_guncelle(id):
    tarih, saat, masa_id = request.form.get('tarih'), request.form.get('saat'), request.form.get('masa_id')
    yeni_tarih = f"{tarih} {saat}:00"
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE REZERVASYON SET Tarih=%s, Masa_Id=%s WHERE Musteri_Id=%s", (yeni_tarih, masa_id, id))
        db.commit()
        flash("Müşterinin rezervasyonu güncellendi!", "success")
    except Exception as e:
        db.rollback()
        flash(f"Hata: {str(e)}", "danger")
    finally:
        db.close()
    return redirect(url_for('musteriler_listesi'))

# ================= 5. MASALAR =================
@app.route('/masalar')
def masalar_listesi():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MASA ORDER BY Masa_Id ASC")
    masalar = cursor.fetchall()
    db.close()
    return render_template('masalar.html', masalar=masalar)

if __name__ == '__main__':
    app.run(debug=True, port=5000)