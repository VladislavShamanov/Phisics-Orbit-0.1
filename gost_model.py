# gost_model.py
import ctypes
import os

dll_path = os.path.join(os.path.dirname(__file__), 'gost_model.dll')
_lib = ctypes.CDLL(dll_path)

# Указываем 5 параметров c_double на входе
_lib.get_density.argtypes = [
    ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double
]
_lib.get_density.restype = ctypes.c_double

def calculate_density(height, f107, f81, kp, day_of_year):
    return _lib.get_density(height, f107, f81, kp, day_of_year)
