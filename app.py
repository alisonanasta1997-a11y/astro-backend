import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from kerykeion import AstrologicalSubjectFactory

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

@app.route('/health', methods=['GET','OPTIONS'])
def health():
    return jsonify({"status": "ok"})

# ── Прокси для Claude API ──────────────────────────────────────
@app.route('/chat', methods=['POST','OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        data = request.json
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return jsonify({"error": "ANTHROPIC_API_KEY не настроен на сервере"}), 500

        resp = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01'
            },
            json=data,
            timeout=60
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Натальная карта ────────────────────────────────────────────
@app.route('/debug', methods=['GET'])
def debug():
    subject = AstrologicalSubjectFactory.from_birth_data(
        name="Test", year=1997, month=1, day=2,
        hour=20, minute=14, lat=57.005, lng=86.1472,
        tz_str="Asia/Krasnoyarsk",
        houses_system_identifier="K", online=False
    )
    attrs = [a for a in dir(subject) if not a.startswith('_')]
    return jsonify({"all_attributes": attrs, "sun_sign": subject.sun.sign})

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
            houses_system_identifier="K",
            online=False
        )

        def fmt(p, pname):
            sign  = getattr(p, 'sign', '')
            pos   = getattr(p, 'position', 0.0)
            house = str(getattr(p, 'house', 1))
            retro = bool(getattr(p, 'retrograde', False))
            return {"name":pname,"sign":sign,"sign_ru":SIGN_RU.get(sign,sign),
                    "degree":round(pos,4),"norm_degree":round(pos%30,4),
                    "house":house,"retrograde":retro}

        node = (getattr(subject,'true_node',None) or
                getattr(subject,'mean_node',None) or
                getattr(subject,'north_node',None))

        planets = [
            fmt(subject.sun,"Sun"), fmt(subject.moon,"Moon"),
            fmt(subject.mercury,"Mercury"), fmt(subject.venus,"Venus"),
            fmt(subject.mars,"Mars"), fmt(subject.jupiter,"Jupiter"),
            fmt(subject.saturn,"Saturn"), fmt(subject.uranus,"Uranus"),
            fmt(subject.neptune,"Neptune"), fmt(subject.pluto,"Pluto"),
        ]
        if node:
            planets.append(fmt(node,"North Node"))

        house_attrs = ['first_house','second_house','third_house','fourth_house',
                       'fifth_house','sixth_house','seventh_house','eighth_house',
                       'ninth_house','tenth_house','eleventh_house','twelfth_house']
        houses = []
        for i,attr in enumerate(house_attrs,1):
            h = getattr(subject, attr)
            sign = getattr(h,'sign','')
            pos  = getattr(h,'position',0.0)
            houses.append({"house":i,"sign":sign,"sign_ru":SIGN_RU.get(sign,sign),"degree":round(pos,4)})

        ASPS = [("conjunction",0,8),("opposition",180,8),("trine",120,7),("square",90,7),("sextile",60,5)]
        lons = [(p["name"], p["degree"]) for p in planets]
        aspects = []
        for i in range(len(lons)):
            for j in range(i+1, len(lons)):
                diff = abs(lons[i][1]-lons[j][1])
                if diff > 180: diff = 360-diff
                for aname,aangle,aorb in ASPS:
                    orb = abs(diff-aangle)
                    if orb <= aorb:
                        aspects.append({"planet1":lons[i][0],"planet2":lons[j][0],"type":aname,"orb":round(orb,2)})
                        break
        aspects.sort(key=lambda x: x['orb'])

        asc = subject.first_house
        mc  = subject.tenth_house
        return jsonify({
            "planets":planets,"houses":houses,"aspects":aspects,
            "ascendant":{"sign":asc.sign,"sign_ru":SIGN_RU.get(asc.sign,asc.sign),"degree":round(asc.position,4)},
            "midheaven":{"sign":mc.sign,"sign_ru":SIGN_RU.get(mc.sign,mc.sign),"degree":round(mc.position,4)}
        })

    except Exception as e:
        import traceback
        return jsonify({"error":str(e),"trace":traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
