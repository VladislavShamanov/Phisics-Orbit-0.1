# main.py
import requests
from gost_model import calculate_density


def get_current_space_weather():
    """
    Финальная надежная версия парсера космической погоды с GFZ Potsdam.
    Использует обратную индексацию для точного поиска параметров.
    """

    url = "https://www-app3.gfz-potsdam.de/kp_index/Kp_ap_Ap_SN_F107_nowcast.txt"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print("⚠️ Ошибка сервера: Сервер GFZ Potsdam недоступен. Применяем дефолт.")
            return 150.0, 4.0

        lines = response.text.strip().split('\n')

        # Перебираем строки с конца файла
        for line in reversed(lines):
            line = line.strip()

            # Игнорируем комментарии и пустые строки
            if line.startswith('#') or not line:
                continue

            parts = line.split()

            # Строка данных в GFZ всегда содержит очень много колонок (около 31-33)
            if len(parts) < 30:
                continue

            # Проверяем, что первая колонка - это действительно год (например, 2026)
            try:
                year = int(parts[0])
                if year < 1932 or year > 2100:  # Защита от случайных чисел в тексте
                    continue
            except ValueError:
                continue  # Если первый элемент не число - это текстовый подвал, пропускаем

            try:
                # В структуре GFZ Nowcast:
                # Самая последняя колонка (индекс -1) - наблюдаемый F10.7
                # Колонка перед ней (индекс -2) - среднесуточный индекс Ap
                f107 = float(parts[-1])
                ap = float(parts[-2])

                # Если данные за текущие сутки ещё не успели обновиться (маркируются как -1.0)
                if f107 < 0 or ap < 0:
                    continue

                print(f"📡 API Успех! Получены живые индексы за дату: {parts[0]}-{parts[1]}-{parts[2]}")
                return f107, ap

            except (ValueError, IndexError):
                continue

    except Exception as e:
        print(f"⚠️ Ошибка сети при запросе к API: {e}. Применяем дефолт.")

    return 150.0, 4.0


if __name__ == "__main__":
    print("=" * 50)
    print("Запуск динамической модели верхней атмосферы Земли...")
    print("=" * 50)

    # 1. Запрашиваем из интернета реальные параметры Солнца и Земли на сегодня!
    f107_current, ap_current = get_current_space_weather()
    print(f"Текущие параметры космоса:")
    print(f"  -> Индекс солнечной активности (F10.7) = {f107_current}")
    print(f"  -> Геомагнитный индекс (Ap) = {ap_current}")

    # В ГОСТе также требуется Kp (баллы). Для спокойного Ap=4 он равен ~1.0.
    # В будущем мы сможем парсить Kp напрямую из этого же файла (он лежит в parts[22])
    kp_current = 1.0
    if ap_current > 4:
        # Простая аппроксимация для теста, если буря начнется
        kp_current = 3.0

        # 2. Вызываем наше скомпилированное C++ ядро ГОСТа!
    height = 400.0  # Высота орбиты, км (уровень МКС)
    day_of_year = 140.0  # Примерный день года

    # Передаем живые данные в DLL: height, f107, f107_avg, ap, day_of_year
    density = calculate_density(
        height,
        f107_current,
        f107_current,  # Для теста используем текущий как средний
        kp_current,
        day_of_year
    )

    print("-" * 50)
    print(f"Результат расчета ГОСТ Р 25645.166 на высоте {height} км:")
    print(f"Истинная плотность атмосферы: {density:.4e} кг/м³")
    print("=" * 50)
