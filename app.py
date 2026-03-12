import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from kerykeion import AstrologicalSubjectFactory
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}},
     allow_headers=["Content-Type"], methods=["GET","POST","OPTIONS"])

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

SIGN_RU = {
    "Ari":"Овен","Tau":"Телец","Gem":"Близнецы","Can":"Рак",
    "Leo":"Лев","Vir":"Дева","Lib":"Весы","Sco":"Скорпион",
    "Sag":"Стрелец","Cap":"Козерог","Aqu":"Водолей","Pis":"Рыбы",
    "Aries":"Овен","Taurus":"Телец","Gemini":"Близнецы","Cancer":"Рак",
    "Virgo":"Дева","Libra":"Весы","Scorpio":"Скорпион",
    "Sagittarius":"Стрелец","Capricorn":"Козерог","Aquarius":"Водолей","Pisces":"Рыбы"
}

KNOWLEDGE_BASE = """
=== БАЗА ЗНАНИЙ ПО АСТРОЛОГИИ ===
(база знаний астролога — используй для консультаций)
"""

@app.route('/health', methods=['GET','OPTIONS'])
def health():
    return jsonify({"status": "ok"})

# ── Геокодирование ─────────────────────────────────────────────
@app.route('/geocode', methods=['POST','OPTIONS'])
def geocode():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data  = request.json
        city  = data.get('city', '')
        year  = int(data.get('year', 2000))
        month = int(data.get('month', 1))
        day   = int(data.get('day', 1))
        hour  = int(data.get('hour', 12))

        # Геокодирование через Nominatim
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': city, 'format': 'json', 'limit': 1},
            headers={'User-Agent': 'AstroConsultant/1.0'},
            timeout=10
        )
        results = resp.json()
        if not results:
            return jsonify({"error": "Город не найден"}), 404

        lat = float(results[0]['lat'])
        lng = float(results[0]['lon'])
        display_name = results[0]['display_name']

        # Определяем timezone через timeapi.io
        tz_resp = requests.get(
            f'https://timeapi.io/api/timezone/coordinate?latitude={lat}&longitude={lng}',
            timeout=10
        )
        tz_data = tz_resp.json()
        tz_str = tz_data.get('timeZone', 'UTC')

        # Точный UTC offset на дату рождения
        tz = pytz.timezone(tz_str)
        birth_dt = datetime(year, month, day, hour, 0)
        offset = tz.utcoffset(birth_dt)
        gmt = offset.total_seconds() / 3600

        return jsonify({
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "gmt": gmt,
            "tz_str": tz_str,
            "display_name": display_name.split(',')[:3]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Прокси для Groq API ────────────────────────────────────────
@app.route('/chat', methods=['POST','OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.json
        api_key = os.environ.get('GROQ_API_KEY', '')
        if not api_key:
            return jsonify({"error": "GROQ_API_KEY не настроен"}), 500

        messages = [{"role": "system", "content": data.get('system', '') + "\n\n" + KNOWLEDGE_BASE}]
        for m in data.get('messages', []):
            messages.append({"role": m['role'], "content": m['content']})

        resp = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
            json={"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 1000, "temperature": 0.7},
            timeout=60
        )
        result = resp.json()
        if 'choices' in result:
            return jsonify({"content": [{"type": "text", "text": result['choices'][0]['message']['content']}]})
        return jsonify({"error": str(result)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Натальная карта ────────────────────────────────────────────
@app.route('/natal', methods=['POST','OPTIONS'])
def natal():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data   = request.json
        name   = data.get('name', 'Client')
        year   = int(data['year'])
        month  = int(data['month'])
        day    = int(data['day'])
        hour   = int(data['hour'])
        minute = int(data['minute'])
        lat    = float(data['lat'])
        lng    = float(data['lng'])
        tz_str = data.get('tz_str', 'UTC')

        subject = AstrologicalSubjectFactory.from_birth_data(
            name=name, year=year, month=month, day=day,
            hour=hour, minute=minute,
            lat=lat, lng=lng, tz_str=tz_str,
            houses_system_identifier="K", online=False
        )

        def fmt(p, pname):
            return {"name": pname, "sign": getattr(p,'sign',''), "sign_ru": SIGN_RU.get(getattr(p,'sign',''),''),
                    "degree": round(getattr(p,'position',0.0),4), "norm_degree": round(getattr(p,'position',0.0)%30,4),
                    "house": str(getattr(p,'house',1)), "retrograde": bool(getattr(p,'retrograde',False))}

        node = getattr(subject,'true_node',None) or getattr(subject,'mean_node',None) or getattr(subject,'north_node',None)
        planets = [fmt(subject.sun,"Sun"), fmt(subject.moon,"Moon"), fmt(subject.mercury,"Mercury"),
                   fmt(subject.venus,"Venus"), fmt(subject.mars,"Mars"), fmt(subject.jupiter,"Jupiter"),
                   fmt(subject.saturn,"Saturn"), fmt(subject.uranus,"Uranus"), fmt(subject.neptune,"Neptune"),
                   fmt(subject.pluto,"Pluto")]
        if node: planets.append(fmt(node,"North Node"))

        houses = []
        for i,attr in enumerate(['first_house','second_house','third_house','fourth_house','fifth_house','sixth_house',
                                   'seventh_house','eighth_house','ninth_house','tenth_house','eleventh_house','twelfth_house'],1):
            h = getattr(subject, attr)
            houses.append({"house":i,"sign":getattr(h,'sign',''),"sign_ru":SIGN_RU.get(getattr(h,'sign',''),''),"degree":round(getattr(h,'position',0.0),4)})

        ASPS = [("conjunction",0,8),("opposition",180,8),("trine",120,7),("square",90,7),("sextile",60,5)]
        lons = [(p["name"], p["degree"]) for p in planets]
        aspects = []
        for i in range(len(lons)):
            for j in range(i+1,len(lons)):
                diff = abs(lons[i][1]-lons[j][1])
                if diff>180: diff=360-diff
                for aname,aangle,aorb in ASPS:
                    orb=abs(diff-aangle)
                    if orb<=aorb:
                        aspects.append({"planet1":lons[i][0],"planet2":lons[j][0],"type":aname,"orb":round(orb,2)}); break
        aspects.sort(key=lambda x:x['orb'])

        asc,mc = subject.first_house, subject.tenth_house
        return jsonify({"planets":planets,"houses":houses,"aspects":aspects,
            "ascendant":{"sign":asc.sign,"sign_ru":SIGN_RU.get(asc.sign,''),"degree":round(asc.position,4)},
            "midheaven":{"sign":mc.sign,"sign_ru":SIGN_RU.get(mc.sign,''),"degree":round(mc.position,4)}})
    except Exception as e:
        import traceback
        return jsonify({"error":str(e),"trace":traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
