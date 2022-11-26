import boto3
import time
import json
import mysql.connector
from parameter_store import Ssm

# need to add a unique ID per instance
# need to add the datetime that the instance started and ended
def insert_instance_terminated(
    average_buy_price,
    average_sell_price,
    bought_value,
    buy_order_count,
    instance_id,
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
    **kwargs,
):
    vals = (
        instance_id,
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
    sql = "insert into instance_results (instance_id, average_buy_price, average_sell_price, bought_value, buy_order_count, play_config_name, run_id, sell_order_count, sell_order_filled_count, sold_value, symbol, symbol_group, total_gain, units, weather_condition) VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s, %s, %s)"
    try:
        mycursor.execute(sql, vals)
    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" not in e.msg:
            raise
    else:
        print(f"New instance result: \t\t{run_id} instance {instance_id}")


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


store = Ssm()

sqs_client = boto3.client("sqs")
sqs_queue_url = store.get("/tabot/telemetry/queue/backtest")

_base = "/tabot/telemetry/sql/"
mydb = mysql.connector.connect(
    host=store.get(f"{_base}host"),
    user=store.get(f"{_base}user"),
    password=store.get(f"{_base}password"),
    database=store.get(f"{_base}database"),
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

            event = body_json["event"].lower()
            if event == "play start":
                insert_play_orchestrator(**body_json)
            elif event == "instance terminated":
                insert_instance_terminated(**body_json)

        mydb.commit()
        sqs_client.delete_message_batch(
            QueueUrl=sqs_queue_url,
            Entries=[
                {"Id": d["MessageId"], "ReceiptHandle": d["ReceiptHandle"]}
                for d in messages["Messages"]
            ],
        )
    # time.sleep(2)
