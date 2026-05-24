# kepler_converter.py
import math


def kepler_to_cartesian(a, e, i_deg, omega_deg, w_deg, M_deg):
    """
    Перевод Кеплеровых элементов орбиты в декартовы координаты (X,Y,Z) и скорости (Vx,Vy,Vz)
    a - большая полуось (км)
    e - эксцентриситет (0 до 1)
    i_deg - наклонение (градусы)
    omega_deg - долгота восходящего узла (градусы)
    w_deg - аргумент перицентра (градусы)
    M_deg - средняя аномалия (градусы)
    """
    # Геоцентрическая гравитационная постоянная Земли (км³/с²)
    MU = 398600.4418

    # Переводим углы в радианы
    i = math.radians(i_deg)
    omega = math.radians(omega_deg)
    w = math.radians(w_deg)
    M = math.radians(M_deg)

    # 1. Решаем уравнение Кеплера: E - e*sin(E) = M методом Ньютона
    E = M  # начальное приближение
    for _ in range(100):
        delta = (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
        E -= delta
        if abs(delta) < 1e-10:
            break

    # 2. Истинная аномалия (nu)
    nu = 2.0 * math.atan2(math.sqrt(1.0 + e) * math.sin(E / 2.0), math.sqrt(1.0 - e) * math.cos(E / 2.0))

    # 3. Расстояние до центра Земли (r)
    r = a * (1.0 - e * math.cos(E))

    # 4. Координаты и скорости в плоскости орбиты (перифокальная система)
    x_orb = r * math.cos(nu)
    y_orb = r * math.sin(nu)

    p = a * (1.0 - e ** 2)
    if p <= 0: return [0, 0, 0], [0, 0, 0]

    vx_orb = -math.sin(nu) * math.sqrt(MU / p)
    vy_orb = (e + math.cos(nu)) * math.sqrt(MU / p)

    # 5. Матрица перехода в геоцентрическую экваториальную систему (3D вращение)
    # Элементы матрицы направляющих косинусов
    cos_o, sin_o = math.cos(omega), math.sin(omega)
    cos_w, sin_w = math.cos(w), math.sin(w)
    cos_i, sin_i = math.cos(i), math.sin(i)

    R11 = cos_o * cos_w - sin_o * sin_w * cos_i
    R12 = -cos_o * sin_w - sin_o * cos_w * cos_i
    R21 = sin_o * cos_w + cos_o * sin_w * cos_i
    R22 = -sin_o * sin_w + cos_o * cos_w * cos_i
    R31 = sin_w * sin_i
    R32 = cos_w * sin_i

    # Преобразуем координаты положения
    X = R11 * x_orb + R12 * y_orb
    Y = R21 * x_orb + R22 * y_orb
    Z = R31 * x_orb + R32 * y_orb

    # Преобразуем компоненты скорости
    Vx = R11 * vx_orb + R12 * vy_orb
    Vy = R21 * vx_orb + R22 * vy_orb
    Vz = R31 * vx_orb + R32 * vy_orb

    return [X, Y, Z], [Vx, Vy, Vz]


# Добавить в конец файла kepler_converter.py

def parse_omm_csv_string(csv_header, csv_data_line):
    """
    Парсит OMM CSV строку с сайта Celestrak.
    Рассчитывает большую полуось 'a' через MEAN_MOTION и возвращает словарь элементов.
    """
    try:
        headers = [h.strip().upper() for h in csv_header.split(',')]
        values = [v.strip() for v in csv_data_line.split(',')]

        if len(headers) != len(values):
            return None

        # Создаем словарь для удобного поиска по именам колонок
        data = dict(zip(headers, values))

        # Вытаскиваем элементы
        norad_id = data.get("NORAD_CAT_ID")
        name = data.get("OBJECT_NAME", f"Sat {norad_id}")
        epoch = data.get("EPOCH", "Unknown")

        e = float(data["ECCENTRICITY"])
        i = float(data["INCLINATION"])
        omega = float(data["RA_OF_ASC_NODE"])
        w = float(data["ARG_OF_PERICENTER"])
        M = float(data["MEAN_ANOMALY"])

        # Закон Кеплера: вычисляем большую полуось 'a' из среднего движения (Mean Motion - оборотов в сутки)
        mean_motion = float(data["MEAN_MOTION"])
        # Переводим обороты/сутки в радианы/сек
        n_rad_sec = (mean_motion * 2.0 * 3.141592653589793) / 86400.0
        MU = 398600.4418  # км³/с²
        a = (MU / (n_rad_sec ** 2)) ** (1.0 / 3.0)

        return {
            "norad_id": norad_id,
            "name": name,
            "epoch": epoch,
            "a": round(a, 2),
            "e": e,
            "i": i,
            "omega": omega,
            "w": w,
            "M": M
        }
    except Exception as ex:
        print(f"Ошибка парсинга OMM CSV: {ex}")
        return None

