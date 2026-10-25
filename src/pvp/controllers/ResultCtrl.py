import re
from PySide6.QtCore import Slot, QObject


def _natural_sort_key(s):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]


class ResultCtrl(QObject):
    def __init__(self, scene_ctrl):
        super().__init__()
        self.__result_data = None
        self.__scene_ctrl = scene_ctrl
        self.__current_field_name = None

    def load_result(self, data):
        self.__result_data = data

    def clear(self):
        self.__result_data = None
        self.__current_field_name = None

    @Slot(result='QVariantList')
    def getFunctionNames(self):
        if self.__result_data is None:
            return []
        names = list(self.__result_data.fields)
        return sorted(names, key=_natural_sort_key)

    @Slot(str)
    def selectFunctionByName(self, name):
        self.__current_field_name = name
        self.__scene_ctrl.select_function(name)

    @Slot(result=bool)
    def isCurrentFieldVectorValued(self):
        if self.__result_data is None or self.__current_field_name is None:
            return False
        data = self.__result_data.fields.get(self.__current_field_name)
        if data is None:
            return False
        return data.ndim > 1 and data.shape[1] > 1

    @Slot(bool, float)
    def apply_vector_field_on_position(self, should_apply, scale):
        self.__scene_ctrl.apply_vector_field_on_position(should_apply, scale)

    @Slot(float)
    def setAnimationTime(self, t):
        self.__scene_ctrl.set_animation_time(t)
