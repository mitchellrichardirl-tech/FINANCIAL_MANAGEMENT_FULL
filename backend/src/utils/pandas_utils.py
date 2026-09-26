from typing import Union

import pandas as pd

class SAME_PD:
    def __init__(self, pd_obj: Union[pd.DataFrame, pd.Series]):
        self.pd_obj = pd_obj

    def __eq__(self, other):
        return isinstance(other, type(self.pd_obj)) and other.equals(self.pd_obj)