# Copyright 2023 Eurobios
# Licensed under the CeCILL License;
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://cecill.info/
import numpy as np
import pandas as pd

from crep import merge, aggregate_constant
from crep.base import __fill_stretch, __merge


def test_merge_basic(get_examples):
    dfl, dfr = get_examples
    ret = merge(dfl, dfr,
                id_continuous=["t1", "t2"],
                id_discrete=["id"],
                how="outer")
    ret_l = merge(dfl, dfr,
                  id_continuous=["t1", "t2"],
                  id_discrete=["id"],
                  how="left")
    ret_i = merge(dfl, dfr,
                  id_continuous=["t1", "t2"],
                  id_discrete=["id"],
                  how="inner")
    ret_r = merge(dfl, dfr,
                  id_continuous=["t1", "t2"],
                  id_discrete=["id"],
                  how="right")
    ret_th = pd.DataFrame(
        dict(id=[1, 1, 1, 1, 2, 2, 2],
             t1=[0, 5, 10, 80, 0, 100, 120],
             t2=[5, 10, 80, 100, 90, 110, 130],
             data1=[0.2, 0.2, 0.2, 0.2, 0.1, 0.3, 0.2],
             data2=[np.nan, 0.2, 0.2, np.nan, 0.1, 0.3, 0.2],
             ))
    ret_i_th = ret_th.dropna()
    ret_i_th.index = range(ret_i_th.__len__())
    assert ret.equals(ret_th)
    assert ret_l.equals(ret_th)
    assert ret_i.equals(ret_i_th)
    assert ret_r.equals(ret_i_th)


def test_fill_stretch(get_examples):
    dfl, _ = get_examples
    ret = __fill_stretch(dfl,
                         id_continuous=["t1", "t2"],
                         id_discrete=["id"],
                         )
    assert ret["added"].sum() == 2


def test__merge(get_examples):
    df_left, df_right = get_examples
    df_merge = __merge(df_left, df_right,
                       id_discrete=["id"], id_continuous=["t1", "t2"])


def test_check_args(get_examples):
    pass


def test_aggregate_constant(get_examples):
    df1, _ = get_examples
    ret = aggregate_constant(df1, id_continuous=["t1", "t2"],
                             id_discrete=["id"])
    print(ret)
    print(pd.__version__)
    assert len(ret) < len(df1)
