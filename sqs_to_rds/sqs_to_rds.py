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


def do_insert(values_list, sql_string):
    try:
        mycursor.executemany(sql_string, values_list)
    except mysql.connector.IntegrityError as e:
        if "Duplicate entry" not in e.msg:
            raise
        return True
    else:
        return True


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

plays_sql = "insert into play_orchestrators (play_id, run_type, start_time_local, start_time_utc) VALUES (%s, %s, %s, %s)"
instances_sql = "insert into instance_results (instance_id, average_buy_price, average_sell_price, bought_value, buy_order_count, play_config_name, run_id, sell_order_count, sell_order_filled_count, sold_value, symbol, symbol_group, total_gain, units, weather_condition) VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s,%s, %s, %s, %s, %s, %s)"

bulk_plays = []
bulk_instances = []


# while True
#   are there more messages?
#       no
#           do we have any buffered?
#               yes - do insert
#               no - sleep 10s
#       yes:
#          get the messages
#           hold on to the message IDs
#           add to list of rows to insert
#           have we now got 100 rows?
#               do insert
#   sleep 10s
#
# func do insert
#       insert them
#       delete the message IDs
#       clear message IDs and rows


sqs = boto3.resource("sqs")

instances = []
plays = []
handles = []
queue = sqs.Queue(store.get("/tabot/telemetry/queue/backtest"))
"""
for m in queue.receive_messages(MaxNumberOfMessages=10):
    body = m.body
    body_json = json.loads(body)

    event = body_json["event"].lower()
    if event == "play start":
        plays.append(
            (
                body_json["play_id"],
                body_json["run_type"],
                body_json["start_time_local"],
                body_json["start_time_utc"],
            )
        )

        # insert_play_orchestrator(**body_json)
    elif event == "instance terminated":
        instances.append(
            (
                body_json["instance_id"],
                body_json["average_buy_price"],
                body_json["average_sell_price"],
                body_json["bought_value"],
                body_json["buy_order_count"],
                body_json["play_config_name"],
                body_json["run_id"],
                body_json["sell_order_count"],
                body_json["sell_order_filled_count"],
                body_json["sold_value"],
                body_json["symbol"],
                body_json["symbol_group"],
                body_json["total_gain"],
                body_json["units"],
                body_json["weather_condition"],
            )
        )
        # insert_instance_terminated(**body_json)

    handles.append({"Id": m.message_id, "ReceiptHandle": m.receipt_handle})
    # Let the queue know that the message is processed
    # message.delete()

if plays:
    if not do_insert(plays, plays_sql):
        print("Insert failure!")
    # print(f"Plays insert for {time.time() - last} seconds")
    last = time.time()
if instances:
    if not do_insert(instances, instances_sql):
        print("Insert failure!")
    print(f"Instances insert for {time.time() - last} seconds")
    last = time.time()

if plays or instances:
    mydb.commit()
    queue.delete_messages(entries=handles)
# sqs.delete_message_batch(QueueUrl=queue_url, Entries=delete_batch)
"""

while True:
    last = time.time()
    messages = sqs_client.receive_message(
        QueueUrl=sqs_queue_url, MaxNumberOfMessages=10
    )
    print(f"SQS recv {time.time() - last} seconds")
    last = time.time()

    try:
        messages["Messages"]
    except KeyError:
        pass
    else:
        # plays = []
        # instances = []
        for m in messages["Messages"]:
            body = m["Body"]
            body_json = json.loads(body)

            event = body_json["event"].lower()
            if event == "play start":
                bulk_plays.append(
                    (
                        body_json["play_id"],
                        body_json["run_type"],
                        body_json["start_time_local"],
                        body_json["start_time_utc"],
                    )
                )

                # insert_play_orchestrator(**body_json)
            elif event == "instance terminated":
                bulk_instances.append(
                    (
                        body_json["instance_id"],
                        body_json["average_buy_price"],
                        body_json["average_sell_price"],
                        body_json["bought_value"],
                        body_json["buy_order_count"],
                        body_json["play_config_name"],
                        body_json["run_id"],
                        body_json["sell_order_count"],
                        body_json["sell_order_filled_count"],
                        body_json["sold_value"],
                        body_json["symbol"],
                        body_json["symbol_group"],
                        body_json["total_gain"],
                        body_json["units"],
                        body_json["weather_condition"],
                    )
                )
                # insert_instance_terminated(**body_json)

        sqs_client.delete_message_batch(
            QueueUrl=sqs_queue_url,
            Entries=[
                {"Id": d["MessageId"], "ReceiptHandle": d["ReceiptHandle"]}
                for d in messages["Messages"]
            ],
        )
        print(f"SQS clear ran for {time.time() - last} seconds")

    # time.sleep(2)
if plays:
    if not do_insert(plays, plays_sql):
        print("Insert failure!")
    print(f"Plays insert for {time.time() - last} seconds")
    last = time.time()
if instances:
    if not do_insert(instances, instances_sql):
        print("Insert failure!")
    print(f"Instances insert for {time.time() - last} seconds")
    last = time.time()

last = time.time()
mydb.commit()
print(f"Commit ran for {time.time() - last} seconds")
print(f"Committed {len(plays)} plays and {len(instances)} instances")
