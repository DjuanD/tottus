import os
import telebot
from telebot import types
import pandas as pd
from flask import Flask
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)
user_step = {}

# Cargar productos y tiendas
productos_df = pd.read_excel("productos.xlsx")
tiendas_df = pd.read_excel("tiendas_tottus.xlsx")

# Función para formatear los resultados como texto
def format_results(resultados):
    message = "🔍 Resultados de la búsqueda:\n\n"
    for producto in resultados:
        message += f"📌 *{producto['PRODUCTO']}* ({producto['MARCA']})\n"
        message += f"🆔 Código: `{producto['CODIGO']}`\n"
        message += "🏪 Precios por tienda:\n"
        
        for tienda, precio in producto['TIENDAS'].items():
            message += f"  • {tienda}: {precio}\n"
        
        message += "\n" + "─" * 30 + "\n"
    return message

# Función de scraping modificada
def hacer_scraping(filtro, tipo):
    resultados = []

    productos_filtrados = productos_df[productos_df[tipo].str.contains(filtro, case=False, na=False)]
    
    for _, producto in productos_filtrados.iterrows():
        codigo = str(producto['CODIGO'])
        nombre_producto = producto['PRODUCTO']
        marca = producto['MARCA']
        
        precios_tiendas = {}
        
        for _, tienda in tiendas_df.iterrows():
            url = tienda['tienda']
            nombre_tienda = tienda['manual']

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--window-size=375,812")

            driver = webdriver.Chrome(options=options)
            try:
                driver.get(url)
                search_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "search"))
                )
                search_input.send_keys(codigo)
                search_input.submit()

                time.sleep(3)

                precio_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-price"))
                )
                precio = precio_element.text
            except Exception as e:
                precio = "No disponible"
            finally:
                driver.quit()

            precios_tiendas[nombre_tienda] = precio

        resultados.append({
            'CODIGO': codigo,
            'PRODUCTO': nombre_producto,
            'MARCA': marca,
            'TIENDAS': precios_tiendas
        })

    return resultados

# Handlers de Telegram
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Buscar por producto", "Buscar por marca")
    bot.send_message(message.chat.id, "¿Cómo quieres buscar?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Buscar por producto", "Buscar por marca"])
def elegir_busqueda(message):
    tipo = "PRODUCTO" if "producto" in message.text.lower() else "MARCA"
    user_step[message.chat.id] = tipo
    bot.send_message(message.chat.id, f"Escribe el {tipo.lower()} que deseas buscar:")

@bot.message_handler(func=lambda m: m.chat.id in user_step)
def recibir_filtro(message):
    tipo = user_step.pop(message.chat.id)
    msg = bot.send_message(message.chat.id, "🔎 Buscando productos, por favor espera...")
    
    resultados = hacer_scraping(message.text, tipo)
    
    if not resultados:
        bot.edit_message_text("❌ No se encontraron resultados.", chat_id=msg.chat.id, message_id=msg.message_id)
        return
    
    # Formatear y enviar resultados
    respuesta = format_results(resultados)
    bot.edit_message_text(respuesta, chat_id=msg.chat.id, message_id=msg.message_id, parse_mode="Markdown")

# Configuración de Flask para Cloud Run
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Tottus activo"

def iniciar_bot():
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=iniciar_bot).start()
    app.run(host='0.0.0.0', port=8080)
