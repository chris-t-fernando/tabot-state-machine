import boto3
import time
import json
import mysql.connector

# need to add a unique ID per instance
# need to add the datetime that the instance started and ended
def insert_instance_terminated(
    average_buy_price,
    average_sell_price,
    bought_value,
    buy_order_count,
    play_config_name,
    run_id,
    sell_order_count,
    sell_order_filled_count,
    sold_value,
    symbol,
    symbol_group,
    total_gain,
    units,
    weather_condition,
):
    vals = (
        average_buy_price,
        average_sell_price,
        bought_value,
        buy_order_count,
        play_config_name,
        run_id,
        sell_order_count,
        sell_order_filled_count,
        sold_value,
        symbol,
        symbol_group,
        total_gain,
        units,
        weather_condition,
    )
    sql = "insert into instance_results (average_buy_price, average_sell_price, bought_value, buy_order_count, play_config_name, run_id, sell_order_count, sell_order_filled_count, sold_value, symbol, symbol_group, total_gain, units, weather_condition) VALUES (%s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s, %s, %s)"
    try:
        mycursor.execute(sql, vals)
    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" not in e.msg:
            raise
    else:
        print(f"New instance result: \t\t{run_id} symbol {symbol}")


def insert_play_orchestrator(
    play_id, run_type, start_time_local, start_time_utc, **kwargs
):
    vals = (play_id, run_type, start_time_local, start_time_utc)
    sql = "insert into play_orchestrators (play_id, run_type, start_time_local, start_time_utc) VALUES (%s, %s, %s, %s)"
    try:
        mycursor.execute(sql, vals)
    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" not in e.msg:
            raise
    else:
        print(f"New Play Orchestrator: \t\t{play_id}")


sqs_client = boto3.client("sqs")
sqs_queue_url = (
    "https://sqs.ap-southeast-2.amazonaws.com/036372598227/tabot_backtest.fifo"
)

mydb = mysql.connector.connect(
    host="jtweets.ciizausrav91.us-west-2.rds.amazonaws.com",
    user="jtweets",
    password="jtweets1",
    database="tabot_results",
)
mycursor = mydb.cursor()

# mycursor.execute(
#    "CREATE TABLE play_orchestrators (play_id VARCHAR(30) PRIMARY KEY, run_type VARCHAR(255), start_time_local DATETIME, start_time_utc DATETIME)"
# )

while True:
    messages = sqs_client.receive_message(
        QueueUrl=sqs_queue_url, MaxNumberOfMessages=10
    )
    try:
        messages["Messages"]
    except KeyError:
        pass
    else:
        for m in messages["Messages"]:
            body = m["Body"]
            body_json = json.loads(body)

            if body_json["event"] == "Play start":
                insert_play_orchestrator(**body_json)
            elif body_json["event"] == "Instance terminated":
                insert_instance_terminated(**body_json)

        mydb.commit()
    time.sleep(2)
