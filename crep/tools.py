# Copyright 2023 Eurobios
# Licensed under the CeCILL License;
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://cecill.info/
import numpy as np
import pandas as pd

from typing import Any, Iterable


def build_admissible_data(
        df: pd.DataFrame,
        id_discrete: Iterable[Any],
        id_continuous: [Any, Any]
) -> pd.DataFrame:
    df.index = range(len(df.index))
    df_non_admissible = sample_non_admissible_data(df, id_discrete, id_continuous).__deepcopy__()
    df_non_admissible = create_zones(df_non_admissible, id_discrete, id_continuous)

    df_non_admissible["__id__"] = range(len(df_non_admissible))
    df_add_non_admissible = df_non_admissible[[*id_discrete, *id_continuous, "__id__", "__zone__"]]
    all_id_continuous = df_non_admissible[id_continuous[0]].to_list()
    all_id_continuous += df_non_admissible[id_continuous[1]].to_list()

    # create good segmentation
    df_ret = pd.concat([df_non_admissible[[*id_discrete, "__zone__"]]] * 2)
    df_ret[id_continuous[0]] = all_id_continuous
    df_ret["__disc__"] = compute_discontinuity(df_ret, id_discrete, id_continuous)
    df_ret = df_ret.sort_values(by=[*id_discrete, id_continuous[0]])
    df_ret[id_continuous[1]] = - df_ret[id_continuous[0]].diff(periods=-1) + df_ret[id_continuous[0]]
    df_ret = df_ret.dropna().drop(columns="__disc__")
    df_ret = df_ret.drop_duplicates().dropna()
    df_ret = df_ret[df_ret[id_continuous[1]] != df_ret[id_continuous[0]]]
    df_ret = df_ret.sort_values(by=[*id_discrete, id_continuous[0]])
    df_ret[id_continuous[1]] = df_ret[id_continuous[1]].astype(df[id_continuous[1]].dtype)

    df_ret = pd.merge(df_ret, df_add_non_admissible,
                      on=id_discrete + ["__zone__"], suffixes=("", "_tmp"))
    id_continuous_tmp = [str(i) + "_tmp" for i in id_continuous]
    c = df_ret[id_continuous[0]] < df_ret[id_continuous_tmp[1]]
    c &= df_ret[id_continuous[1]] > df_ret[id_continuous_tmp[0]]
    df_ret = df_ret.loc[c].drop(columns=id_continuous_tmp)

    df_ret = pd.merge(df_ret, df_non_admissible.drop(columns=[*id_discrete, *id_continuous, "__zone__"]), on="__id__"
                      ).drop(columns=["__id__", "__zone__"])
    df_ret = df_ret.astype(df_non_admissible.dtypes.drop(["__id__", "__zone__"]))

    df_ret_all = df[~get_overlapping(df, id_discrete, id_continuous)]
    df_ret_all = pd.concat((df_ret_all, df_ret))
    df_ret_all = df_ret_all.sort_values(by=[*id_discrete, id_continuous[0]])
    df_ret_all.index = range(len(df_ret_all.index))
    return df_ret_all


def create_zones(
        df: pd.DataFrame,
        id_discrete: Iterable[Any],
        id_continuous: [Any, Any]
):
    """
    Create overlapping zone identifiers in the DataFrame based on discrete and continuous ID columns.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame containing the df.
    id_discrete : iter
        An iterable of column names that are considered discrete identifiers.
    id_continuous : iter
        An iterable of column names that are considered continuous identifiers.

    Returns
    -------
    pd.DataFrame
        The DataFrame with an additional '__zone__' column indicating the zone for each row.

    Notes
    -----
    The function works by sorting the DataFrame based on the given discrete and continuous identifiers,
    and then creating a zone identifier (`__zone__`) that groups rows based on specific conditions.

    Steps:
    1. Sort the DataFrame based on discrete identifiers and the second continuous identifier.
    2. Assign a forward index (`__zf__`) based on the sorted order.
    3. Sort the DataFrame based on discrete identifiers and the first continuous identifier.
    4. Assign a backward index (`__zi__`) based on the sorted order.
    5. Determine zones where the forward and backward indices are equal (`c_zone`).
    6. Check if the start of a zone is greater than or equal to the end of the previous zone (`c_inner`).
    7. Identify changes in discrete identifiers (`c_disc`).
    8. Combine the conditions to create the final zone identifier (`__zone__`).

    Examples
    --------
    >>> df = {
    ...     'id': [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2],
    ...     't1': [932, 996, 2395, 2395, 3033, 3628, 4126, 4140, 4154, 316263, 316263, 316471, 316471],
    ...     't2': [2395, 2324, 3033, 3628, 3035, 4140, 4140, 5508, 5354, 316399, 316471, 317406, 317557],
    ...     'LONGUEUR': [1463, 1328, 638, 1233, 2, 512, 14, 1368, 1200, 136, 208, 935, 1086],
    ...     '__zone__': [0, 0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4]
    ... }
    >>> df = pd.DataFrame(df)
    >>> create_zones(df, ['id'], ['t1', 't2'])
    """
    df_out = df.__deepcopy__()
    if "__zone__" in df.columns:
        df_out = df_out.drop(columns='__zone__')

    df_out = df_out.sort_values([*id_discrete, id_continuous[1]])
    df_out["__zf__"] = range(len(df_out))
    df_out = df_out.sort_values([*id_discrete, id_continuous[0]])
    df_out["__zi__"] = range(len(df_out))
    c_zone = (df_out["__zf__"] - df_out["__zi__"]) == 0

    df_out["__id2_prev__"] = df[id_continuous[1]]
    df_out.loc[df_out.index[1:], "__id2_prev__"] = df_out.loc[df_out.index[:-1], id_continuous[1]].values
    c_inner = df_out[id_continuous[0]] >= df_out["__id2_prev__"]

    c_disc = df_out[id_discrete].iloc[1:].values == df_out[id_discrete].iloc[:-1].values
    c_disc = c_disc.mean(axis=1) == 1
    c_disc = ~ np.concatenate(([True], c_disc))

    df_out["__zone__"] = (c_zone & c_inner) | c_disc
    df_out["__zone__"] = df_out["__zone__"].cumsum()

    return df_out.loc[df.index, [*df.columns.to_list(), "__zone__"]]


def get_overlapping(df: pd.DataFrame,
                    id_discrete: Iterable[Any],
                    id_continuous: [Any, Any]
                    ) -> pd.Series:
    df = create_zones(df, id_discrete, id_continuous)
    overlap = df["__zone__"].duplicated(keep=False)
    return overlap


def admissible_dataframe(data: pd.DataFrame,
                         id_discrete: Iterable[Any],
                         id_continuous: [Any, Any]
                         ):
    return sum(get_overlapping(data, id_discrete,
                               id_continuous)) == 0


def sample_non_admissible_data(data: pd.DataFrame,
                               id_discrete: Iterable[Any],
                               id_continuous: [Any, Any]
                               ) -> pd.DataFrame:
    return data[get_overlapping(data, id_discrete,
                                id_continuous)]


def compute_discontinuity(
        df,
        id_discrete: Iterable[Any],
        id_continuous: [Any, Any]
):
    """
    Compute discontinuity in rail segment. The i-th element in return
    will be True if i-1 and i are discontinuous

    """
    discontinuity = np.zeros(len(df)).astype(bool)
    for col in id_discrete:
        if col in df.columns:
            discontinuity_temp = np.concatenate(
                ([False], df[col].values[1:] != df[col].values[:-1]))
            discontinuity |= discontinuity_temp

    if id_continuous[0] in df.columns and id_continuous[1] in df.columns:
        discontinuity_temp = np.concatenate(
            ([False], df[id_continuous[0]].values[1:] != df[id_continuous[
                1]].values[:-1]))
        discontinuity |= discontinuity_temp
    return discontinuity


def create_continuity(
        df: pd.DataFrame,
        id_discrete: Iterable[Any],
        id_continuous: [Any, Any],
        limit=None, sort=False
) -> pd.DataFrame:
    df_in = df.__deepcopy__()
    col_save = np.array(df_in.columns)
    index = [*id_discrete, *id_continuous]
    df_in["discontinuity"] = compute_discontinuity(df_in, id_discrete, id_continuous)
    if df_in["discontinuity"].sum() == 0:
        return df
    else:
        ix__ = np.where(df_in["discontinuity"].values)[0]
        df_add = pd.DataFrame(columns=df_in.columns, index=range(len(ix__)))
        df_add[index] = df_in.iloc[ix__][index].values
        df_add[id_continuous[0]] = df_in.iloc[ix__ - 1].loc[:, id_continuous[1]].values
        df_add[id_continuous[1]] = df_in.iloc[ix__].loc[:, id_continuous[0]].values
        if limit is not None:
            df_add = df_add[(df_add[id_continuous[1]] - df_add[id_continuous[0]]) < limit]
        df_in = pd.concat((df_in, df_add.dropna(axis=1, how='all')), axis=0)
        df_in = df_in[df_in[id_continuous[0]] < df_in[id_continuous[1]]]
    if sort:
        df_in = df_in.sort_values([*id_discrete, *id_continuous])
    return df_in.loc[:, col_save]
