from safe_utils import calculate_total_score,calculate_total_score_mc

def cal_total_score(added_df):
    added_df["total_score"] = added_df.apply(lambda row: calculate_total_score(
        basic_pt=row["basic_pt"],
        bonus_pt=row["bonus_pt"],
        type_=row["type_"],
        ai_score=row["task_score"],
        diver=row["diver"],
        cooper=row["cooper"]
    ), axis=1,)

    sorted_df = added_df.sort_values(by="total_score", ascending=False)
    distinct_cards_df = sorted_df.drop_duplicates(subset=['card_name'], keep='first')
    
    # 從去重後的結果中選取前三名
    top_df = distinct_cards_df.head(3)
    top_df["total_score"] = top_df["total_score"].apply(lambda x: f"{x:.2f}")
        # 組合回饋趴數（選擇要顯示哪一個或加總/文字串）
    top_df["總回饋"] = top_df.apply(
            lambda row: f"{float(row['basic_pt']) + float(row['bonus_pt'])}%", axis=1
        )
    print(top_df)
        # 只輸出所需欄位
    result = top_df[["card_name","store", "總回饋", "task","total_score"]]
    
    return added_df, result


def cal_total_scoremc(added_df):
    added_df["total_score"] = added_df.apply(lambda row: calculate_total_score_mc(
        basic_pt=row["basic_pt"],
        bonus_pt=row["bonus_pt"],
        type_=row["type_"],
        ai_score=row["task_score"],
    ), axis=1)

    sorted_df = added_df.sort_values(by="total_score", ascending=False)
    distinct_cards_df = sorted_df.drop_duplicates(subset=['card_name'], keep='first')
    
    # 從去重後的結果中選取前三名
    top_df = distinct_cards_df.head(3)
    top_df["total_score"] = top_df["total_score"].apply(lambda x: f"{x:.2f}")
        # 組合回饋趴數（選擇要顯示哪一個或加總/文字串）
    top_df["總回饋"] = top_df.apply(
            lambda row: f"{float(row['basic_pt']) + float(row['bonus_pt'])}%", axis=1
        )
    print(top_df)
        # 只輸出所需欄位
    result = top_df[["card_name","store", "總回饋", "task","total_score"]]
    
    return added_df, result