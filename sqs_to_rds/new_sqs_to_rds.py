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


import aiobotocore
import json
import logging
import asyncio

max_queue_messages = 10


async def poll_queue(client):
    while True:
        try:
            # This loop wont spin really fast as there is
            # essentially a sleep in the receieve_message call
            response = await client.receive_message(
                QueueUrl=queue,
                WaitTimeSeconds=2,
            )

            if "Messages" in response:
                for msg in response["Messages"]:
                    # print('Got msg "{0}"'.format(msg['Body']))
                    print("got queue message")
            else:
                print("No messages in queue")
        except KeyboardInterrupt:
            break

    print("Finished")
    await client.close()


def func1():
    loop = asyncio.get_event_loop()
    session = aiobotocore.get_session(loop=loop)
    client = session.create_client("sqs")
    asyncio.ensure_future(poll_queue(client))


# async def hello(request):
#    return web.Response(text="Hello, world")


def func2():
    #    app.add_routes([web.get("/", hello)])
    print("Starting web Server")


#    web.run_app(app, host="127.0.0.1", port=5000)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)

    func1()
    func2()

    loop.run_forever()
