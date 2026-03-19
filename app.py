from flask import Flask, request, jsonify
from flask_cors import CORS
from kerykeion import AstrologicalSubject, KerykeionChartSVG
import requests
import pytz
from datetime import datetime
import os
import re

app = Flask(__name__)
CORS(app)

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
SUPABASE_URL  = "https://cjtcggqrlbrcuuslgzmz.supabase.co"
SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNqdGNnZ3FybGJyY3V1c2xnem16Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMzOTkxNjAsImV4cCI6MjA4ODk3NTE2MH0.1rj5AdbAj7foEKiQI0eJFgJvzk1-_BlaEJQdLD0zZqM"

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/debug', methods=['GET'])
def debug():
    try:
        from kerykeion import AstrologicalSubject
        s = AstrologicalSubject("Test", 1997, 1, 2, 20, 14, lat=56.9992, lng=86.1417, tz_str="Asia/Krasnoyarsk", houses_system_identifier="K")
        attrs = [a for a in dir(s) if not a.startswith('_')]
        sun_attrs = {}
        try:
            sun = s.sun
            sun_attrs = {k: str(getattr(sun,k,'?')) for k in ['name','sign','abs_pos','position','house_name','retrograde'] if hasattr(sun,k)}
        except Exception as e:
            sun_attrs = {"error": str(e)}
        return jsonify({"attrs_sample": attrs[:30], "sun": sun_attrs})
    except Exception as e:
        return jsonify({"error": str(e)})

# ── Поиск в базе знаний ────────────────────────────────────────
def search_knowledge(query, limit=4):
    """Полнотекстовый поиск по базе Шестопалова"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/search_chunks"
        headers = {
            "apikey": SUPABASE_ANON,
            "Authorization": f"Bearer {SUPABASE_ANON}",
            "Content-Type": "application/json"
        }
        r = requests.post(url, headers=headers, json={"query": query, "lim": limit}, timeout=5)
        if r.status_code == 200:
            results = r.json()
            if results:
                return "\n\n---\n\n".join([
                    f"[{item['book']}, стр.{item['page']}]\n{item['text'][:600]}"
                    for item in results
                ])
    except Exception as e:
        print(f"Knowledge search error: {e}")
    return ""

# ── Геокодирование ─────────────────────────────────────────────
@app.route('/geocode', methods=['POST'])
def geocode():
    data = request.json
    city = data.get('city', '')
    year = data.get('year', 2000)
    month = data.get('month', 1)
    day = data.get('day', 1)
    hour = data.get('hour', 12)

    nom_url = "https://nominatim.openstreetmap.org/search"
    nom_params = {"q": city, "format": "json", "limit": 1, "addressdetails": 1}
    nom_headers = {"User-Agent": "AstroAgent/1.0"}
    nom_resp = requests.get(nom_url, params=nom_params, headers=nom_headers, timeout=10)
    nom_resp.raise_for_status()
    results = nom_resp.json()
    if not results:
        return jsonify({"error": f"Город '{city}' не найден"}), 404

    loc = results[0]
    lat = float(loc['lat'])
    lng = float(loc['lon'])
    display_name = loc.get('display_name', city)

    tz_url = f"https://timeapi.io/api/timezone/coordinate?latitude={lat}&longitude={lng}"
    tz_resp = requests.get(tz_url, timeout=10)
    tz_resp.raise_for_status()
    tz_data = tz_resp.json()
    tz_str = tz_data.get('timeZone', 'UTC')

    tz = pytz.timezone(tz_str)
    dt = datetime(int(year), int(month), int(day), int(hour), 0)
    offset = tz.utcoffset(dt)
    gmt = int(offset.total_seconds() / 3600)

    return jsonify({"lat": lat, "lng": lng, "gmt": gmt, "tz_str": tz_str, "display_name": display_name})

# ── Натальная карта ────────────────────────────────────────────
@app.route('/natal', methods=['POST'])
def natal():
    data = request.json
    name    = data.get('name', 'User')
    year    = int(data.get('year', 2000))
    month   = int(data.get('month', 1))
    day     = int(data.get('day', 1))
    hour    = int(data.get('hour', 12))
    minute  = int(data.get('minute', 0))
    lat     = float(data.get('lat', 55.75))
    lng     = float(data.get('lng', 37.62))
    tz_str  = data.get('tz_str', 'Europe/Moscow')

    subject = AstrologicalSubject(
        name=name, year=year, month=month, day=day,
        hour=hour, minute=minute,
        lat=lat, lng=lng,
        tz_str=tz_str,
        houses_system_identifier="K"
    )

    SIGNS_RU = {
        'Ari':'Овен','Tau':'Телец','Gem':'Близнецы','Can':'Рак',
        'Leo':'Лев','Vir':'Дева','Lib':'Весы','Sco':'Скорпион',
        'Sag':'Стрелец','Cap':'Козерог','Aqu':'Водолей','Pis':'Рыбы'
    }

    def sign_ru(s):
        return SIGNS_RU.get(s, s)

    planets_data = []
    for pname in ['sun','moon','mercury','venus','mars','jupiter','saturn','uranus','neptune','pluto','true_node']:
        try:
            p = getattr(subject, pname)
            planets_data.append({
                "name": p.name,
                "sign": p.sign,
                "sign_ru": sign_ru(p.sign),
                "degree": p.abs_pos,
                "norm_degree": p.position,
                "house": p.house_name,
                "retrograde": p.retrograde
            })
        except:
            pass

    houses_data = []
    for i, hname in enumerate(['first_house','second_house','third_house','fourth_house',
                                'fifth_house','sixth_house','seventh_house','eighth_house',
                                'ninth_house','tenth_house','eleventh_house','twelfth_house'], 1):
        try:
            h = getattr(subject, hname)
            houses_data.append({
                "house": i,
                "sign": h.sign,
                "degree": h.abs_pos,
                "norm_degree": h.position
            })
        except:
            pass

    aspects_data = []
    try:
        from kerykeion import NatalAspects
        aspects = NatalAspects(subject)
        for a in aspects.all_aspects:
            aspects_data.append({
                "planet1": a.p1_name,
                "planet2": a.p2_name,
                "type": a.aspect,
                "orb": round(abs(a.orbit), 2)
            })
    except:
        pass

    asc = subject.first_house
    mc  = subject.tenth_house

    return jsonify({
        "planets": planets_data,
        "houses": houses_data,
        "aspects": aspects_data,
        "ascendant": {"sign": asc.sign, "sign_ru": sign_ru(asc.sign), "degree": asc.abs_pos},
        "midheaven": {"sign": mc.sign,  "sign_ru": sign_ru(mc.sign),  "degree": mc.abs_pos}
    })

# ── Чат с базой знаний ─────────────────────────────────────────
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    messages  = data.get('messages', [])
    chart_ctx = data.get('chart_context', '')

    # Поиск релевантных отрывков из книг
    last_user_msg = ""
    for m in reversed(messages):
        if m.get('role') == 'user':
            last_user_msg = m.get('content', '')
            break

    knowledge = ""
    if last_user_msg:
        knowledge = search_knowledge(last_user_msg)

    knowledge_block = ""
    if knowledge:
        knowledge_block = f"""

═══ ЗНАНИЯ ИЗ КНИГ ШЕСТОПАЛОВА ═══
{knowledge}
═══════════════════════════════════
Используй эти знания как основу для ответа. Ссылайся на них естественно, не цитируй дословно.
"""

    system_prompt = f"""Ты — профессиональный астролог-консультант, глубоко знающий систему Шестопалова.
Говоришь по-русски, тепло и профессионально. Используешь астрологическую символику.
Опираешься на систему домов Кох.

НАТАЛЬНАЯ КАРТА КЛИЕНТА:
{chart_ctx}
{knowledge_block}
Давай конкретные, персональные интерпретации на основе карты и знаний из книг."""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": 1000,
        "messages": [{"role": "system", "content": system_prompt}] + messages
    }
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    reply = r.json()["choices"][0]["message"]["content"]
    return jsonify({"reply": reply})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
