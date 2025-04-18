import os
import telebot
from telebot import types
import pandas as pd
from flask import Flask, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Configuración inicial
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
user_step = {}

# Carga de datos (usa rutas absolutas en producción)
def cargar_datos():
    try:
        productos_df = pd.read_excel("productos.xlsx")
        tiendas_df = pd.read_excel("tiendas_tottus.xlsx")
        return productos_df, tiendas_df
    except Exception as e:
        print(f"Error cargando archivos: {e}")
        return pd.DataFrame(), pd.DataFrame()

productos_df, tiendas_df = cargar_datos()

# Configuración de Chrome para Cloud Run
def get_chrome_driver():
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

# Función de scraping optimizada
def hacer_scraping(filtro, tipo):
    resultados = []
    productos_filtrados = productos_df[productos_df[tipo].str.contains(filtro, case=False, na=False)]

    for _, producto in productos_filtrados.iterrows():
        codigo = str(producto['CODIGO'])
        precios_tiendas = {}

        for _, tienda in tiendas_df.iterrows():
            driver = get_chrome_driver()
            try:
                driver.get(tienda['tienda'])
                
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "search"))
                ).send_keys(codigo)
                
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                ).click()
                
                precio = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".product-price"))
                ).text
                
                precios_tiendas[tienda['manual']] = precio
                
            except Exception as e:
                precios_tiendas[tienda['manual']] = f"Error: {str(e)}"
            finally:
                driver.quit()

        resultados.append({
            'Producto': producto['PRODUCTO'],
            'Marca': producto['MARCA'],
            'Código': codigo,
            'Precios': precios_tiendas
        })
        time.sleep(1)  # Espera entre productos

    return resultados

# Formatear resultados para Telegram
def format_results(resultados):
    msg = "🔍 *Resultados encontrados:*\n\n"
    for item in resultados:
        msg += f"📦 *{item['Producto']}* ({item['Marca']})\n"
        msg += f"🆔 Código: `{item['Código']}`\n"
        msg += "🏪 *Precios:*\n"
        for tienda, precio in item['Precios'].items():
            msg += f"  • {tienda}: _{precio}_\n"
        msg += "\n"
    return msg

# Handlers de Telegram
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Buscar por producto", "Buscar por marca")
    bot.send_message(message.chat.id, "Selecciona el tipo de búsqueda:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["Buscar por producto", "Buscar por marca"])
def set_search_type(message):
    search_type = "PRODUCTO" if "producto" in message.text.lower() else "MARCA"
    user_step[message.chat.id] = search_type
    bot.send_message(message.chat.id, f"🔎 Escribe el {search_type.lower()} a buscar:")

@bot.message_handler(func=lambda m: m.chat.id in user_step)
def handle_search(message):
    search_type = user_step.pop(message.chat.id)
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        resultados = hacer_scraping(message.text, search_type)
        if not resultados:
            bot.send_message(message.chat.id, "❌ No se encontraron resultados")
            return
            
        response = format_results(resultados)
        bot.send_message(message.chat.id, response, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error: {str(e)}")

# Endpoints para Cloud Run
@app.route('/', methods=['GET'])
def health_check():
    return "Bot activo", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# Inicialización
def initialize_bot():
    if os.getenv('ENVIRONMENT') == 'production':
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"https://{os.getenv('SERVICE_URL')}/webhook")

if __name__ == '__main__':
    initialize_bot()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
