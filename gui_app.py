import wx
import wx.adv
import wx.grid
import json
import os
import math
from datetime import datetime

import matplotlib

matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure

from orbit_propagator import save_grid_to_csv
from gost_model import calculate_density
from kepler_converter import kepler_to_cartesian, parse_omm_csv_string


class OrbitControlFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title="🚀 Phisics-Orbit-0.1: Баллистический OMM/JSON комплекс", size=(1150, 750))

        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ЛЕВАЯ ПАНЕЛЬ
        left_panel = wx.Panel(panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Статус
        status_box = wx.StaticBox(left_panel, label="🛰 Мониторинг")
        status_sizer = wx.StaticBoxSizer(status_box, wx.VERTICAL)
        self.weather_label = wx.StaticText(left_panel, label="🟢 База данных автономна. Готова к расчету сценариев.")
        self.weather_label.SetForegroundColour(wx.Colour(0, 128, 0))
        status_sizer.Add(self.weather_label, 0, wx.ALL, 5)
        left_sizer.Add(status_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.input_notebook = wx.Notebook(left_panel)

        # Вкладка А: Управление Библиотекой Сценариев
        tab_json = wx.Panel(self.input_notebook)
        json_sizer = wx.BoxSizer(wx.VERTICAL)

        json_sizer.Add(wx.StaticText(tab_json, label="1. Выберите спутник:"), 0, wx.ALL, 5)
        self.sat_listbox = wx.ListBox(tab_json, style=wx.LB_SINGLE)
        self.sat_listbox.Bind(wx.EVT_LISTBOX, self.on_satellite_selected)
        json_sizer.Add(self.sat_listbox, 1, wx.EXPAND | wx.ALL, 5)

        json_sizer.Add(wx.StaticText(tab_json, label="2. Выберите эпоху/сценарий:"), 0, wx.ALL, 5)
        self.epoch_listbox = wx.ListBox(tab_json, style=wx.LB_SINGLE, size=(-1, 100))
        self.epoch_listbox.Bind(wx.EVT_LISTBOX, self.on_epoch_selected)
        json_sizer.Add(self.epoch_listbox, 0, wx.EXPAND | wx.ALL, 5)

        tab_json.SetSizer(json_sizer)

        # Вкладка Б: Элементы Кеплера (Текущие параметры расчета)
        tab_kep = wx.Panel(self.input_notebook)
        kep_grid = wx.FlexGridSizer(7, 2, 5, 5)
        kep_labels = ["Полуось a (км):", "Эксцентриситет e:", "Наклонение i (°):", "Узел Ω (°):", "Перицентр ω (°):",
                      "Аномалия M (°)", "Эпоха (Текст):"]
        self.kep_inputs = {}
        for label_text in kep_labels:
            lbl = wx.StaticText(tab_kep, label=label_text)
            txt = wx.TextCtrl(tab_kep, value="6771.0" if "полуось" in label_text.lower() else "0.0")
            kep_grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            kep_grid.Add(txt, 1, wx.EXPAND)
            self.kep_inputs[label_text] = txt
        kep_grid.AddGrowableCol(1, 1)
        tab_kep.SetSizer(kep_grid)

        # Вкладка В: Мгновенный Импорт OMM CSV с сайта Celestrak!
        tab_csv = wx.Panel(self.input_notebook)
        csv_sizer = wx.BoxSizer(wx.VERTICAL)
        csv_sizer.Add(wx.StaticText(tab_csv, label="Вставьте шапку OMM CSV с сайта:"), 0, wx.ALL, 2)
        self.csv_hdr_input = wx.TextCtrl(tab_csv,
                                         value="OBJECT_NAME,OBJECT_ID,EPOCH,MEAN_MOTION,ECCENTRICITY,INCLINATION,RA_OF_ASC_NODE,ARG_OF_PERICENTER,MEAN_ANOMALY,NORAD_CAT_ID")
        csv_sizer.Add(self.csv_hdr_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        csv_sizer.Add(wx.StaticText(tab_csv, label="Вставьте строку данных спутника:"), 0, wx.ALL, 2)
        self.csv_data_input = wx.TextCtrl(tab_csv, style=wx.TE_MULTILINE,
                                          value="OBJECT C,2023-091C,2026-05-22T17:26:00.243744,15.26057255,.0011356,97.5035,204.9400,188.2024,171.9031,0,U,57168")
        csv_sizer.Add(self.csv_data_input, 1, wx.EXPAND | wx.ALL, 5)

        import_btn = wx.Button(tab_csv, label="⚡ МГНОВЕННО ИМПОРТИРОВАТЬ В БАЗУ")
        import_btn.Bind(wx.EVT_BUTTON, self.on_import_omm_csv_click)
        csv_sizer.Add(import_btn, 0, wx.EXPAND | wx.ALL, 5)
        tab_csv.SetSizer(csv_sizer)

        self.input_notebook.AddPage(tab_json, "Библиотека")
        self.input_notebook.AddPage(tab_kep, "Параметры Кеплера")
        self.input_notebook.AddPage(tab_csv, "Импорт OMM CSV")
        left_sizer.Add(self.input_notebook, 1, wx.EXPAND | wx.ALL, 10)

        # Кнопка сохранения правок
        self.save_db_btn = wx.Button(left_panel, label="💾 СОХРАНИТЬ ТЕКУЩИЕ ПРАВКИ КАК СЦЕНАРИЙ")
        self.save_db_btn.Bind(wx.EVT_BUTTON, self.on_save_scenario_to_json)
        left_sizer.Add(self.save_db_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Блок шага
        step_box = wx.StaticBox(left_panel, label="⏱ Шаг симуляции")
        step_sizer = wx.StaticBoxSizer(step_box, wx.HORIZONTAL)
        step_sizer.Add(wx.StaticText(left_panel, label="Шаг расчета (сек):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.step_input = wx.TextCtrl(left_panel, value="120")
        step_sizer.Add(self.step_input, 1, wx.EXPAND)
        left_sizer.Add(step_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.run_btn = wx.Button(left_panel, label="🚀 ЗАПУСТИТЬ МОДЕЛИРОВАНИЕ")
        self.run_btn.SetBackgroundColour(wx.Colour(2, 132, 199))
        self.run_btn.SetForegroundColour(wx.WHITE)
        self.run_btn.Bind(wx.EVT_BUTTON, self.on_run_simulation)
        left_sizer.Add(self.run_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        left_panel.SetSizer(left_sizer)

        # ПРАВАЯ ПАНЕЛЬ
        self.right_notebook = wx.Notebook(panel)
        self.tab_graph = wx.Panel(self.right_notebook)
        graph_sizer = wx.BoxSizer(wx.VERTICAL)
        self.figure = Figure(figsize=(5, 4), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self.tab_graph, -1, self.figure)
        graph_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)
        self.tab_graph.SetSizer(graph_sizer)

        tab_table = wx.Panel(self.right_notebook)
        table_sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid = wx.grid.Grid(tab_table)
        self.grid.CreateGrid(0, 5)
        self.grid.SetColLabelValue(0, "Время")
        self.grid.SetColLabelValue(1, "Высота (км)")
        self.grid.SetColLabelValue(2, "Широта")
        self.grid.SetColLabelValue(3, "Долгота")
        self.grid.SetColLabelValue(4, "Плотность (кг/м³)")
        table_sizer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 5)

        self.export_btn = wx.Button(tab_table, label="📥 Экспортировать данные в CSV")
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export_click)
        table_sizer.Add(self.export_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        tab_table.SetSizer(table_sizer)

        self.right_notebook.AddPage(self.tab_graph, "Графический анализ")
        self.right_notebook.AddPage(tab_table, "Таблица данных")

        main_sizer.Add(left_panel, 0, wx.EXPAND)
        main_sizer.Add(self.right_notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)

        self.load_satellites_from_json()
        self.Show()

    def load_satellites_from_json(self):
        self.sat_listbox.Clear()
        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                self.sat_data = json.load(f)
                for norad_id, info in self.sat_data.items():
                    idx = self.sat_listbox.Append(f"{info['name']} (NORAD: {norad_id})")
                    self.sat_listbox.SetClientData(idx, info)
                if self.sat_listbox.GetCount() > 0:
                    self.sat_listbox.SetSelection(0)
                    self.on_satellite_selected(None)

    def on_satellite_selected(self, event):
        """При выборе спутника заполняет список его эпох/истории"""
        idx = self.sat_listbox.GetSelection()
        if idx == wx.NOT_FOUND: return
        info = self.sat_listbox.GetClientData(idx)

        self.epoch_listbox.Clear()
        if 'history' in info:
            for ep_idx, ep in enumerate(info['history']):
                self.epoch_listbox.Append(f"Эпоха: {ep['epoch']} ({ep.get('comment', 'Без описания')})", ep)
            if self.epoch_listbox.GetCount() > 0:
                self.epoch_listbox.SetSelection(0)
                self.on_epoch_selected(None)

    def on_epoch_selected(self, event):
        """При выборе эпохи раскидывает элементы в поля ввода Кеплера"""
        idx = self.epoch_listbox.GetSelection()
        if idx == wx.NOT_FOUND: return
        ep = self.epoch_listbox.GetClientData(idx)

        self.kep_inputs["Полуось a (км):"].SetValue(str(ep['a']))
        self.kep_inputs["Эксцентриситет e:"].SetValue(str(ep['e']))
        self.kep_inputs["Наклонение i (°):"].SetValue(str(ep['i']))
        self.kep_inputs["Узел Ω (°):"].SetValue(str(ep['omega']))
        self.kep_inputs["Перицентр ω (°):"].SetValue(str(ep['w']))
        self.kep_inputs["Аномалия M (°)"].SetValue(str(ep['M']))
        self.kep_inputs["Эпоха (Текст):"].SetValue(str(ep['epoch']))

    def on_import_omm_csv_click(self, event):
        """Мгновенно парсит CSV строку с Celestrak и добавляет как новый сценарий"""
        hdr = self.csv_hdr_input.GetValue().strip()
        data_line = self.csv_data_input.GetValue().strip().split('\n')[-1]  # берем последнюю строку данных

        res = parse_omm_csv_string(hdr, data_line)
        if res is None:
            wx.MessageBox("Ошибка парсинга! Проверьте структуру колонок и строки данных.", "Ошибка CSV",
                          wx.OK | wx.ICON_ERROR)
            return

        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        norad_str = str(res['norad_id'])

        # Если такого спутника еще нет в базе, создаем его родительскую карточку
        # Если такого спутника еще нет в базе, создаем его родительскую карточку
        if norad_str not in self.sat_data:
            self.sat_data[norad_str] = {"name": res['name'], "history": []}

        # Добавляем новую эпоху в историю этого спутника!
        new_epoch = {
            "epoch": res['epoch'],
            "comment": f"Импорт OMM CSV за {res['epoch'][:10]}",
            "a": res['a'], "e": res['e'], "i": res['i'],
            "omega": res['omega'], "w": res['w'], "M": res['M']
        }
        self.sat_data[norad_str]['history'].append(new_epoch)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sat_data, f, ensure_ascii=False, indent=2)

        self.load_satellites_from_json()
        # Автоматически переключаем фокус на вкладку Библиотеки, чтобы увидеть результат
        self.input_notebook.SetSelection(0)
        wx.MessageBox(f"Сценарий для ИСЗ '{res['name']}' успешно импортирован без ожидания почты!", "Триумф API",
                      wx.OK | wx.ICON_INFORMATION)

    def on_save_scenario_to_json(self, event):
        """Сохраняет текущие экранные параметры как новый сценарий для выбранного спутника"""
        sat_idx = self.sat_listbox.GetSelection()
        if sat_idx == wx.NOT_FOUND: return
        info = self.sat_listbox.GetClientData(sat_idx)

        new_ep = {
            "epoch": self.kep_inputs["Эпоха (Текст):"].GetValue().strip(),
            "comment": "Пользовательский сценарий правок",
            "a": float(self.kep_inputs["Полуось a (км):"].GetValue()),
            "e": float(self.kep_inputs["Эксцентриситет e:"].GetValue()),
            "i": float(self.kep_inputs["Наклонение i (°):"].GetValue()),
            "omega": float(self.kep_inputs["Узел Ω (°):"].GetValue()),
            "w": float(self.kep_inputs["Перицентр ω (°):"].GetValue()),
            "M": float(self.kep_inputs["Аномалия M (°)"].GetValue())
        }

        for norad_id, data in self.sat_data.items():
            if data['name'] == info['name']:
                self.sat_data[norad_id]['history'].append(new_ep)
                break

        json_path = os.path.join(os.path.dirname(__file__), 'satellites.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.sat_data, f, ensure_ascii=False, indent=2)

        self.load_satellites_from_json()
        wx.MessageBox("Сценарий сохранен в историю спутника!", "Успех", wx.OK | wx.ICON_INFORMATION)

    def on_export_click(self, event):
        if self.grid.GetNumberRows() == 0: return
        with wx.FileDialog(self, "Сохранить баллистические данные", wildcard="CSV файлы (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL: return
            if save_grid_to_csv(dlg.GetPath(), self.grid):
                wx.MessageBox("Данные успешно экспортированы!", "Успех", wx.OK | wx.ICON_INFORMATION)

    def on_run_simulation(self, event):
        try:
            step_sec = int(self.step_input.GetValue())
        except:
            step_sec = 120

        try:
            a = float(self.kep_inputs["Полуось a (км):"].GetValue())
            e = float(self.kep_inputs["Эксцентриситет e:"].GetValue())
            i = float(self.kep_inputs["Наклонение i (°):"].GetValue())
            omega = float(self.kep_inputs["Узел Ω (°):"].GetValue())
            w = float(self.kep_inputs["Перицентр ω (°):"].GetValue())
            M = float(self.kep_inputs["Аномалия M (°)"].GetValue())

            pos, vel = kepler_to_cartesian(a, e, i, omega, w, M)

            orbit_points = []
            for step_idx in range(int(45 * 60 / step_sec)):
                nu_step = math.radians(M) + (step_idx * step_sec * 0.00111)
                r_step = a * (1.0 - e * math.cos(nu_step))
                lat_step = i * math.sin(nu_step)
                lon_step = (omega + math.degrees(nu_step)) % 360.0
                if lon_step > 180: lon_step -= 360.0

                from datetime import timedelta
                sim_time = datetime.utcnow() + timedelta(seconds=step_idx * step_sec)
                orbit_points.append({'time': sim_time.strftime("%H:%M:%S"), 'height': r_step - 6371.0, 'lat': lat_step,
                                     'lon': lon_step})
        except Exception as ex:
            wx.MessageBox(f"Ошибка Кеплера: {ex}")
            return

        if self.grid.GetNumberRows() > 0: self.grid.DeleteRows(0, self.grid.GetNumberRows())
        self.axes.clear()
        x_time, y_density = [], []

        for i, pt in enumerate(orbit_points):
            density = 0.0 if pt['height'] > 1500.0 else calculate_density(pt['height'], 150.0, 150.0, 1.0, 140.0)

            # Расчет магнитного поля IGRF-13
            from magnetic_model import calculate_magnetic_field
            mag_field = calculate_magnetic_field(pt['height'], pt['lat'], pt['lon'], datetime.utcnow())
            if i % 5 == 0:
                print(f"Точка {i}: Высота={pt['height']:.1f}км, Магнитное поле B={mag_field['B']:.1f} нТл")

            x_time.append(i * step_sec)
            y_density.append(density)

            self.grid.AppendRows(1)
            row = self.grid.GetNumberRows() - 1
            self.grid.SetCellValue(row, 0, pt['time'])
            self.grid.SetCellValue(row, 1, f"{pt['height']:.2f}")
            self.grid.SetCellValue(row, 2, f"{pt['lat']:.2f}")
            self.grid.SetCellValue(row, 3, f"{pt['lon']:.2f}")
            self.grid.SetCellValue(row, 4, f"{density:.4e}")

        self.axes.plot(x_time, y_density, color='#0284c7', linewidth=2)
        self.axes.set_title("Профиль плотности атмосферы")
        self.axes.set_xlabel("Время полета (сек)")
        self.axes.set_ylabel("Плотность, кг/м³")
        self.axes.grid(True)
        self.canvas.draw()
        wx.Bell()


if __name__ == "__main__":
    app = wx.App()
    frame = OrbitControlFrame()
    app.MainLoop()
