from safe_utils import calculate_total_score, calculate_total_score_mc
from db import create_connection

def append_platform(df):
    """
    給定一個包含 'card_name' 和 'store' 欄位的 DataFrame，
    逐筆查詢資料庫取得對應的 platform，並新增 'platform' 欄位。
    """
    conn = create_connection()
    cursor = conn.cursor()
    platforms = []
    for _, row in df.iterrows():
        query = f"""
        SELECT DISTINCT
            p.platform 
        FROM
            `Platform` AS p
        JOIN
            Card AS c ON c.card_id = p.card_id
        JOIN
            Main AS m ON m.card_id = c.card_id
        WHERE c.card_name LIKE %s AND p.store LIKE %s
        """
        params = (
           f"%{row['card_name']}%", f"%{row['store']}%"
        )
 
        cursor.execute(query, params)
        rows = cursor.fetchall()
        if rows:
            platform_list = [r[0] for r in rows]
            platforms.append(", ".join(platform_list))
        else:
            platforms.append(None)
    cursor.close()
    conn.close()
    df["platform"] = platforms
    return df


def cal_total_score(added_df):
    added_df["total_score"] = added_df.apply(
        lambda row: calculate_total_score(
            basic_pt=row["basic_pt"],
            bonus_pt=row["bonus_pt"],
            type=row["type"],
            ai_score=row["task_score"],
            diver=row["diver"],
            cooper=row["cooper"]
        ),
        axis=1,
    )

    top_df = added_df.sort_values(by="total_score", ascending=False).head(3)
    top_df["total_score"] = top_df["total_score"].apply(lambda x: f"{x:.2f}")
    top_df["總回饋"] = top_df.apply(
        lambda row: f"{float(row['basic_pt']) + float(row['bonus_pt'])}%", axis=1
    )

    result = top_df[["card_name", "store", "總回饋", "task", "total_score"]]
    result = append_platform(result)
    return result


def cal_total_scoremc(added_df):
    added_df["total_score"] = added_df.apply(
        lambda row: calculate_total_score_mc(
            basic_pt=row["basic_pt"],
            bonus_pt=row["bonus_pt"],
            type=row["type"],
            ai_score=row["task_score"],
        ),
        axis=1,
    )

    top_df = added_df.sort_values(by="total_score", ascending=False).head(3)
    top_df["total_score"] = top_df["total_score"].apply(lambda x: f"{x:.2f}")
    top_df["總回饋"] = top_df.apply(
        lambda row: f"{float(row['basic_pt']) + float(row['bonus_pt'])}%", axis=1
    )

    result = top_df[["card_name", "store", "總回饋", "task", "total_score"]]
    result = append_platform(result)
    return result