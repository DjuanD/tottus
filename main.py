import os
import telebot
from telebot import types
import pandas as pd
from flask import Flask, request, jsonify
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from openpyxl.styles import PatternFill
from openpyxl import load_workbook

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)
user_step = {}
app = Flask(__name__)

# Configuración para Cloud Run
PORT = int(os.environ.get("PORT", 8080))

# Cargar productos y tiendas (usa rutas absolutas para producción)
try:
    productos_df = pd.read_excel("productos.xlsx")
    tiendas_df = pd.read_excel("tiendas_tottus.xlsx")
except Exception as e:
    print(f"Error cargando archivos: {e}")
    productos_df = pd.DataFrame()
    tiendas_df = pd.DataFrame()

# Configuración de Chrome para Cloud Run
def configurar_chrome():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=375,812")
    chrome_options.binary_location = os.getenv("GOOGLE_CHROME_BIN")
    return webdriver.Chrome(
        executable_path=os.getenv("CHROMEDRIVER_PATH"),
        options=chrome_options
    )

# ---- Funciones de scraping ----
def hacer_scraping(filtro, tipo):
    if productos_df.empty or tiendas_df.empty:
        return "Error: No se cargaron los datos correctamente"

    resultados = []
    productos_filtrados = productos_df[productos_df[tipo].str.contains(filtro, case=False, na=False)]

    for _, producto in productos_filtrados.iterrows():
        codigo = str(producto['CODIGO'])
        nombre_producto = producto['PRODUCTO']
        marca = producto['MARCA']

        for _, tienda in tiendas_df.iterrows():
            driver = configurar_chrome()
            try:
                driver.get(tienda['tienda'])
                search_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "search"))
                )
                search_input.send_keys(codigo)
                search_input.submit()

                precio = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-price"))
                ).text
                
                resultados.append({
                    'CODIGO': codigo,
                    'PRODUCTO': nombre_producto,
                    'MARCA': marca,
                    'TIENDA': tienda['manual'],
                    'PRECIO': precio
                })
            except Exception as e:
                resultados.append({
                    'CODIGO': codigo,
                    'PRODUCTO': nombre_producto,
                    'MARCA': marca,
                    'TIENDA': tienda['manual'],
                    'PRECIO': f"Error: {str(e)}"
                })
            finally:
                driver.quit()

    # (Mantén el resto de tu lógica de guardado y formato)
    return "resultados.xlsx"

# ---- Telegram Handlers ----
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Buscar por producto", "Buscar por marca")
    bot.send_message(message.chat.id, "¿Cómo quieres buscar?", reply_markup=markup)

# (Mantén los demás handlers igual)

# ---- Flask Endpoints ----
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Bot Tottus activo"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# ---- Configuración para producción ----
def run_bot():
    if os.getenv("ENVIRONMENT") == "production":
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://your-service-url.a.run.app/webhook")
    else:
        bot.infinity_polling()

if __name__ == '__main__':
    if os.getenv("ENVIRONMENT") == "production":
        # Modo producción (Cloud Run)
        threading.Thread(target=run_bot).start()
        app.run(host='0.0.0.0', port=PORT)
    else:
        # Modo desarrollo local
        run_bot()
