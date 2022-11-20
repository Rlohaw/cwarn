import json
from telebot import async_telebot
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import re
import mysql.connector
import asyncio


class DataBase:
    __cls = None

    def __new__(cls, *args, **kwargs):
        if cls.__cls is None:
            cls.__cls = super().__new__(cls)
        return cls.__cls

    def __init__(self, host='', user='', password='', database=''):
        self.mydb = mysql.connector.connect(host=host,
                                            user=user,
                                            password=password,
                                            database=database)
        self.cursor = self.mydb.cursor()

    def del_level(self, name, price):
        self.cursor.execute(f'delete from orders where name="{name.upper()}" and price={price}')
        self.mydb.commit()

    def create_level(self, name, price):
        self.cursor.execute(f'insert into orders(name, price) values ("{name.upper()}",{price})')
        self.mydb.commit()

    def get_levels(self):
        self.cursor.execute(f'select * from orders')
        return tuple(self.cursor)


class Price:
    def __init__(self, url='', coins=[],
                 convert='USD', api=''):
        self.url = url
        self.parameters = {'symbol': ','.join(coins),
                           'convert': convert}
        self.headers = {'Accepts': 'application/json',
                        'X-CMC_PRO_API_KEY': api}

    def get_price(self, coins=[]):
        session = Session()
        session.headers.update(self.headers)
        try:
            response = session.get(self.url, params=self.parameters)
            data = json.loads(response.text)
            res = {i: data['data'][i.upper()]['quote']['USD']['price'] for i in coins}
            return res
        except (ConnectionError, Timeout, TooManyRedirects, KeyError) as e:
            print(e)


token = ''
bot = async_telebot.AsyncTeleBot(token)
database = DataBase()


def eq(a, b, diff=0.05):
    res = 1 - (min(a, b) / max(a, b))
    return res <= diff


@bot.message_handler(commands=['set'])
async def set_price(msg):
    if msg.chat.id == 'userid':
        txt = msg.text.replace('/set ', '')
        if re.fullmatch(r'\w+: \d+\.?\d*', txt):
            coin = re.search(r'\w+', txt).group().upper()
            price = float(re.search(r'\d+\.?\d*', txt).group())
            if (coin, price) not in database.get_levels():
                database.create_level(coin, price)
            else:
                await bot.send_message('userid', 'Already created')


@bot.message_handler(commands=['del'])
async def del_price(msg):
    if msg.chat.id == 'userid':
        txt = msg.text.replace('/del ', '')
        if re.fullmatch(r'\w+: \d+\.?\d*', txt):
            coin = re.search(r'\w+', txt).group().upper()
            price = float(re.search(r'\d+\.?\d*', txt).group())
            if (coin, price) in database.get_levels():
                database.del_level(coin, price)
            else:
                await bot.send_message('userid', 'Not found')


@bot.message_handler(commands=['scan'])
async def scan(msg):
    while True:
        levels = database.get_levels()
        coins = list(set(map(lambda x: x[0], levels)))
        prices_dct = Price(coins=coins).get_price(coins=coins)
        res = list(filter(lambda x: eq(x[1], prices_dct[x[0]]), levels))
        if res:
            message = '\n'.join(map(lambda x: ' ||| '.join([*map(str, x), str(round(prices_dct[x[0]], 3))]), res))
            [database.del_level(*i) for i in res]
            await bot.send_message('userid', message)
        await asyncio.sleep(900)


@bot.message_handler(commands=['show'])
async def show(msg):
    levels = database.get_levels()
    coins = list(set(map(lambda x: x[0], levels)))
    prices_dct = Price(coins=coins).get_price(coins=coins)
    message = '\n'.join(map(lambda x: ' ||| '.join([*map(str, x), str(round(prices_dct[x[0]], 3))]), levels))
    await bot.send_message('userid', message)


while True:
    try:
        asyncio.run(bot.polling(non_stop=True))
    except Exception as e:
        print(e)
