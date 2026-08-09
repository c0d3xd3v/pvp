import re
from PySide6.QtCore import Slot, QObject


def _natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


class ResultCtrl(QObject):
    def __init__(self):
        super().__init__()
        self.__result_data = None
        self.__scene_ctrl = None
        self.__current_field_name = None

    def set_scene_ctrl(self, scene_ctrl):
        self.__scene_ctrl = scene_ctrl

    def load_result(self, data):
        self.__result_data = data

    def clear(self):
        self.__result_data = None
        self.__current_field_name = None

    @Slot(result='QVariantList')
    def getFunctionNames(self):
        if self.__result_data is None:
            return []
        names = self.__result_data.get_field_names() or []
        return sorted(names, key=_natural_sort_key)

    @Slot(str)
    def selectFunctionByName(self, name):
        self.__current_field_name = name
        if self.__scene_ctrl is not None:
            self.__scene_ctrl.select_function(name)

    @Slot(result=bool)
    def isCurrentFieldVectorValued(self):
        if self.__result_data is None or self.__current_field_name is None:
            return False
        data = self.__result_data.get_vertex_field_data(self.__current_field_name)
        if data is None:
            return False
        return data.ndim > 1 and data.shape[1] > 1

    @Slot(bool, float)
    def apply_vector_field_on_position(self, should_apply, scale):
        if self.__scene_ctrl is not None:
            self.__scene_ctrl.apply_vector_field_on_position(should_apply, scale)

    @Slot(float)
    def setAnimationTime(self, t):
        if self.__scene_ctrl is not None:
            self.__scene_ctrl.set_animation_time(t)
