# ui/timeline_widget.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsItem
)
from PyQt5.QtCore import pyqtSignal, QObject, QRectF, QPointF, Qt # Добавлен Qt для FocusPolicy
from PyQt5.QtGui import QColor, QPen, QBrush, QPainter
from model.project import GenericLabel, CalculatedRange # Импортируем нужные классы из модели проекта

# --- визуальные параметры: Цвета,толщины, высоты ---
COLOR_MAPPING = {
    "Сегмент": QColor(0, 0, 255, 100),  # Синий
    "Пауза": QColor(255, 0, 0, 200),    # Красный
    "ЧИИ": QColor(0, 255, 0, 160),      # Зелёный
    "Всё видео": QColor(128, 128, 128, 100), # Серый
    "Смена": QColor(255, 165, 0, 100),  # Оранжевый 
    "Гол": QColor(0, 0, 0, 250),        # Черный
    "Удаление": QColor(238, 255, 25, 190), #Желтый
    "Черн.FOOTAGE": QColor(0, 100, 0, 100), # Темнозелёный
    "Черн.OSD": QColor(0, 0, 0, 250), # Светлозелёный
    "game_mode": QColor(74, 254, 249, 100), # Голубой
}
DEFAULT_COLOR = QColor(128, 128, 128, 100) # Серый по умолчанию

# --- НОВОЕ: Толщина линий для TimelineLabel ---
LINE_WIDTH_MAPPING = {
    "Сегмент": 4,
    "Пауза": 2,
    "ЧИИ": 1,
    "Всё видео": 1, # Для линии, если она отображается как TimelineLabel
    "Смена": 1,
    "Гол": 1, # Пример
    "Удаление": 4, #Желтый и толстый
    "Черн.FOOTAGE": 2, # Пример
    "Черн.OSD": 2, # Пример
    "game_mode": 2,
}
DEFAULT_LINE_WIDTH = 2 # Толщина по умолчанию
# --- КОНЕЦ НОВОГО ---

# --- НОВОЕ: Высота TimelineLabel ---
LABEL_HEIGHT_MAPPING = {
    "Сегмент": 145,
    "Пауза": 100,
    "ЧИИ": 100,
    "Всё видео": 100, # Для линии, если она отображается как TimelineLabel
    "Смена": 115,
    "Гол": 140, # Пример
    "Удаление": 125,
    "Черн.FOOTAGE": 60, # Пример
    "Черн.OSD": 90, # Пример
}
DEFAULT_LABEL_HEIGHT = 100 # Высота по умолчанию
# --- КОНЕЦ НОВОГО ---

# --- НОВОЕ: Высота TimelineRange ---
RANGE_HEIGHT_MAPPING = {
    "Сегмент": 50,
    "Пауза": 30,
    "ЧИИ": 40,
    "Всё видео": 60, # Пример
    "Смена": 30,
    "Гол": 20, # Пример
    "Удаление": 30,
    "game_mode": 80,
}
DEFAULT_RANGE_HEIGHT = 40 # Высота по умолчанию
# --- КОНЕЦ НОВОГО ---

# --- Визуальные элементы для отображения на шкале ---

class TimelineLabel(QGraphicsItem):
    """QGraphicsItem для отображения GenericLabel как вертикальной линии/стрелки."""
    def __init__(self, generic_label: GenericLabel):
        super().__init__()
        self.generic_label = generic_label
        self._color = self._get_color_for_label_type(generic_label.label_type)
        # --- НОВОЕ: Получаем высоту из мэппинга ---
        self._height = LABEL_HEIGHT_MAPPING.get(generic_label.label_type, DEFAULT_LABEL_HEIGHT)
        # --- КОНЕЦ НОВОГО ---

        # Устанавливаем всплывающую подсказку, используя новую функцию
        tooltip_text = self._format_generic_label_tooltip(generic_label)
        self.setToolTip(tooltip_text)

        
    def _format_generic_label_tooltip(self, generic_label: GenericLabel) -> str:
        """
        Создаёт текст всплывающей подсказки для GenericLabel в зависимости от его типа и context.
        """
        label_type = generic_label.label_type
        global_time = generic_label.global_time
        context = generic_label.context or {} # Защита от None

        if label_type == "Гол":
            player_name = context.get("player_name", "Unknown Player")
            f_pass = context.get("f-pass", "N/A")
            s_pass = context.get("s-pass", "N/A")
            return f"{player_name} ({f_pass}, {s_pass})\nTime: {global_time:.1f}s"
        elif label_type == "Удаление":
            team = context.get("team", "Unknown Team")
            player_name = context.get("player_name", "Unknown Player")
            return f"{team}: {player_name}\nTime: {global_time:.1f}s"
        else:
            # Стандартный формат для остальных типов меток
            return f"Label: {label_type}\nTime: {global_time:.1f}s"
    # --- Конец нового метода ---

    def _get_color_for_label_type(self, label_type: str) -> QColor:
        """Возвращает цвет для label_type из COLOR_MAPPING или DEFAULT_COLOR."""
        return COLOR_MAPPING.get(label_type, DEFAULT_COLOR)

    def boundingRect(self) -> QRectF:
        """Определяет область, занимаемую элементом. Пока фиксированная высота, ширина = 1 пиксель."""
        # Пусть высота будет 100 пикселей, ширина 1 пиксель
        # X и Y будут устанавливаться при позиционировании на сцене
        # Пока используем 0, 0 как центр, корректируем в paint
        height = self._height # Соответствует высоте TimelineView
        width = 1
        # QRectF принимает (x, y, width, height). Центрируем относительно (0,0)
        return QRectF(-width / 2, -height / 2, width, height)

    def paint(self, painter: QPainter, option, widget=None):
        """Отрисовывает вертикальную линию."""
        # --- НОВОЕ: Получаем толщину линии из мэппинга ---
        line_width = LINE_WIDTH_MAPPING.get(self.generic_label.label_type, DEFAULT_LINE_WIDTH)
        pen = QPen(self._color, line_width) # <-- Используем динамическую толщину
        # --- КОНЕЦ НОВОГО ---
        #pen = QPen(self._color, 2)
        painter.setPen(pen)
        # Используем QPointF для координат, чтобы избежать ошибки TypeError
        p1 = QPointF(0, -self.boundingRect().height() / 2)
        p2 = QPointF(0, self.boundingRect().height() / 2)
        painter.drawLine(p1, p2)

    def update_position(self, x_pos: float, y_pos: float = 0):
        """Обновляет позицию элемента на сцене."""
        self.setPos(x_pos, y_pos)

    def update_color(self):
        """Обновляет цвет элемента."""
        self._color = self._get_color_for_label_type(self.generic_label.label_type)


class TimelineRange(QGraphicsItem):
    """QGraphicsItem для отображения CalculatedRange как прямоугольника."""
    def __init__(self, calculated_range: CalculatedRange):
        super().__init__()
        self.calculated_range = calculated_range
        self._color = self._get_color_for_label_type(calculated_range.label_type)
        self._border_color = self._color.darker(150) # Немного темнее для границы
        # --- НОВОЕ: Получаем высоту из мэппинга ---
        self._height = RANGE_HEIGHT_MAPPING.get(calculated_range.label_type, DEFAULT_RANGE_HEIGHT)
        # --- КОНЕЦ НОВОГО ---

        # Устанавливаем всплывающую подсказку
        #self.setToolTip(f"Range: {calculated_range.name}\nType: {calculated_range.label_type}\nStart: {calculated_range.start_time:.3f}s\nEnd: {calculated_range.end_time:.3f}s\nDuration: {calculated_range.end_time - calculated_range.start_time:.3f}s")
        # Формируем основную часть подсказки
        #tooltip_parts = [f"Range: {calculated_range.name}"]
        tooltip_parts = [f"{calculated_range.name}"]

        # Добавляем информацию об активных штрафах из context, если она есть
        active_penalties = getattr(calculated_range, 'context', {}).get('active_penalties', [])
        if active_penalties:
            tooltip_parts.append("Active Penalties:")
            for penalty in active_penalties:
                team = penalty.get('team', 'Unknown team')
                player_name = penalty.get('player_name', 'Unknown player')
                tooltip_parts.append(f"  {team}: {player_name}")
        # Собираем финальную строку подсказки
        self.setToolTip("\n".join(tooltip_parts))       


        # --- Храним ширину и высоту для отрисовки ---
        self._width = 100 # Временное значение
        #self._height = 40

    def _get_color_for_label_type(self, label_type: str) -> QColor:
        """Возвращает цвет для label_type из COLOR_MAPPING или DEFAULT_COLOR."""
        return COLOR_MAPPING.get(label_type, DEFAULT_COLOR)

    def boundingRect(self) -> QRectF:
        """Определяет область, занимаемую элементом. Использует динамически заданные размеры."""
        # Пусть высота будет 40 пикселей
        # Ширина будет определяться start_time и end_time в глобальных координатах и масштабе
        # X и Y будут устанавливаться при позиционировании
        # boundingRect теперь от (0, -height/2) до (width, height/2) относительно pos()
        return QRectF(0, -self._height / 2, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None):
        """Отрисовывает прямоугольник и текст."""
        brush = QBrush(self._color)
        # --- НОВОЕ: Получаем толщину границы из мэппинга (опционально, можно отдельный мэппинг) ---
        # border_width = RANGE_BORDER_WIDTH_MAPPING.get(self.calculated_range.label_type, 1) # Если нужен отдельный мэппинг
        pen = QPen(self._border_color, 1) # Пока оставим 1, можно изменить
        # --- КОНЕЦ НОВОГО ---
        painter.setBrush(brush)
        painter.setPen(pen)

        # rect = self.boundingRect() # Используем динамически заданные размеры
        # Рисуем прямоугольник с динамической высотой и шириной
        rect = QRectF(0, -self._height / 2, self._width, self._height) # <-- Используем динамическую высоту
        painter.drawRect(rect)

        # Рисуем текст
        painter.setPen(QPen(QColor(0, 0, 0))) # Чёрный цвет текста
        # Qt.AlignCenter = 132. Используем 132 для выравнивания по центру
        painter.drawText(rect, 132, self.calculated_range.name)


    def update_position(self, x_start: float, x_end: float, y_pos: float = 0):
        """Обновляет позицию и размер элемента на сцене."""
        width = x_end - x_start
        height = self._height # Используем сохранённую динамическую высоту
        # Устанавливаем позицию левого верхнего угла элемента
        self.setPos(x_start, y_pos)
        # Обновляем внутреннюю ширину
        old_width = self._width
        self._width = width
        # Если ширина изменилась, нужно сообщить сцене о смене геометрии
        if abs(old_width - width) > 0.001: # Проверка на изменение
            self.prepareGeometryChange()
        # print(f"[DEBUG] TimelineRange.update_position: setPos({x_start}, {y_pos}), width={width}, height={height}, boundingRect={self.boundingRect()}") # DEBUG



    def update_color(self):
        """Обновляет цвет элемента."""
        self._color = self._get_color_for_label_type(self.calculated_range.label_type)
        self._border_color = self._color.darker(150)


# --- Вспомогательные классы View и Scene ---
class TimelineView(QGraphicsView):
    """QGraphicsView для отображения TimelineScene."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Пока без специфичной логики, кроме базовой инициализации
        # Убираем прокрутку, чтобы шкала отображалась как один элемент
        self.setHorizontalScrollBarPolicy(1) # Qt.ScrollBarAlwaysOff
        self.setVerticalScrollBarPolicy(1) # Qt.ScrollBarAlwaysOff
        # Устанавливаем фиксированную высоту для области просмотра
        self.setFixedHeight(150) # Можно настроить позже

    def setScene(self, scene: 'TimelineScene'):
        """Устанавливает сцену и передаёт ссылку на TimelineWidget."""
        # Сначала устанавливаем сцену через родительский метод
        super().setScene(scene)
        # Теперь сцена установлена, можно получить родителя (TimelineWidget)
        # и установить ему ссылку на себя (TimelineScene)
        parent_widget = self.parent() # Получаем родителя QGraphicsView, т.е. TimelineWidget
        if parent_widget and isinstance(parent_widget, TimelineWidget) and scene:
            # Устанавливаем связь сцены с TimelineWidget
            scene.set_timeline_widget(parent_widget)

    def mousePressEvent(self, event):
        """Обрабатывает клик по шкале для навигации."""
        # Получаем позицию клика в координатах сцены
        scene_pos = self.mapToScene(event.pos())
        x_scene = scene_pos.x()

        # Получаем TimelineWidget через родителя
        timeline_widget = self.parent()
        if not timeline_widget or not isinstance(timeline_widget, TimelineWidget):
            #print("[DEBUG] TimelineView.mousePressEvent: Не могу получить TimelineWidget.")
            return

        # Получаем данные о текущем активном диапазоне из TimelineWidget
        active_start = timeline_widget.active_start_time
        active_end = timeline_widget.active_end_time
        view_width = self.width()

        # Вычисляем масштаб (пиксели в секунду) для текущего активного диапазона
        active_duration = active_end - active_start
        if view_width > 0 and active_duration > 0:
            view_width_per_sec = view_width / active_duration
        else:
            # Если диапазон 0 или ширина 0, масштаб не определён. Прерываем.
            #print(f"[DEBUG] TimelineView.mousePressEvent: Невозможно вычислить масштаб. view_width: {view_width}, active_duration: {active_duration}")
            return

        # Вычисляем глобальное время по X-координате клика
        # Формула: глобальное_время = (X_клика / view_width_per_sec) + active_start_time
        calculated_global_time = (x_scene / view_width_per_sec) + active_start

        # Проверяем, находится ли вычисленное время в пределах активного диапазона
        if active_start <= calculated_global_time <= active_end:
            #print(f"[DEBUG] TimelineView.mousePressEvent: Клик на X={x_scene}, вычислено глобальное время {calculated_global_time:.3f}s. В пределах диапазона ({active_start} - {active_end}).")
            # Эмитируем сигнал навигации через TimelineWidget
            timeline_widget.globalTimeRequested.emit(calculated_global_time)
        else:
            pass#print(f"[DEBUG] TimelineView.mousePressEvent: Клик на X={x_scene}, вычислено глобальное время {calculated_global_time:.3f}s. Вне активного диапазона ({active_start} - {active_end}). Игнорируем.")


class TimelineScene(QGraphicsScene):
    """QGraphicsScene для отображения элементов шкалы и индикатора времени."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Ссылка на TimelineWidget для доступа к данным и настройкам
        self.timeline_widget: 'TimelineWidget' = None

        # Элемент для индикатора текущего времени
        self.current_time_indicator: QGraphicsLineItem = None
        # Настройка пера для индикатора (можно уточнить позже)
        self.current_time_indicator_pen = QPen(QColor(0, 0, 255), 4) # Синяя линия

        # Словари для хранения элементов шкалы (TimelineLabel, TimelineRange)
        # Ключ - id соответствующего GenericLabel или CalculatedRange
        # Эти словари будут заполняться и использоваться в redraw
        self.timeline_items_generic: dict[str, TimelineLabel] = {}
        self.timeline_items_calculated: dict[str, TimelineRange] = {}

    def set_timeline_widget(self, widget: 'TimelineWidget'):
        """Устанавливает ссылку на TimelineWidget."""
        self.timeline_widget = widget

 # --- НОВЫЙ метод: Обновление позиции ТОЛЬКО индикатора времени ---
    def update_time_indicator_position(self):
        """Обновляет позицию индикатора текущего времени без перерисовки других элементов."""
        if not self.timeline_widget:
            print("[DEBUG] TimelineScene.update_time_indicator_position(): timeline_widget не установлена.")
            return

        current_time = self.timeline_widget.current_global_time
        active_start = self.timeline_widget.active_start_time
        active_end = self.timeline_widget.active_end_time

        # Удаляем старый индикатор, если он был
        if self.current_time_indicator:
            self.removeItem(self.current_time_indicator)
            self.current_time_indicator = None

        # Если время вне активного диапазона, не рисуем индикатор
        if not (active_start <= current_time <= active_end):
            #print(f"[DEBUG] TimelineScene.update_time_indicator_position(): Время {current_time} вне активного диапазона ({active_start} - {active_end}). Индикатор не рисуется.")
            return # Индикатор не создается/обновляется

        # Вычисляем X-координату индикатора с учётом масштаба
        view_width = self.timeline_widget.view.width()
        active_duration = active_end - active_start
        if view_width > 0 and active_duration > 0:
            relative_pos = (current_time - active_start) / active_duration
            x_pos = relative_pos * view_width
            # Создаём новый индикатор (или можно переиспользовать старый, если он был, и просто setLine)
            self.current_time_indicator = QGraphicsLineItem(0, 0, 0, 100) # Высота 100
            self.current_time_indicator.setPen(self.current_time_indicator_pen)
            self.addItem(self.current_time_indicator)
            self.current_time_indicator.setLine(x_pos, 0, x_pos, 100)
            #print(f"[DEBUG] TimelineScene.update_time_indicator_position(): Индикатор времени установлен на x={x_pos} для времени {current_time}.")
        else:
            pass#print(f"[DEBUG] TimelineScene.update_time_indicator_position(): Невозможно вычислить позицию индикатора. view_width: {view_width}, active_duration: {active_duration}")


    def redraw(self):
        """Перерисовывает сцену: удаляет старые элементы (TimelineLabel, TimelineRange), добавляет новые на основе данных, фильтров и масштаба.
        Логика индикатора времени вынесена в update_time_indicator_position."""
        #print(f"[DEBUG] TimelineScene.redraw() вызван (без индикатора времени).")

        # УДАЛЯЕМ логику удаления и позиционирования индикатора времени из redraw
        # (Вся логика с self.current_time_indicator убирается отсюда)

        # Проверяем, находится ли текущее время в активном диапазоне (для отладки, можно убрать)
        if not self.timeline_widget:
            print("[DEBUG] TimelineScene.redraw(): timeline_widget не установлена.")
            return

        # current_time = self.timeline_widget.current_global_time # Убираем, не нужно для отрисовки элементов
        active_start = self.timeline_widget.active_start_time
        active_end = self.timeline_widget.active_end_time

        # --- Расчёт масштаба ---
        view_width = self.timeline_widget.view.width()
        active_duration = active_end - active_start
        if view_width > 0 and active_duration > 0:
            view_width_per_sec = view_width / active_duration
        else:
            # Если диапазон 0 или ширина 0, масштаб не определён. Примем за 1 для избежания деления на 0.
            view_width_per_sec = 1.0
        #print(f"[DEBUG] TimelineScene.redraw(): view_width_per_sec = {view_width_per_sec}, active_range = ({active_start} - {active_end})")

        # --- Логика отображения элементов шкалы ---
        # 1. Очищаем сцену от старых элементов TimelineLabel и TimelineRange
        # Удаляем только элементы, созданные для отображения меток и диапазонов
        for item in list(self.timeline_items_generic.values()):
            self.removeItem(item)
        for item in list(self.timeline_items_calculated.values()):
            self.removeItem(item)
        # Очищаем словари
        self.timeline_items_generic.clear()
        self.timeline_items_calculated.clear()

        # 2. Получаем данные и фильтры из TimelineWidget
        generic_labels = self.timeline_widget.generic_labels
        calculated_ranges = self.timeline_widget.calculated_ranges
        # Словари фильтров из TimelineWidget
        filter_checkboxes_generic = self.timeline_widget.filter_checkboxes_generic
        filter_checkboxes_calculated = self.timeline_widget.filter_checkboxes_calculated

        # 3. Добавляем TimelineLabel на сцену, если его тип не отфильтрован и он в диапазоне
        for label in generic_labels:
            label_type = label.label_type
            # Проверяем, есть ли чекбокс для этого типа и включён ли он
            if label_type in filter_checkboxes_generic and filter_checkboxes_generic[label_type].isChecked():
                # Проверяем, находится ли метка в активном диапазоне
                if active_start <= label.global_time <= active_end:
                    timeline_label = TimelineLabel(label)
                    # Позиционирование с учётом масштаба и смещения
                    x_pos = (label.global_time - active_start) * view_width_per_sec
                    timeline_label.update_position(x_pos, y_pos=0) # Y пока фиксирован
                    self.addItem(timeline_label)
                    # Сохраняем ссылку для потенциального управления
                    self.timeline_items_generic[label.id] = timeline_label
                    #print(f"[DEBUG] TimelineScene.redraw(): Добавлен TimelineLabel для {label_type} в {label.global_time}s (id: {label.id}) на x={x_pos}")
                else:
                    pass#print(f"[DEBUG] TimelineScene.redraw(): TimelineLabel для {label.label_type} в {label.global_time}s вне активного диапазона ({active_start} - {active_end}). Пропущен.")


        # 4. Добавляем TimelineRange на сцену, если его тип не отфильтрован и он пересекается с диапазоном
        for range_obj in calculated_ranges:
            range_type = range_obj.label_type
            # Проверяем, есть ли чекбокс для этого типа и включён ли он
            if range_type in filter_checkboxes_calculated and filter_checkboxes_calculated[range_type].isChecked():
                # Проверяем, пересекается ли диапазон с активным диапазоном
                if not (range_obj.end_time < active_start or range_obj.start_time > active_end):
                    timeline_range = TimelineRange(range_obj)
                    # Позиционирование с учётом масштаба и смещения
                    x_start = (range_obj.start_time - active_start) * view_width_per_sec
                    x_end = (range_obj.end_time - active_start) * view_width_per_sec
                    timeline_range.update_position(x_start, x_end, y_pos=0) # Y пока фиксирован
                    self.addItem(timeline_range)
                    # Сохраняем ссылку для потенциального управления
                    self.timeline_items_calculated[range_obj.id] = timeline_range
                    #print(f"[DEBUG] TimelineScene.redraw(): Добавлен TimelineRange для {range_type} ({range_obj.start_time}s - {range_obj.end_time}s, id: {range_obj.id}) на x={x_start} - {x_end}")
                else:
                    pass#print(f"[DEBUG] TimelineScene.redraw(): TimelineRange для {range_obj.label_type} ({range_obj.start_time}s - {range_obj.end_time}s) не пересекается с активным диапазоном ({active_start} - {active_end}). Пропущен.")



# --- Основной класс TimelineWidget ---
class TimelineWidget(QWidget):
    """
    Виджет универсальной шкалы времени для Hockey Tagger.
    Отображает метки и диапазоны, синхронизируется с плеером.
    """
    # Сигнал для навигации плеера
    globalTimeRequested = pyqtSignal(float)

     # --- Новые атрибуты для фильтрации типов ---
    # Можно сделать их изменяемыми через метод, если нужно гибко
    ALLOWED_LABEL_TYPES = {"Сегмент", "Пауза", "Смена", "Гол", "Удаление", "Черн.FOOTAGE", "Черн.OSD"} # Пример
    ALLOWED_RANGE_TYPES = {"Всё видео", "Сегмент", "ЧИИ", "Удаление", "game_mode", "Счёт"} # Пример, исключаем "Всё видео", "ЧИИ_СУММА"

    def __init__(self, parent=None):
        super().__init__(parent)

        # --- Инициализация внутренних атрибутов ---
        # Активный диапазон (глобальное время)
        self.active_start_time: float = 0.0
        self.active_end_time: float = 1.0 # Начальное значение, будет обновлено позже
        self.active_range_name: str = "Нет активного диапазона"

        # Текущее глобальное время (для индикатора)
        self.current_global_time: float = 0.0

        # Списки данных для отображения
        self.generic_labels: list[GenericLabel] = []
        self.calculated_ranges: list[CalculatedRange] = []

        # Сцена и представление
        self.scene: TimelineScene = TimelineScene(self)
        self.view: TimelineView = TimelineView(self)
        # Устанавливаем сцену через метод TimelineView, чтобы установилась связь
        self.view.setScene(self.scene)

        # Словари для чекбоксов фильтров
        self.filter_checkboxes_generic: dict[str, QCheckBox] = {}
        self.filter_checkboxes_calculated: dict[str, QCheckBox] = {}

        # --- Установка FocusPolicy ---
        self.setFocusPolicy(Qt.StrongFocus)

        # --- Создание UI ---
        self._setup_ui()

    def _setup_ui(self):
        """Создание и настройка элементов интерфейса."""
        # Основной вертикальный макет
        layout = QVBoxLayout(self)

        # Панель фильтров (вертикальный макет для групп)
        self.filter_layout = QVBoxLayout() # Изменён на QVBoxLayout

        # Группа для фильтров GenericLabel
        self.filter_group_generic = QWidget()
        # --- НОВОЕ: Устанавливаем минимальную высоту для группы ---
        self.filter_group_generic.setMinimumHeight(33) # Пример высоты, подберите по необходимости
        # --- КОНЕЦ НОВОГО ---
        self.filter_layout_generic = QHBoxLayout(self.filter_group_generic) # Макет для чекбоксов меток
        self.filter_layout_generic.addWidget(QLabel("Метки (GenericLabel):")) # Заголовок для группы

        # Группа для фильтров CalculatedRange
        self.filter_group_calculated = QWidget()
        # --- НОВОЕ: Устанавливаем минимальную высоту для группы ---
        self.filter_group_calculated.setMinimumHeight(33) # Пример высоты, подберите по необходимости
        # --- КОНЕЦ НОВОГО ---
        self.filter_layout_calculated = QHBoxLayout(self.filter_group_calculated) # Макет для чекбоксов диапазонов
        self.filter_layout_calculated.addWidget(QLabel("Диапазоны (CalculatedRange):")) # Заголовок для группы

        # Добавление групп на основной макет фильтров (одна под другой)
        self.filter_layout.addWidget(self.filter_group_generic) # Первая строка
        self.filter_layout.addWidget(self.filter_group_calculated) # Вторая строка

        # Добавление элементов на основной макет
        layout.addLayout(self.filter_layout)
        layout.addWidget(self.view)

        # Установка макета
        self.setLayout(layout)

    # --- Новые методы для фильтров ---
    def _create_filter_checkboxes(self):
        """Создаёт чекбоксы фильтров для GenericLabel и CalculatedRange."""
        #print(f"[DEBUG] TimelineWidget._create_filter_checkboxes() вызван.")

        # --- НОВОЕ: Сохраняем старые состояния ---
        old_states_generic = {label_type: checkbox.isChecked() for label_type, checkbox in self.filter_checkboxes_generic.items()}
        old_states_calculated = {label_type: checkbox.isChecked() for label_type, checkbox in self.filter_checkboxes_calculated.items()}
        # --- КОНЕЦ НОВОГО ---

        # Очищаем текущие макеты групп фильтров
        # Удаляем старые чекбоксы
        # --- ИСПРАВЛЕНО: Используем self.filter_layout_generic и self.filter_layout_calculated ---
        for i in reversed(range(self.filter_layout_generic.count())):
            widget = self.filter_layout_generic.itemAt(i).widget()
            if widget and isinstance(widget, QCheckBox):
                widget.setParent(None)
        for i in reversed(range(self.filter_layout_calculated.count())):
            widget = self.filter_layout_calculated.itemAt(i).widget()
            if widget and isinstance(widget, QCheckBox):
                widget.setParent(None)

        # Очищаем словари
        self.filter_checkboxes_generic.clear()
        self.filter_checkboxes_calculated.clear()

        # Получаем уникальные label_type из данных
        generic_types = set(label.label_type for label in self.generic_labels if label.label_type in self.ALLOWED_LABEL_TYPES)
        calculated_types = set(range_obj.label_type for range_obj in self.calculated_ranges if range_obj.label_type in self.ALLOWED_RANGE_TYPES)

        # Создаём чекбоксы для GenericLabel
        for label_type in sorted(generic_types): # sorted для стабильности порядка
            checkbox = QCheckBox(label_type)
            # --- ИЗМЕНЕНО: Устанавливаем НЕ включенным по умолчанию ---
            checkbox.setChecked(False)
             # --- НОВОЕ: Устанавливаем минимальную высоту для чекбокса ---
            # checkbox.setMinimumHeight(30) # Пример высоты, подберите по необходимости
            # --- КОНЕЦ НОВОГО ---
            # --- ИЗМЕНЕНО: Устанавливаем цвет фона всего чекбокса ---
            color = COLOR_MAPPING.get(label_type, DEFAULT_COLOR)
            # Создаём более светлый или темный оттенок для фона
            # QColor.adjusted(hue, sat, val) может помочь, но проще использовать rgba с разной прозрачностью или lighten/darken
            bg_color = color.lighter(150) if color.value() < 128 else color.darker(150) # Пример: светлее, если тёмный, темнее, если светлый
            # Устанавливаем стиль: цвет фона и цвет текста (чтобы текст был виден)
            text_color = "white" # if bg_color.value() < 128 else "black"
            checkbox.setStyleSheet(f"QCheckBox {{ background-color: {bg_color.name()}; color: {text_color}; padding: 2px; }} QCheckBox::indicator {{ width: 12px; height: 12px; }}")
            # Подключаем сигнал
            checkbox.stateChanged.connect(self._on_filter_changed)
            # Добавляем в словарь
            self.filter_checkboxes_generic[label_type] = checkbox
            # Добавляем на макет группы
            self.filter_layout_generic.addWidget(checkbox)
            #print(f"[DEBUG] _create_filter_checkboxes: создан чекбокс для GenericLabel: {label_type}")

        # Создаём чекбоксы для CalculatedRange
        for label_type in sorted(calculated_types): # sorted для стабильности порядка
            checkbox = QCheckBox(label_type)
            # --- ИЗМЕНЕНО: Устанавливаем НЕ включенным по умолчанию ---
            checkbox.setChecked(False)
            # --- НОВОЕ: Устанавливаем минимальную высоту для чекбокса ---
            # checkbox.setMinimumHeight(30) # Пример высоты, подберите по необходимости
            # --- КОНЕЦ НОВОГО ---
            # --- ИЗМЕНЕНО: Устанавливаем цвет фона всего чекбокса ---
            color = COLOR_MAPPING.get(label_type, DEFAULT_COLOR)
            bg_color = color.lighter(150) if color.value() < 128 else color.darker(150)
            text_color = "white" # if bg_color.value() < 128 else "black"
            checkbox.setStyleSheet(f"QCheckBox {{ background-color: {bg_color.name()}; color: {text_color}; padding: 2px; }} QCheckBox::indicator {{ width: 12px; height: 12px; }}")
            # Подключаем сигнал
            checkbox.stateChanged.connect(self._on_filter_changed)
            # Добавляем в словарь
            self.filter_checkboxes_calculated[label_type] = checkbox
            # Добавляем на макет группы
            self.filter_layout_calculated.addWidget(checkbox)
            #print(f"[DEBUG] _create_filter_checkboxes: создан чекбокс для CalculatedRange: {label_type}")
                # --- НОВОЕ: Восстанавливаем старые состояния ---
        for label_type, was_checked in old_states_generic.items():
            if label_type in self.filter_checkboxes_generic:
                # Если чекбокс с таким label_type был и есть, восстанавливаем его состояние
                self.filter_checkboxes_generic[label_type].setChecked(was_checked)
                print(f"[DEBUG] _create_filter_checkboxes: восстановлено состояние для GenericLabel: {label_type} (checked={was_checked})")

        for label_type, was_checked in old_states_calculated.items():
            if label_type in self.filter_checkboxes_calculated:
                # Если чекбокс с таким label_type был и есть, восстанавливаем его состояние
                self.filter_checkboxes_calculated[label_type].setChecked(was_checked)
                print(f"[DEBUG] _create_filter_checkboxes: восстановлено состояние для CalculatedRange: {label_type} (checked={was_checked})")
        # --- КОНЕЦ НОВОГО ---


    def _on_filter_changed(self):
        """Обработчик изменения состояния чекбокса фильтра."""
        #print(f"[DEBUG] TimelineWidget._on_filter_changed() вызван.")
        # Перерисовываем сцену при изменении фильтра
        if self.scene:
            self.scene.redraw()

    # --- Новый метод для расчёта масштаба ---
    def _calculate_scale(self):
        """Вычисляет масштаб (пикселей в секунду) для текущего активного диапазона."""
        active_duration = self.active_end_time - self.active_start_time
        if active_duration > 0:
            scale = self.view.width() / active_duration
        else:
            scale = 1.0  # Избегаем деления на 0, если диапазон 0
        return scale

    # --- Новый метод для поиска ближайшего элемента ---
    def _find_closest_element_time(self, direction: str) -> float | None:
        """
        Ищет ближайшее видимое время (GenericLabel.global_time или CalculatedRange.start_time/end_time)
        слева ('left') или справа ('right') от self.current_global_time.

        Возвращает найденное время (float) или None, если не найдено.
        """
        current_time = self.current_global_time
        active_start = self.active_start_time
        active_end = self.active_end_time

        # Получаем фильтры
        filter_checkboxes_generic = self.filter_checkboxes_generic
        filter_checkboxes_calculated = self.filter_checkboxes_calculated

        # Список времён для поиска
        candidate_times = []

        # Собираем времена из GenericLabel
        for label in self.generic_labels:
            label_type = label.label_type
            # Проверяем фильтр и попадание в активный диапазон
            if (label_type in filter_checkboxes_generic and
                filter_checkboxes_generic[label_type].isChecked() and
                active_start <= label.global_time <= active_end):
                    candidate_times.append(label.global_time)

        # Собираем времена из CalculatedRange (start и end)
        for range_obj in self.calculated_ranges:
            range_type = range_obj.label_type
            # Проверяем фильтр и пересечение с активным диапазоном
            if (range_type in filter_checkboxes_calculated and
                filter_checkboxes_calculated[range_type].isChecked() and
                not (range_obj.end_time < active_start or range_obj.start_time > active_end)):
                    # Добавляем start_time и end_time, если они внутри активного диапазона
                    if active_start <= range_obj.start_time <= active_end:
                        candidate_times.append(range_obj.start_time)
                    if active_start <= range_obj.end_time <= active_end and range_obj.start_time != range_obj.end_time: # Не добавляем дубль, если start=end
                        candidate_times.append(range_obj.end_time)

        if not candidate_times:
            #print(f"[DEBUG] _find_closest_element_time: Нет видимых элементов для поиска.")
            return None

        # Сортируем времена
        candidate_times.sort()

        #print(f"[DEBUG] _find_closest_element_time: Кандидаты (отсортированы): {candidate_times}, current_time: {current_time}, direction: {direction}")

        # Ищем ближайшее
        if direction == "left":
            # Ищем последнее время, которое меньше current_time
            for t in reversed(candidate_times):
                if t < current_time:
                    #print(f"[DEBUG] _find_closest_element_time: Найдено слева: {t}")
                    return t
        elif direction == "right":
            # Ищем первое время, которое больше current_time
            for t in candidate_times:
                if t > current_time:
                    #print(f"[DEBUG] _find_closest_element_time: Найдено справа: {t}")
                    return t

        #print(f"[DEBUG] _find_closest_element_time: Не найдено подходящего времени в направлении {direction}.")
        return None


    # --- Переопределение keyPressEvent для "прилипания" ---
    # --- Переопределение keyPressEvent для "прилипания" ---
    def keyPressEvent(self, event):
        """Обработка нажатия клавиш 8 и 9 для 'прилипания'."""
        key = event.key()
        if key == Qt.Key_8: # Клавиша 8
            print("[DEBUG] TimelineWidget.keyPressEvent: Нажата клавиша 8 (влево).") # Изменили подпись
            # --- ИСПРАВЛЕНО: ищем СЛЕВА от current_time ---
            target_time = self._find_closest_element_time("left") # Было "right", стало "left"
            if target_time is not None:
                #print(f"[DEBUG] TimelineWidget.keyPressEvent: Прилипание к времени {target_time:.3f}s по клавише 8.")
                self.globalTimeRequested.emit(target_time)
            else:
                print("[DEBUG] TimelineWidget.keyPressEvent: Не найдено время для 'прилипания' по клавише 8.")
        elif key == Qt.Key_9: # Клавиша 9
            print("[DEBUG] TimelineWidget.keyPressEvent: Нажата клавиша 9 (вправо).") # Изменили подпись
            # --- ИСПРАВЛЕНО: ищем СПРАВА от current_time ---
            target_time = self._find_closest_element_time("right") # Было "left", стало "right"
            if target_time is not None:
                #print(f"[DEBUG] TimelineWidget.keyPressEvent: Прилипание к времени {target_time:.3f}s по клавише 9.")
                self.globalTimeRequested.emit(target_time)
            else:
                print("[DEBUG] TimelineWidget.keyPressEvent: Не найдено время для 'прилипания' по клавише 9.")
        else:
            # Вызов родительской реализации для других клавиш
            super().keyPressEvent(event)



    # --- Заглушка для метода обновления данных ---
    def update_data(self, generic_labels: list[GenericLabel], calculated_ranges: list[CalculatedRange]):
        """Обновляет внутренние списки данных и чекбоксы фильтров."""
        #print(f"[DEBUG] TimelineWidget.update_data() вызван. generic_labels: {len(generic_labels)}, calculated_ranges: {len(calculated_ranges)}")
        self.generic_labels = generic_labels
        self.calculated_ranges = calculated_ranges
        # Обновление фильтров и отображения
        self._create_filter_checkboxes() # Создаём чекбоксы на основе новых данных
        if self.scene:
            self.scene.redraw() # Перерисовываем сцену с новыми данными и фильтрами

    # --- Заглушка для метода обновления активного диапазона ---
    def update_active_range(self, start_time: float, end_time: float, name: str):
        """Обновляет активный диапазон."""
        #print(f"[DEBUG] TimelineWidget.update_active_range() вызван. ({start_time} - {end_time}, '{name}')")
        self.active_start_time = start_time
        self.active_end_time = end_time
        self.active_range_name = name
        # Перерасчет масштаба и отображения будет реализован позже
        # Пока просто перерисуем, чтобы обновить индикатор времени и проверить видимость элементов
        if self.scene:
            self.scene.redraw()

    # --- Заглушка для метода обновления текущего времени ---
    def update_current_time(self, global_time_sec: float):
        """Заглушка. Обновляет текущее время."""
        #print(f"[DEBUG TimelineWidget] update_current_time вызван с global_time_sec = {global_time_sec}") # <-- НОВАЯ СТРОКА
        self.current_global_time = global_time_sec
        # Перемещение индикатора будет реализовано позже через вызов scene.redraw()
        # --- ИЗМЕНЕНО: Вызываем update_time_indicator_position вместо redraw ---
        if self.scene:
            self.scene.update_time_indicator_position() # Обновляем ТОЛЬКО индикатор времени
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    # --- Заглушка для обработки нажатия клавиш (оставлена для примера, но основная логика в keyPressEvent) ---
    # def keyPressEvent(self, event):
    #     """Заглушка. Обработка клавиш 8 и 9 для 'прилипания' будет реализована позже."""
    #     # Пока не реализовано
    #     super().keyPressEvent(event) # Вызов родительской реализации для других клавиш
