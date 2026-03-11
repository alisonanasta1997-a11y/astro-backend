from flask import Flask, request, jsonify
from flask_cors import CORS
from kerykeion import AstrologicalSubject

app = Flask(__name__)
CORS(app)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/natal', methods=['POST'])
def natal():
    try:
        data = request.json
        name   = data.get('name', 'Client')
        year   = int(data['year'])
        month  = int(data['month'])
        day    = int(data['day'])
        hour   = int(data['hour'])
        minute = int(data['minute'])
        lat    = float(data['lat'])
        lng    = float(data['lng'])
        tz_str = data.get('tz_str', 'UTC')

        subject = AstrologicalSubject(
            name=name, year=year, month=month, day=day,
            hour=hour, minute=minute,
            lat=lat, lng=lng, tz_str=tz_str,
            houses_system_identifier="K",
            zodiac_type="Tropic",
            online=False
        )

        SIGN_RU = {
            "Ari":"Овен","Tau":"Телец","Gem":"Близнецы","Can":"Рак",
            "Leo":"Лев","Vir":"Дева","Lib":"Весы","Sco":"Скорпион",
            "Sag":"Стрелец","Cap":"Козерог","Aqu":"Водолей","Pis":"Рыбы",
            "Aries":"Овен","Taurus":"Телец","Gemini":"Близнецы","Cancer":"Рак",
            "Virgo":"Дева","Libra":"Весы","Scorpio":"Скорпион",
            "Sagittarius":"Стрелец","Capricorn":"Козерог","Aquarius":"Водолей","Pisces":"Рыбы"
        }

        def p(obj, name):
            return {"name": name, "sign": obj.sign, "sign_ru": SIGN_RU.get(obj.sign, obj.sign),
                    "degree": round(obj.position, 4), "norm_degree": round(obj.position % 30, 4),
                    "house": obj.house, "retrograde": obj.retrograde}

        planets = [
            p(subject.sun, "Sun"), p(subject.moon, "Moon"),
            p(subject.mercury, "Mercury"), p(subject.venus, "Venus"),
            p(subject.mars, "Mars"), p(subject.jupiter, "Jupiter"),
            p(subject.saturn, "Saturn"), p(subject.uranus, "Uranus"),
            p(subject.neptune, "Neptune"), p(subject.pluto, "Pluto"),
            p(subject.true_node, "North Node"),
        ]

        houses = [{"house": h.number, "sign": h.sign,
                   "sign_ru": SIGN_RU.get(h.sign, h.sign),
                   "degree": round(h.position, 4)} for h in subject.houses_list]

        planet_objs = [subject.sun, subject.moon, subject.mercury, subject.venus,
                       subject.mars, subject.jupiter, subject.saturn, subject.uranus,
                       subject.neptune, subject.pluto, subject.true_node]
        planet_names = ["Sun","Moon","Mercury","Venus","Mars","Jupiter",
                        "Saturn","Uranus","Neptune","Pluto","North Node"]
        ASPS = [("conjunction",0,8),("opposition",180,8),("trine",120,7),
                ("square",90,7),("sextile",60,5)]
        aspects = []
        for i in range(len(planet_objs)):
            for j in range(i+1, len(planet_objs)):
                diff = abs(planet_objs[i].position - planet_objs[j].position)
                if diff > 180: diff = 360 - diff
                for aname, aangle, aorb in ASPS:
                    orb = abs(diff - aangle)
                    if orb <= aorb:
                        aspects.append({"planet1": planet_names[i], "planet2": planet_names[j],
                                        "type": aname, "orb": round(orb, 2)})
                        break
        aspects.sort(key=lambda x: x['orb'])

        return jsonify({
            "planets": planets, "houses": houses, "aspects": aspects,
            "ascendant": {"sign": subject.first_house.sign,
                          "sign_ru": SIGN_RU.get(subject.first_house.sign, ""),
                          "degree": round(subject.first_house.position, 4)},
            "midheaven": {"sign": subject.tenth_house.sign,
                          "sign_ru": SIGN_RU.get(subject.tenth_house.sign, ""),
                          "degree": round(subject.tenth_house.position, 4)}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
