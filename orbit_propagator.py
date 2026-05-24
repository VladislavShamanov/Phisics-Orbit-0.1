# orbit_propagator.py
from datetime import datetime, timedelta
from sgp4.api import Satrec, WGS72
import math

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)



def get_points_along_orbit(tle_line1, tle_line2, start_time, duration_minutes, step_seconds):
    """
    Генерирует точки орбиты спутника на основе TLE.
    Возвращает список словарей с параметрами: время, высота, широта, долгота.
    """
    # Инициализируем спутник из TLE
    satellite = Satrec.twoline2rv(tle_line1, tle_line2)

    points = []
    current_time = start_time
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Радиус Земли по модели WGS72
    R_earth = 6378.135

    while current_time <= end_time:
        # Переводим время в формат для SGP4 (Юлианская дата)
        # В новых версиях sgp4 перевод делается через функцию jday
        from sgp4.api import jday
        jd, fr = jday(
            current_time.year, current_time.month, current_time.day,
            current_time.hour, current_time.minute, current_time.second + current_time.microsecond / 1e6
        )

        # Получаем положение (position) и скорость в геоцентрической системе координат (в км)
        error_code, position, velocity = satellite.sgp4(jd, fr)

        if error_code == 0:
            x, y, z = position[0], position[1], position[2]

            # Расчет полной высоты от центра Земли и высоты над поверхностью (км)
            r = math.sqrt(x ** 2 + y ** 2 + z ** 2)
            height = r - R_earth

            # Перевод декартовых координат в широту и долготу (упрощенно)
            latitude = math.degrees(math.asin(z / r))
            longitude = math.degrees(math.atan2(y, x))

            # Рассчитываем местное время (local time) приблизительно по долготе
            local_time = (current_time.hour + current_time.minute / 60.0 + longitude / 15.0) % 24.0
            if local_time < 0: local_time += 24.0

            points.append({
                'time': current_time.strftime("%H:%M:%S"),
                'height': height,
                'lat': latitude,
                'lon': longitude,
                'local_time': local_time
            })

        # Шагаем вперед по орбите
        current_time += timedelta(seconds=step_seconds)

    return points

# Добавить в самый конец orbit_propagator.py

def download_tle_from_celestrak(norad_id):
    """Скачивает свежий TLE с Celestrak по NORAD ID и обновляет satellites.json"""
    import requests, json, os
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ИСПРАВЛЕННЫЙ URL: ОФИЦИАЛЬНОЕ API CELESTRAK
    url = f"https://celestrak.org{norad_id}&FORMAT=TLE"

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # verify=False убирает проблемы с SSL-сертификатами в Python на Windows
        response = requests.get(url, headers=headers, timeout=10, verify=False)

        # Если Celestrak вернул ошибку или пустой файл
        if response.status_code != 200 or "No data found" in response.text or not response.text.strip():
            return None

        lines = [line.strip() for line in response.text.strip().split('\n') if line.strip()]

        # Проверяем, что пришло ровно 3 строки (Имя + 2 строки TLE)
        if len(lines) >= 3:
            name = lines[0]
            tle_l1 = lines[1]
            tle_l2 = lines[2]

            json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
            sat_data = {}

            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    try:
                        sat_data = json.load(f)
                    except:
                        sat_data = {}

            # Сохраняем под ключом NORAD ID
            sat_data[str(norad_id)] = {
                "name": name,
                "tle_l1": tle_l1,
                "tle_l2": tle_l2
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(sat_data, f, ensure_ascii=False, indent=2)

            return name
    except Exception as e:
        print(f"Ошибка API: {e}")
        return None
    return None


def save_grid_to_csv(path, grid_ctrl):
    """Сохраняет данные из таблицы wx.grid.Grid в CSV файл"""
    num_rows = grid_ctrl.GetNumberRows()
    try:
        with open(path, 'w', encoding='utf-8-sig') as f:
            headers = ["Время", "Высота (км)", "Широта", "Долгота", "Плотность (кг/м³)"]
            f.write(";".join(headers) + "\n")
            for r in range(num_rows):
                row_data = [grid_ctrl.GetCellValue(r, c) for c in range(5)]
                f.write(";".join(row_data) + "\n")
        return True
    except:
        return False

