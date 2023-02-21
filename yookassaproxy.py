from flask import Flask, request, redirect, Response
from yookassa import Configuration, Payment
import sqlite3
import os.path
import uuid
import json

app = Flask(__name__)

with open('config.json') as config_file:
    config = json.load(config_file)

Configuration.account_id = config['yookassaAccountID']
Configuration.secret_key = config['yookassaSecretKey']
connectionToken = config['connectionToken']
database = config['database']
debug = config['debug']
domain = config['domain']

if debug:
    port = config['port']
    url = "http://"+domain+":"+str(port)+"/"
else:
    url = "http://"+domain+"/"

return_url = url + "backtalk"

def initDatabase():
    if not os.path.isfile(database):
        schema = """
            CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paymentID TEXT,
            isWebView boolean DEFAULT false
            )
        """
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute(schema)
        conn.commit()
        print("DB created")
        conn.close()

@app.route('/wp-json/avito/v1/getNewOrderId')
def paymentCreate():
    if 'amount' in request.args:
        amount = request.args.get('amount')
        if not amount.replace(',', '').replace('.', '').isnumeric():
            return '{"status":"error","message":"Amount is not a number"}'
    else:
        return '{"status":"error","message":"Missed argument"}'
    if 'token' not in request.args:
        return '{"status":"error","message":"Missed token"}'
    else:
        if request.args.get('token') != connectionToken:
            return '{"status":"error","message":"Invalid token"}'
    initDatabase()
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO payments DEFAULT VALUES""")
    conn.commit()
    rowid = cursor.lastrowid
    try:
        payment = Payment.create({
            "amount": {
                "value": amount,
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url+"?id="+str(rowid)
            },
            "capture": True,
            "description": "Благотворительное пожертвование"
        }, uuid.uuid4())
    except:
        return '{"status":"error","message":"Could not create payment"}'
    if 'isWebView' in request.args:
        if request.args.get('isWebView') == "true":
            query = """UPDATE payments SET paymentID = ?, isWebView = true WHERE id = ?;"""
            cursor.execute(query, (str(payment.id), str(rowid),))
        else:
            query = """UPDATE payments SET paymentID = ? WHERE id = ?;"""
            cursor.execute(query, (str(payment.id), str(rowid),))
    else:
        query = """UPDATE payments SET paymentID = ? WHERE id = ?;"""
        cursor.execute(query, (str(payment.id), str(rowid),))
    conn.commit()
    conn.close()
    return Response('{"status":"ok","result":{"orderId":"'+str(payment.id)+'"}}', mimetype='application/json')

@app.route('/wp-json/avito/v1/checkDonationStatus')
def paymentCheck():
    if 'orderId' not in request.args:
        return '{"status":"error","message":"Missed argument"}'
    if 'token' not in request.args:
        return '{"status":"error","message":"Missed token"}'
    else:
        if request.args.get('token') != connectionToken:
            return '{"status":"error","message":"Invalid token"}'
    paymentID = request.args.get('orderId')
    try:
        payment = Payment.find_one(paymentID)
    except:
        return '{"status":"error","result":{"orderStatus":"not found"}}'
    return Response('{"status":"ok","result":{"orderStatus":"'+str(payment.status)+'"}}', mimetype='application/json')

@app.route('/kindness-badge')
def paymentURL():
    if 'orderId' not in request.args:
        return '{"status":"error","message":"Missed argument"}'
    paymentID = request.args.get('orderId')
    payment = Payment.find_one(paymentID)
    #по какому коду перенаправляем?
    return redirect(payment.confirmation.confirmation_url, code=302)


@app.route('/backtalk')
def paymentparse():
    if 'id' not in request.args:
        return '{"status":"error","message":"Missed argument"}'
    rowid = request.args.get('id')
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    query = """SELECT paymentID, isWebView FROM payments WHERE id = ?"""
    cursor.execute(query, (rowid,))
    result = cursor.fetchall()
    conn.close()
    if result[0][1] == False:
        return redirect("https://www.avito.ru/kindness-badge?mode=checkDonationPage&orderId="+str(result[0][0]), code=302)
    else:
        return redirect("ru.avito://1/webview?url=https%3A%2F%2Fwww.avito.ru%2Fkindness-badge%3Fmode%3DcheckDonationPage%26orderId%3D"+str(result[0][0])+"&mavAuth=true", code=302)

application = app

if __name__ == '__main__':
    if debug:
        app.run(host=domain, port=port, debug=debug)
    else:
        app.run(debug=debug)