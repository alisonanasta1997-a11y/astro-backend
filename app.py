from flask import Flask, request, jsonify
from flask_cors import CORS
from kerykeion import AstrologicalSubjectFactory

app = Flask(__name__)
CORS(app)

SIGN_RU = {
    "Ari":"Овен","Tau":"Телец","Gem":"Близнецы","Can":"Рак",
    "Leo":"Лев","Vir":"Дева","Lib":"Весы","Sco":"Скорпион",
    "Sag":"Стрелец","Cap":"Козерог","Aqu":"Водолей","Pis":"Рыбы",
    "Aries":"Овен","Taurus":"Телец","Gemini":"Близнецы","Cancer":"Рак",
    "Virgo":"Дева","Libra":"Весы","Scorpio":"Скорпион",
    "Sagittarius":"Стрелец","Capricorn":"Козерог","Aquarius":"Водолей","Pisces":"Рыбы"
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/natal', methods=['POST'])
def natal():
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
            houses_system="K",   # Koch
            online=False
        )

        def fmt_planet(p, name):
            sign = p.sign if hasattr(p, 'sign') else str(p.get('sign',''))
            pos  = p.position if hasattr(p, 'position') else float(p.get('abs_pos', 0))
            house = str(p.house) if hasattr(p, 'house') else str(p.get('house','1'))
            retro = p.retrograde if hasattr(p, 'retrograde') else bool(p.get('retrograde', False))
            return {
                "name": name,
                "sign": sign,
                "sign_ru": SIGN_RU.get(sign, sign),
                "degree": round(pos, 4),
                "norm_degree": round(pos % 30, 4),
                "house": house,
                "retrograde": retro
            }

        planet_map = [
            (subject.sun,       "Sun"),
            (subject.moon,      "Moon"),
            (subject.mercury,   "Mercury"),
            (subject.venus,     "Venus"),
            (subject.mars,      "Mars"),
            (subject.jupiter,   "Jupiter"),
            (subject.saturn,    "Saturn"),
            (subject.uranus,    "Uranus"),
            (subject.neptune,   "Neptune"),
            (subject.pluto,     "Pluto"),
            (subject.true_node, "North Node"),
        ]
        planets = [fmt_planet(p, n) for p, n in planet_map]

        # Houses
        house_attrs = [
            'first_house','second_house','third_house','fourth_house',
            'fifth_house','sixth_house','seventh_house','eighth_house',
            'ninth_house','tenth_house','eleventh_house','twelfth_house'
        ]
        houses = []
        for i, attr in enumerate(house_attrs, 1):
            h = getattr(subject, attr)
            sign = h.sign if hasattr(h, 'sign') else str(h.get('sign',''))
            pos  = h.position if hasattr(h, 'position') else float(h.get('abs_pos', 0))
            houses.append({
                "house": i,
                "sign": sign,
                "sign_ru": SIGN_RU.get(sign, sign),
                "degree": round(pos, 4)
            })

        # Aspects
        ASPS = [("conjunction",0,8),("opposition",180,8),("trine",120,7),
                ("square",90,7),("sextile",60,5)]
        planet_lons = [(n, p.position if hasattr(p,'position') else float(p.get('abs_pos',0)))
                       for p,n in planet_map]
        aspects = []
        for i in range(len(planet_lons)):
            for j in range(i+1, len(planet_lons)):
                diff = abs(planet_lons[i][1] - planet_lons[j][1])
                if diff > 180: diff = 360 - diff
                for aname, aangle, aorb in ASPS:
                    orb = abs(diff - aangle)
                    if orb <= aorb:
                        aspects.append({"planet1": planet_lons[i][0], "planet2": planet_lons[j][0],
                                        "type": aname, "orb": round(orb, 2)})
                        break
        aspects.sort(key=lambda x: x['orb'])

        asc = subject.first_house
        mc  = subject.tenth_house
        return jsonify({
            "planets": planets,
            "houses": houses,
            "aspects": aspects,
            "ascendant": {
                "sign": asc.sign, "sign_ru": SIGN_RU.get(asc.sign, asc.sign),
                "degree": round(asc.position, 4)
            },
            "midheaven": {
                "sign": mc.sign, "sign_ru": SIGN_RU.get(mc.sign, mc.sign),
                "degree": round(mc.position, 4)
            }
        })

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
