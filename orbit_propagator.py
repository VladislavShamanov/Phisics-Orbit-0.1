# orbit_propagator.py
from datetime import datetime, timedelta
from sgp4.api import Satrec, WGS72
import math


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

        # --- ЗАМЕНИ ЭТОТ БЛОК В orbit_propagator.py (строки 22-26 примерно) ---
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
