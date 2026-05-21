# main.py
from gost_model import calculate_density

if __name__ == "__main__":
    # Высота 400 км, F107=150, F81=150, Kp=1.0, День=140
    density = calculate_density(400.0, 150.0, 150.0, 1.0, 140.0)
    print(f"Истинная плотность по ГОСТ: {density:.4e} кг/м³")
