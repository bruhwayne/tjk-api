from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)
CORS(app)  # Flutter'dan gelen isteklere izin ver

# TJK ayarları
TARGET_URL = "https://www.tjk.org/TR/YarisSever/Query/Data/Atlar"
REFERER_URL = "https://www.tjk.org/TR/YarisSever/Query/Page/Atlar?QueryParameter_OLDUFLG=on"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Referer": REFERER_URL
}

def map_breed_to_id(breed):
    """Irk adını TJK ID'sine çevirir"""
    breed_map = {
        'Tümü': '-1',
        'İngiliz': '1',
        'Arap': '2'
    }
    return breed_map.get(breed, '-1')

def map_gender_to_id(gender):
    """Cinsiyet adını TJK ID'sine çevirir"""
    gender_map = {
        'Tümü': '-1',
        'Erkek': '1',
        'Dişi': '2',
        'İğdiş': '3'
    }
    return gender_map.get(gender, '-1')

def map_country_to_id(country):
    """Ülke adını TJK ID'sine çevirir"""
    country_map = {
        'Tümü': '-1',
        'Türkiye': '1',
        'İngiltere': '2',
        'Fransa': '3',
        'ABD': '4',
        'İrlanda': '5'
    }
    return country_map.get(country, '-1')

@app.route('/api/search-horses', methods=['POST'])
def search_horses():
    """At arama endpoint'i"""
    try:
        data = request.json
        
        # Form payload'ını hazırla
        payload = {
            "QueryParameter_AtIsmi": data.get('horseName', ''),
            "QueryParameter_IrkId": map_breed_to_id(data.get('breed', 'Tümü')),
            "QueryParameter_CinsiyetId": map_gender_to_id(data.get('gender', 'Tümü')),
            "QueryParameter_Yas": data.get('age', ''),
            "QueryParameter_BabaId": data.get('fatherName', ''),
            "QueryParameter_AnneId": data.get('motherName', ''),
            "QueryParameter_UzerineKosanSahipId": data.get('ownerName', ''),
            "QueryParameter_YetistiricAdi": data.get('breederName', ''),
            "QueryParameter_AntronorId": data.get('trainerName', ''),
            "QueryParameter_UlkeId": map_country_to_id(data.get('country', 'Tümü')),
            "QueryParameter_OLDUFLG": "on" if data.get('includeDeadHorses', False) else "",
            "Era": "past",
            "Sort": "AtIsmi",
            "OldQueryParameter_OLDUFLG": "on" if data.get('includeDeadHorses', False) else ""
        }
        
        # TJK'ya istek gönder
        response = requests.get(
            TARGET_URL,
            params=payload,
            headers=HEADERS,
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'TJK sunucusundan cevap alınamadı. Status: {response.status_code}'
            }), 500
        
        # HTML'i parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        stats_table = soup.find('table', id='queryTable')
        
        if not stats_table:
            return jsonify({
                'success': True,
                'horses': [],
                'message': 'Sonuç bulunamadı'
            })
        
        table_body = stats_table.find('tbody', id='tbody0')
        if not table_body:
            return jsonify({
                'success': True,
                'horses': [],
                'message': 'Sonuç bulunamadı'
            })
        
        rows = table_body.find_all('tr')
        horses = []
        
        for row in rows:
            if 'hidable' in row.get('class', []):
                continue
            
            try:
                at_ismi_cell = row.find('td', class_='sorgu-Atlar-AtIsmi')
                irk_cell = row.find('td', class_='sorgu-Atlar-IrkAdi')
                cinsiyet_cell = row.find('td', class_='sorgu-Atlar-Cinsiyet')
                yas_cell = row.find('td', class_='sorgu-Atlar-Yas')
                orijin_cell = row.find('td', class_='sorgu-Atlar-BabaAdi')
                sahip_cell = row.find('td', class_='sorgu-Atlar-UzerineKosanSahip')
                antrenor_cell = row.find('td', class_='sorgu-Atlar-Antronoru')
                son_kosu_cell = row.find('td', class_='sorgu-Atlar-SonKosu')
                ikramiye_cell = row.find('td', class_='sorgu-Atlar-SadeAtKazanc')
                
                if not at_ismi_cell or not irk_cell:
                    continue
                
                # Orijin (Baba/Anne) bilgisini parse et
                orijin_text = " ".join(orijin_cell.text.split()) if orijin_cell else ""
                orijin_parts = orijin_text.split('/')
                baba = orijin_parts[0].strip() if len(orijin_parts) > 0 else ""
                anne = orijin_parts[1].strip() if len(orijin_parts) > 1 else ""
                
                at_ismi_link = at_ismi_cell.find('a')
                
                horse = {
                    'name': at_ismi_cell.text.strip(),
                    'detailLink': at_ismi_link['href'] if at_ismi_link else "",
                    'breed': irk_cell.text.strip(),
                    'gender': cinsiyet_cell.text.strip() if cinsiyet_cell else "",
                    'age': yas_cell.text.strip() if yas_cell else "",
                    'father': baba,
                    'mother': anne,
                    'owner': sahip_cell.text.strip() if sahip_cell else "",
                    'trainer': antrenor_cell.text.strip() if antrenor_cell else "",
                    'lastRace': son_kosu_cell.text.strip() if son_kosu_cell else "",
                    'prize': ikramiye_cell.text.strip() if ikramiye_cell else ""
                }
                
                horses.append(horse)
                
            except Exception as e:
                print(f"Satır parse hatası: {e}")
                continue
        
        return jsonify({
            'success': True,
            'horses': horses,
            'count': len(horses)
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'İstek hatası: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Beklenmeyen hata: {str(e)}'
        }), 500

@app.route('/api/horse-details', methods=['POST'])
def get_horse_details():
    """At detay bilgilerini getir"""
    try:
        data = request.json
        relative_url = data.get('detailLink', '')
        
        if not relative_url:
            return jsonify({
                'success': False,
                'error': 'Detay linki bulunamadı'
            }), 400
        
        detail_url = urljoin(TARGET_URL, relative_url)
        detail_url = detail_url.replace("&amp;", "&")
        
        response = requests.get(detail_url, headers=HEADERS, timeout=10)
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'Detay sayfası alınamadı. Status: {response.status_code}'
            }), 500
        
        soup = BeautifulSoup(response.text, 'html.parser')
        data_div = soup.find('div', id='dataDiv')
        
        if not data_div:
            return jsonify({
                'success': False,
                'error': 'Detay sayfasında veri bulunamadı'
            }), 404
        
        race_table = data_div.find('table', id='queryTable')
        if not race_table:
            return jsonify({
                'success': True,
                'races': [],
                'message': 'Yarış geçmişi bulunamadı'
            })
        
        table_body = race_table.find('tbody', id='tbody0')
        if not table_body:
            return jsonify({
                'success': True,
                'races': [],
                'message': 'Yarış geçmişi bulunamadı'
            })
        
        rows = table_body.find_all('tr')
        races = []
        
        for row in rows:
            if 'hidable' in row.get('class', []):
                continue
            
            cells = row.find_all('td')
            
            if len(cells) > 17:
                try:
                    race = {
                        'date': cells[0].text.strip(),
                        'city': cells[1].text.strip(),
                        'distance': cells[2].text.strip(),
                        'track': " ".join(cells[3].text.strip().split()),
                        'position': cells[4].text.strip(),
                        'grade': cells[5].text.strip(),
                        'jockey': cells[8].text.strip(),
                        'prize': cells[17].text.strip()
                    }
                    races.append(race)
                except IndexError:
                    continue
        
        return jsonify({
            'success': True,
            'races': races,
            'count': len(races)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Hata: {str(e)}'
        }), 500

@app.route('/api/search-races', methods=['POST'])
def search_races():
    """Yarış arama endpoint'i"""
    try:
        data = request.json
        
        # Yarış sorgulama URL'si
        race_url = "https://www.tjk.org/TR/YarisSever/Query/DataRows/KosuSorgulama"
        
        # Form payload'ını hazırla
        params = {
            'PageNumber': '1',
            'Sort': 'Tarih desc, Sehir asc, KosuSirasi asc',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        payload = {
            'QueryParameter_TarihBaslangic': data.get('startDate', ''),
            'QueryParameter_TarihBitis': data.get('endDate', ''),
            'QueryParameter_Sehir': data.get('city', ''),
            'QueryParameter_TumSehirler': data.get('allCities', 'on'),
            'QueryParameter_TumIrklar': data.get('allBreeds', 'on'),
            'QueryParameter_TumKosuGrubu': data.get('allRaceGroups', 'on'),
            'QueryParameter_TumPistler': data.get('allTracks', 'on'),
            'QueryParameter_AprKosCinsi': data.get('raceType', ''),
            'QueryParameter_Mesafe': data.get('distance', ''),
            'QueryParameter_BabaIsmi': data.get('fatherName', ''),
            'QueryParameter_AnneIsmi': data.get('motherName', ''),
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.tjk.org/TR/YarisSever/Query/Page/KosuSorgulama"
        }
        
        # TJK'ya istek gönder
        response = requests.post(
            race_url,
            params=params,
            data=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({
                'success': False,
                'error': f'TJK sunucusundan cevap alınamadı. Status: {response.status_code}'
            }), 500
        
        # HTML'i parse et
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Yarış satırlarını bul
        race_rows = soup.find_all('tr', class_='row-data')
        
        if not race_rows:
            return jsonify({
                'success': True,
                'races': [],
                'message': 'Sonuç bulunamadı'
            })
        
        races = []
        
        for row in race_rows:
            try:
                cells = row.find_all('td')
                
                if len(cells) >= 8:
                    # Detay linkini bul
                    detail_link = ''
                    link_elem = row.find('a', href=True)
                    if link_elem:
                        detail_link = link_elem['href']
                    
                    race = {
                        'date': cells[0].text.strip() if len(cells) > 0 else '',
                        'city': cells[1].text.strip() if len(cells) > 1 else '',
                        'raceNumber': cells[2].text.strip() if len(cells) > 2 else '',
                        'raceType': cells[3].text.strip() if len(cells) > 3 else '',
                        'distance': cells[4].text.strip() if len(cells) > 4 else '',
                        'track': cells[5].text.strip() if len(cells) > 5 else '',
                        'breed': cells[6].text.strip() if len(cells) > 6 else '',
                        'gender': cells[7].text.strip() if len(cells) > 7 else '',
                        'detailLink': detail_link
                    }
                    
                    races.append(race)
                    
            except Exception as e:
                print(f"Satır parse hatası: {e}")
                continue
        
        return jsonify({
            'success': True,
            'races': races,
            'count': len(races)
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'İstek hatası: {str(e)}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Beklenmeyen hata: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Sunucu sağlık kontrolü"""
    return jsonify({'status': 'ok', 'message': 'TJK API Server çalışıyor'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("TJK API Server başlatılıyor...")
    print("Endpoint'ler:")
    print("  POST /api/search-horses - At arama")
    print("  POST /api/horse-details - At detayları")
    print("  POST /api/search-races - Yarış arama")
    print("  GET  /health - Sağlık kontrolü")
    print(f"Port: {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
