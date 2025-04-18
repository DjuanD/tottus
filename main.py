import os
import time
import random
import pandas as pd
import undetected_chromedriver as uc
from flask import Flask, request
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
modo_busqueda = {}
app = Flask(__name__)

def start(update: Update, context):
    botones = [
        [InlineKeyboardButton("🔍 Buscar por MARCA", callback_data='marca')],
        [InlineKeyboardButton("🔍 Buscar por PRODUCTO", callback_data='producto')]
    ]
    update.message.reply_text("¿Cómo deseas buscar?", reply_markup=InlineKeyboardMarkup(botones))

def elegir_modo(update: Update, context):
    query = update.callback_query
    modo_busqueda[query.from_user.id] = query.data
    query.answer()
    query.message.reply_text(f"Escribe la {query.data.upper()} que deseas buscar:")

def manejar_texto(update: Update, context):
    user_id = update.message.from_user.id
    texto = update.message.text.strip().upper()
    if user_id not in modo_busqueda:
        update.message.reply_text("Usa /start para elegir búsqueda.")
        return

    modo = modo_busqueda[user_id]
    update.message.reply_text(f"🔎 Buscando {modo}: {texto}, por favor espera...")

    resultados = ejecutar_scraping(modo, texto)
    if not resultados:
        update.message.reply_text("❌ No se encontraron resultados.")
        return

    for mensaje in resultados:
        update.message.reply_text(mensaje, parse_mode="Markdown")

def ejecutar_scraping(modo, valor):
    df_productos = pd.read_excel("productos.xlsx")
    df_tiendas = pd.read_excel("tiendas_tottus.xlsx")

    if modo == "marca":
        productos = df_productos[df_productos["MARCA"].str.upper() == valor]
    else:
        productos = df_productos[df_productos["PRODUCTO"].str.upper().str.contains(valor)]

    if productos.empty:
        return []

    codigos = productos["CODIGO"].astype(str).tolist()
    opciones = uc.ChromeOptions()
    opciones.add_argument("--headless=new")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--window-size=1920x1080")

    driver = uc.Chrome(options=opciones)
    resultados = []

    for codigo in codigos:
        mensaje = f"*Código:* `{codigo}`\n"
        for _, tienda in df_tiendas.iterrows():
            try:
                driver.get(tienda["manual"])
                time.sleep(random.uniform(2, 3))

                input_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "outlined-error"))
                )
                input_box.clear()
                input_box.send_keys(codigo)

                boton = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "vpirIQmyDNzjQV2QMrJQ"))
                )
                boton.click()

                nombre = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "RKoA3grvPxhJJPGskAZd"))
                ).text

                precio = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[price]"))
                ).get_attribute("price")

                mensaje += f"🏬 *{tienda['tienda']}*: {nombre} - S/. {precio}\n"
            except:
                mensaje += f"🏬 *{tienda['tienda']}*: ❌ Sin resultados\n"
        resultados.append(mensaje)

    driver.quit()
    return resultados

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot funcionando."

dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(elegir_modo))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, manejar_texto))
from flask import Flask
import threading

app = Flask(__name__)

# Inicia tu bot en un hilo separado
def start_bot():
    import tu_script_bot  # importa y lanza tu bot desde aquí

threading.Thread(target=start_bot).start()

@app.route("/")
def home():
    return "Bot activo"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

