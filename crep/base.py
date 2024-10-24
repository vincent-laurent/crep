# Copyright 2023 Eurobios
# Licensed under the CeCILL License;
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://cecill.info/
import numpy as np
import pandas as pd
from crep import tools

from typing import Any


def merge(
        data_left: pd.DataFrame,
        data_right: pd.DataFrame,
        id_continuous: [Any, Any],
        id_discrete: iter,
        how: str,
        remove_duplicates: bool = False,
        verbose=False) -> pd.DataFrame:
    """
    This function aims at creating merge data frame

    Parameters
    ----------

    data_left
        data frame with continuous representation
    data_right
        data frame with continuous representation
    id_continuous
        iterable of length two that delimits the edges of the segment
    id_discrete: iterable
        iterable that lists all the columns on which to perform a classic merge
    how: str
        how to make the merge, possible options are

        - 'left'
        - 'right'
        - 'inner'
        - 'outer'

    remove_duplicates
        whether to remove duplicates
    verbose
    """
    __check_args_merge(data_left, data_right,
                       id_continuous, id_discrete, how)

    data_left = data_left.__deepcopy__()
    data_right = data_right.__deepcopy__()
    id_continuous = list(id_continuous)
    id_discrete = list(id_discrete)

    id_discrete_left = [col for col in data_left.columns if col in id_discrete]
    id_discrete_right = [col for col in data_right.columns if col in id_discrete]
    data_left, data_right = __fix_discrete_index(
        data_left, data_right,
        id_discrete_left,
        id_discrete_right)
    data_left.index = range(len(data_left))
    data_right.index = range(len(data_right))
    df_merge = __merge_index(data_left, data_right,
                             id_discrete=id_discrete,
                             id_continuous=id_continuous)
    df = pd.merge(
        df_merge,
        data_left[list(set(data_left.columns).difference(df_merge.columns))],
        left_on="left_idx", right_index=True, how="left")
    df = pd.merge(
        df,
        data_right[list(set(data_right.columns).difference(df_merge.columns))],
        left_on="right_idx", right_index=True, how="left")

    if how == "left":
        df = df.loc[df["left_idx"] != -1]
    if how == "right":
        df = df.loc[df["right_idx"] != -1]
    if how == "inner":
        df = df.loc[(df["right_idx"] != -1) & (df["left_idx"] != -1)]

    df = df.drop(["left_idx", "right_idx"], axis=1)
    df.index = range(len(df))
    if remove_duplicates:
        df = suppress_duplicates(df, id_discrete=id_discrete,
                                 continuous_index=id_continuous)
    if verbose:
        print("[merge] nb rows left  table frame ", data_left.shape[0])
        print("[merge] nb rows right table frame ", data_right.shape[0])
        print("[merge] nb rows outer table frame ", df.shape[0])
    return df


def unbalanced_merge(
        data_admissible: pd.DataFrame,
        data_not_admissible: pd.DataFrame, id_discrete: iter, id_continuous: [Any, Any]) -> pd.DataFrame:
    """
    Merge admissible and non-admissible dataframes based on discrete and continuous identifiers.

    Parameters
    ----------
    data_admissible : pd.DataFrame
        DataFrame containing admissible data.
    data_not_admissible : pd.DataFrame
        DataFrame containing non-admissible data.
    id_discrete : list
        List of column names representing discrete identifiers.
    id_continuous : list
        List of column names representing continuous identifiers.

    Returns
    -------
    pd.DataFrame
        A DataFrame resulting from the unbalanced merge of admissible and non-admissible data.

    Notes
    -----
    The function performs the following steps:
    1. Combines and sorts the admissible and non-admissible data based on the identifiers.
    2. Resolves overlaps and conflicts between the admissible and non-admissible data.
    3. Merges and returns the final DataFrame.
    """
    # assert tools.admissible_dataframe(data_admissible, id_discrete, id_continuous)
    df_idx_w = data_admissible[[*id_discrete, *id_continuous]].copy()
    df_idx_s = data_not_admissible[[*id_discrete, *id_continuous]].copy()
    df_idx_w["__t__"] = True
    df_idx_s["__t__"] = False

    df_idx = pd.concat((df_idx_w, df_idx_s))
    df_idx = df_idx.sort_values([*id_discrete, id_continuous[0], "__t__"],
                                ascending=[*[True] * len(id_discrete), True, False])

    df_idx["__id2__"] = np.nan
    df_idx["__id1__"] = np.nan
    df_idx.loc[df_idx["__t__"], "__id2__"] = df_idx.loc[df_idx["__t__"], id_continuous[1]]
    df_idx.loc[df_idx["__t__"], "__id1__"] = df_idx.loc[df_idx["__t__"], id_continuous[0]]
    df_idx["__id2__"] = df_idx["__id2__"].ffill()
    df_idx["__id1__"] = df_idx["__id1__"].ffill()

    c_resolve = df_idx["__id2__"] < df_idx[id_continuous[1]]
    c_out = df_idx["__id2__"] < df_idx[id_continuous[0]]
    created_columns = ["__t__", "__id2__", "__id1__"]

    # =================
    # Encompassed data
    df_admissible = df_idx[~c_resolve].copy()
    df_admissible_ret = pd.merge(df_admissible, data_admissible, how='inner',
                                 left_on=[*id_discrete, "__id1__", "__id2__"], right_on=[*id_discrete, *id_continuous],
                                 suffixes=("", "__init"))
    df_admissible_ret = df_admissible_ret[~df_admissible_ret.__t__]
    df_admissible_ret = df_admissible_ret.drop(
        columns=[*created_columns, id_continuous[0] + "__init", id_continuous[1] + "__init"])
    df_admissible_ret = pd.merge(df_admissible_ret, data_not_admissible, on=[*id_discrete, *id_continuous], how="left")

    # =================
    # To resolve data
    df_to_resolve = df_idx[c_resolve & ~c_out].copy()
    old = [f"{id_continuous[0]}__", f"{id_continuous[1]}__"]
    df_to_resolve[old] = df_to_resolve[id_continuous]
    df_to_resolve_admissible = tools.build_admissible_data(df_to_resolve.drop(columns=created_columns), id_discrete,
                                                           id_continuous)

    df_to_resolve_no_d = df_to_resolve_admissible.drop_duplicates(subset=[*id_discrete, *id_continuous])
    if len(df_to_resolve_no_d) > 0:
        df_to_resolve_no_d = merge(
            df_to_resolve_no_d,
            data_admissible, id_discrete=id_discrete, id_continuous=id_continuous,
            how="inner")
        df_ret = pd.merge(
            df_to_resolve_no_d,
            data_not_admissible,
            left_on=[*id_discrete, *old],
            right_on=[*id_discrete, *id_continuous], how="inner", suffixes=("", "__")
        )
        df_ret = df_ret[df_admissible_ret.columns]
    else:
        df_ret = pd.DataFrame([], columns=df_admissible_ret.columns)
    # =================
    # Out data
    df_to_out = df_idx[c_resolve & c_out].copy().drop(columns=created_columns)
    df_to_out = pd.merge(df_to_out, data_not_admissible, on=[*id_discrete, *id_continuous], how='inner')

    df_ret_all = pd.concat((df_ret, df_admissible_ret, df_to_out), axis=0)
    df_ret_all.index = range(len(df_ret_all))
    df_ret_all = df_ret_all.sort_values(by=[*id_discrete, *id_continuous])
    return df_ret_all


def aggregate_constant(df: pd.DataFrame,
                       id_discrete: iter,
                       id_continuous: iter,
                       ):
    """

    Parameters
    ----------
    df
    id_discrete
    id_continuous

    Returns
    -------

    """
    data_ = df.copy(deep=True)
    dtypes = data_.dtypes
    data_ = data_.sort_values([*id_discrete, *id_continuous])
    # 1/ detect unnecessary segment
    indexes = [*id_discrete, *id_continuous]
    no_index = list(set(data_.columns).difference(indexes))
    id1, id2 = id_continuous

    disc = tools.compute_discontinuity(data_, id_discrete, id_continuous)
    identical = False * np.ones_like(disc)

    index = data_.index

    data_1 = data_.loc[index[:-1], no_index].fillna(np.nan).values
    data_2 = data_.loc[index[1:], no_index].fillna(np.nan).values

    np_bool: np.array = np.equal(data_1, data_2)

    res = pd.Series(np_bool.sum(axis=1), index=index[:-1])
    res = pd.Series(res == len(no_index)).values

    identical[:-1] = res
    identical[:-1] = identical[:-1] & ~disc[1:]

    n = identical.sum()
    if n == 0:
        return df
    dat = pd.DataFrame(dict(
        identical=identical,
        keep=False * np.ones_like(disc)),
        index=data_.index)

    keep = list(set(np.where(identical)[0]).union(np.where(identical)[0] + 1))
    dat.loc[dat.index[keep], "keep"] = True

    data_merge = data_.sort_values([*id_discrete, *id_continuous])
    data_merge[f"{id1}_new"] = np.nan
    b = ~ dat["identical"]
    b_disc = [True] + list(~dat["identical"].values[:-1])
    data_merge.loc[b, f"{id2}_new"] = data_merge.loc[b, id2]
    data_merge.loc[b_disc, f"{id1}_new"] = data_merge.loc[b_disc, id1]

    data_merge[f"{id2}_new"] = data_merge[f"{id2}_new"].bfill()
    data_merge[f"{id1}_new"] = data_merge[f"{id1}_new"].ffill()

    data_merge = data_merge.drop(list(id_continuous), axis=1)
    data_merge = data_merge.rename({f"{id1}_new": id1, f"{id2}_new": id2},
                                   axis=1)
    return data_merge[df.columns].drop_duplicates().astype(dtypes)


def __merge_index(data_left, data_right,
                  id_discrete,
                  id_continuous,
                  names=("left", "right")):
    id_ = [*id_discrete, *id_continuous]
    id_c = id_continuous
    cr = is_event(data_right, id_continuous=id_continuous)
    cl = is_event(data_left, id_continuous=id_continuous)
    if cr and cl:
        raise AssertionError(
            "[merge] This functionality is not yet implemented")
    elif cl:
        return __merge_index(data_right, data_left, id_discrete=id_discrete,
                             id_continuous=id_c, names=names)
    elif cr:
        data_left = data_left.loc[:, id_].dropna()
        data_left.loc[:, id_c] = data_left.loc[:, id_c].astype(int)

        data_right = data_right.loc[:, [*id_discrete, "pk"]]
        raise AssertionError(
            "[merge] This functionality is not yet implemented")
    else:
        data_left = data_left.loc[:, id_].dropna()
        data_right = data_right.loc[:, id_].dropna()
        df_merge = __merge(data_left, data_right,
                           id_discrete=id_discrete, id_continuous=id_c)
    return df_merge


def merge_event(
        data_left: pd.DataFrame, data_right: pd.DataFrame,
        id_discrete: iter,
        id_continuous: [Any, Any],
):
    """
    Merges two dataframes on both discrete and continuous indices, with forward-filling of missing data.

    This function merges two Pandas DataFrames (`data_left` and `data_right`) based on discrete and continuous keys.
    It creates a deep copy of the dataframes, reindexes their columns to match, and concatenates them along the rowaxis.
    The merged dataframe is sorted based on the discrete and continuous index columns, and missing values in the left dataframe
    are forward-filled.

    Parameters
    ----------
    data_left : pd.DataFrame
        The left dataframe to be merged.
    data_right : pd.DataFrame
        The right dataframe to be merged.
    id_discrete : iterable
        The list of column names representing discrete identifiers for sorting and merging (e.g., categorical variables).
    id_continuous : list of two elements (Any, Any)
        A list with two elements representing the continuous index (e.g., time or numerical variables).
        The first element is the column name of the continuous identifier used for sorting.

    Returns
    -------
    pd.DataFrame
        A merged dataframe that combines `data_left` and `data_right`.

    """
    data_left_ = data_left.__deepcopy__()
    data_right_ = data_right.__deepcopy__()
    data_left_ = _increasing_continuous_index(data_left_, id_continuous)

    data_left_ = data_left_.reset_index()
    data_right_ = data_right_.reset_index()

    all_columns = list(set(data_left_.columns).union(data_right_.columns))
    df_merge = data_left_.reindex(columns=all_columns)
    df_merge["__t"] = df_merge[id_continuous[0]]
    data_right_ = data_right_.reindex(columns=all_columns)
    df_merge = pd.concat((df_merge, data_right_), axis=0).sort_values(
        [*id_discrete, "__t"])
    df_merge[data_left_.columns] = df_merge[data_left_.columns].ffill()

    df_merge.dropna()
    return df_merge


def create_regular_segment_segmentation(
        data: pd.DataFrame, length,
        id_discrete: iter,
        id_continuous: [Any, Any]
) -> pd.DataFrame:
    if length == 0:
        return data
    # For each couple we compute the number of segment given the length
    df_disc_f = data.groupby(id_discrete)[id_continuous[1]].max().reset_index()
    df_disc_d = data.groupby(id_discrete)[id_continuous[0]].min().reset_index()
    df_disc = pd.merge(df_disc_d, df_disc_f, on=id_discrete)

    df_disc["nb_coupon"] = np.round((df_disc[id_continuous[1]] - df_disc[id_continuous[0]]) / length).astype(int)
    df_disc["nb_coupon_cumsum"] = df_disc["nb_coupon"].cumsum()
    df_disc["nb_coupon_cumsum0"] = 0
    df_disc.loc[df_disc.index[1:], "nb_coupon_cumsum0"] = df_disc["nb_coupon_cumsum"].values[:-1]

    # Create empty regular segment table and we fill it with regular segment
    df_new = pd.DataFrame(index=range(df_disc["nb_coupon"].sum()),
                          columns=[*id_discrete, *id_continuous])
    for ix in df_disc.index:
        nb_cs = df_disc.loc[ix]
        value_temp = np.linspace(
            nb_cs[id_continuous[0]],
            nb_cs[id_continuous[1]],
            num=nb_cs['nb_coupon'] + 1,
            dtype=int)
        df_temp = pd.DataFrame(columns=[*id_discrete, *id_continuous])
        df_temp[id_continuous[0]] = value_temp[:-1]
        df_temp[id_continuous[1]] = value_temp[1:]
        df_temp[id_discrete] = nb_cs[id_discrete].values
        df_new.iloc[nb_cs["nb_coupon_cumsum0"]:nb_cs["nb_coupon_cumsum"]] = df_temp

    df_new["__id__"] = range(len(df_new))

    df_keep = merge(df_new, data,
                    id_continuous=id_continuous,
                    id_discrete=id_discrete,
                    how="left")

    df_new = df_new[df_new["__id__"].isin(df_keep["__id__"])]
    return df_new[[*id_discrete, *id_continuous]]


def __merge(df_left: pd.DataFrame, df_right: pd.DataFrame,
            id_discrete: iter,
            id_continuous,
            names=("left", "right")):
    index = [*id_discrete, *id_continuous]

    df_id1, df_id2, index_left, index_right = __refactor_data(
        df_left,
        df_right, id_continuous, id_discrete,
        names=names)
    df_id1_stretched = tools.create_continuity(
        df_id1, id_discrete=id_discrete,
        id_continuous=id_continuous)
    df_id2_stretched = tools.create_continuity(
        df_id2, id_discrete=id_discrete,
        id_continuous=id_continuous)

    df_id1_stretched.loc[df_id1_stretched[index_left].isna(), index_left] = -1
    df_id2_stretched.loc[df_id2_stretched[index_right].isna(), index_right] = -1

    df = pd.concat((df_id1_stretched, df_id2_stretched), sort=False)
    df = df.sort_values(by=index)

    id1, id2 = id_continuous
    df_merge = __table_jumps(df, *id_continuous, id_discrete)

    df_merge = df_merge.dropna()

    df_merge = pd.merge(
        df_merge,
        df_id1_stretched[[index_left, id1, *id_discrete]],
        on=[id1, *id_discrete], how="left")

    df_merge = pd.merge(
        df_merge,
        df_id2_stretched[[index_right, id1, *id_discrete]],
        on=[id1, *id_discrete], how="left")

    df_end1 = df_id1_stretched[[index_left, id2, *id_discrete]].rename(
        {index_left: index_left + "_end"}, axis=1)
    df_end2 = df_id2_stretched[[index_right, id2, *id_discrete]].rename(
        {index_right: index_right + "_end"}, axis=1)

    df_merge = pd.merge(
        df_merge,
        df_end1,
        left_on=[id1, *id_discrete],
        right_on=[id2, *id_discrete], how="left", suffixes=("", "_1"))
    df_merge = pd.merge(
        df_merge,
        df_end2,
        left_on=[id1, *id_discrete],
        right_on=[id2, *id_discrete], how="left", suffixes=("", "_2"))
    df_merge = df_merge.drop([f"{id2}_1", f"{id2}_2"], axis=1)

    # Tackle the problem of ending pad when there is discontinuity
    idx1 = (df_merge[index_left + "_end"].infer_objects(copy=False).fillna(-1) >= 0).values
    is_na_condition = df_merge.loc[:, index_left].isna()
    df_merge.loc[idx1 & is_na_condition, index_left] = -1

    idx2 = (df_merge[index_right + "_end"].infer_objects(copy=False).fillna(-1) >= 0).values
    is_na_condition_2 = df_merge.loc[:, index_right].isna()
    df_merge.loc[idx2 & is_na_condition_2, index_right] = -1
    df_merge = df_merge.drop([index_right + "_end", index_left + "_end"],
                             axis=1)

    discontinuity = tools.compute_discontinuity(df_merge, id_discrete, id_continuous)
    df_merge.loc[discontinuity & df_merge[
        index_left].isna(), index_left] = -1
    df_merge.loc[discontinuity & df_merge[
        index_right].isna(), index_right] = -1

    df_merge = df_merge.infer_objects(copy=False).ffill().drop("___t", axis=1)

    df_merge[[index_right, index_left, id1, id2]] = df_merge[
        [index_right, index_left, id1, id2]].astype(float).fillna(
        -1).astype(int)

    df_merge = df_merge.loc[
        ~(df_merge[index_left] + df_merge[index_right] == -2)]
    return df_merge


def is_event(data, id_continuous: iter):
    id_continuous = list(id_continuous)
    if id_continuous[0] in data.columns and id_continuous[1] in data.columns:
        return False
    return True


def __fix_discrete_index(
        data_left: pd.DataFrame,
        data_right: pd.DataFrame,
        id_discrete_left: iter,
        id_discrete_right: iter):
    if len(id_discrete_left) < len(id_discrete_right):
        data_right, data_left = __fix_discrete_index(
            data_right, data_left,
            id_discrete_right, id_discrete_left, )
        return data_left, data_right

    df_id_left = data_left.loc[:, id_discrete_left].drop_duplicates()
    df_id_right = data_right.loc[:, id_discrete_right].drop_duplicates()

    id_inter = [id_ for id_ in id_discrete_right if id_ in id_discrete_left]
    id_inter = list(id_inter)
    df_id_right = pd.merge(df_id_left, df_id_right, on=id_inter)
    data_right = pd.merge(df_id_right, data_right, on=id_discrete_right, how="left")
    return data_left, data_right


def suppress_duplicates(df, id_discrete, continuous_index):
    df = df.sort_values([*id_discrete, *continuous_index])
    df_duplicated = df.drop([*id_discrete, *continuous_index], axis=1)
    mat_duplicated = pd.DataFrame(
        df_duplicated.iloc[1:].values == df_duplicated.iloc[
                                         :-1].values)
    id1 = continuous_index[0]
    id2 = continuous_index[1]
    index = mat_duplicated.sum(axis=1) == df_duplicated.shape[1]
    index = np.where(index)[0]
    df1 = df.iloc[index]
    df2 = df.iloc[index + 1]
    idx_replace = df1[id2].values == df2[id1].values
    idx_to_agg = index[idx_replace]
    i_loc = df1.columns.get_loc(id2)
    df.iloc[idx_to_agg, i_loc] = df.iloc[idx_to_agg + 1, i_loc].values
    df = df.drop(df.index[idx_to_agg + 1])
    return df


def _increasing_continuous_index(df: pd.DataFrame, id_continuous):
    id1 = id_continuous[0]
    id2 = id_continuous[1]
    df[f"{id1}_new"] = df.loc[:, [id1, id2]].min(axis=1)
    df[f"{id2}_new"] = df.loc[:, [id1, id2]].max(axis=1)

    df = df.drop([id1, id2], axis=1)
    df = df.rename({f"{id1}_new": id1, f"{id2}_new": id2}, axis=1)
    return df


def __refactor_data(data_left, data_right, id_continuous, id_discrete,
                    names=("left", "right")):
    index = [*id_discrete, *id_continuous]
    data_left = _increasing_continuous_index(data_left, id_continuous)
    data_right = _increasing_continuous_index(data_right, id_continuous)
    index_right = names[1] + "_idx"
    index_left = names[0] + "_idx"
    df_id1 = data_left[index].drop_duplicates()
    df_id2 = data_right[index].drop_duplicates()
    df_id1.index.name = index_left
    df_id2.index.name = index_right
    df_id1 = df_id1.reset_index()
    df_id2 = df_id2.reset_index()

    df_id1[index_right] = np.nan
    df_id2[index_left] = np.nan

    df_id1 = df_id1.sort_values(by=index)
    df_id2 = df_id2.sort_values(by=index)
    return df_id1, df_id2, index_left, index_right


def __check_args_merge(data_left, data_right,
                       id_continuous,
                       id_discrete,
                       how):
    for c in [*id_continuous, *id_discrete]:
        if not (c in data_left.columns or c in data_right.columns):
            raise ValueError(f"{c} is not in columns")
    if not len(id_continuous) == 2:
        raise ValueError("Only two continuous index is possible")
    if how not in ["left", "right", "inner", "outer"]:
        raise ValueError('How must be in "left", "right", "inner", "outer"')


def __table_jumps(data, id1, id2, id_discrete):
    df_unique_start = data[[id1, *id_discrete]].rename(
        {id1: "___t"}, axis=1).drop_duplicates()

    df_unique_end = data[[id2, *id_discrete]].rename(
        {id2: "___t"}, axis=1).drop_duplicates()

    ret = pd.concat((df_unique_end, df_unique_start),
                    sort=False).sort_values(
        by=[*id_discrete, "___t"]).drop_duplicates()
    if len(ret) == 0:
        return ret
    ret.index = range(ret.shape[0])
    ret[id1] = -1
    ret.iloc[:-1, -1] = ret["___t"].iloc[:-1].values
    ret[id2] = -1
    ret.iloc[:-1, -1] = ret["___t"].iloc[1:].values
    return ret
