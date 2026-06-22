# Use "streamlit run app.py" to launch the app, and sign up with any username/password (email is not verified, just for show).
# write "python -m venv venv" to create a virtual environment
# The app will create a local SQLite database file named "kitchen.db" in the same directory to store user data, pantry inventory, meal plans, and more. You can reset the database by deleting this file.
# "pip install streamlit anthropic requests python-dotenv google-generativeai Pillow"

import streamlit as st
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import hashlib
import sqlite3
import json
import google.generativeai as genai
from PIL import Image
import re
import textwrap
import streamlit.components.v1 as components

# ====================== LOAD ENVIRONMENT ======================
load_dotenv()
SPOONACULAR_KEYS = os.getenv('SPOONACULAR_KEYS', '')
GEMINI_API_KEYS = os.getenv('GEMINI_API_KEYS', '') or os.getenv("GOOGLE_API_KEY", '')

if 'gemini_key_index' not in st.session_state:
    st.session_state.gemini_key_index = 0

# ====================== PAGE CONFIG ======================
st.set_page_config(page_title="Smart Recipe Tracker", page_icon="🍳", layout="wide", initial_sidebar_state="collapsed")

# ====================== GLOBAL PREMIUM CSS ======================
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stToolbar"] {display: none;}
        [data-testid="collapsedControl"] {display: none !important;}
        .stApp {background-color: #0e1117; color: #ecf0f1;}
        .premium-card {
            background-color: #1a1c23; border: 1px solid #2d3139;
            padding: 20px; border-radius: 12px; margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .section-header {border-bottom: 2px solid #2d3139; padding-bottom: 8px; margin-bottom: 20px; color: #4caf50;}
    </style>
    """,
    unsafe_allow_html=True
)

# ====================== DYNAMIC FOOD EMOJI ENGINE ======================
def get_food_emoji(food_name):
    food_name = food_name.lower()
    emoji_map = {
        "chicken": "🍗", "beef": "🥩", "steak": "🥩", "lamb": "🥩", "meat": "🥩", "bacon": "🥓", "egg": "🥚", "milk": "🥛",
        "cheese": "🧀", "butter": "🧈", "rice": "🍚", "banana": "🍌", "apple": "🍎", "tomato": "🍅",
        "carrot": "🥕", "bread": "🍞", "fish": "🐟", "salmon": "🍣", "olive": "🫒", "pepper": "🫑",
        "onion": "🧅", "garlic": "🧄", "potato": "🥔", "corn": "🌽", "broccoli": "🥦", "mushroom": "🍄",
        "avocado": "🥑", "lemon": "🍋", "watermelon": "🍉", "strawberry": "🍓"
    }
    for keyword, emoji in emoji_map.items():
        if keyword in food_name:
            return emoji
    return "🍽️"

def normalize_ingredient_name(name: str) -> str:
    """The Ultimate Ultra-Comprehensive Normalization Engine for Pantry & Spoonacular"""
    if not name:
        return name
    name = name.lower().strip()

    # ==========================================
    # 1. SPECIFIC/COMPOUND INGREDIENTS 
    # ==========================================
    if any(x in name for x in ["peanut butter", "mentega kacang"]): return "Peanut Butter"
    if any(x in name for x in ["coconut milk", "santan"]): return "Coconut Milk"
    if any(x in name for x in ["coconut oil", "minyak kelapa"]): return "Coconut Oil"
    if any(x in name for x in ["almond milk", "susu badam"]): return "Almond Milk"
    if any(x in name for x in ["soy milk", "susu soya"]): return "Soy Milk"
    if any(x in name for x in ["oat milk"]): return "Oat Milk"
    if any(x in name for x in ["sweet potato", "keledek"]): return "Sweet Potato"
    if any(x in name for x in ["cherry tomato", "baby tomato"]): return "Cherry Tomato"
    if any(x in name for x in ["soy sauce", "kicap"]): return "Soy Sauce"
    if any(x in name for x in ["fish sauce", "sos ikan"]): return "Fish Sauce"
    if any(x in name for x in ["oyster sauce", "sos tiram"]): return "Oyster Sauce"
    if any(x in name for x in ["chili sauce", "sos cili", "sriracha"]): return "Chili Sauce"
    if any(x in name for x in ["tomato sauce", "ketchup", "sos tomato"]): return "Ketchup"
    if any(x in name for x in ["baking powder", "serbuk penaik"]): return "Baking Powder"
    if any(x in name for x in ["baking soda", "soda bikarbonat"]): return "Baking Soda"
    if any(x in name for x in ["vanilla extract", "vanilla essence", "esktrak vanila"]): return "Vanilla Extract"
    if any(x in name for x in ["cocoa powder", "serbuk koko"]): return "Cocoa Powder"
    
    # ==========================================
    # 2. MEAT & POULTRY
    # ==========================================
    if any(x in name for x in ["minced beef", "ground beef", "beef mince"]): return "Ground Beef"
    if any(x in name for x in ["ribeye", "rib eye", "rump", "sirloin", "tenderloin", "wagyu", "steak"]): return "Beef Steak"
    if any(x in name for x in ["beef", "daging lembu", "daging"]): return "Beef"
    
    if any(x in name for x in ["chicken breast", "dada ayam", "chicken fillet"]): return "Chicken Breast"
    if any(x in name for x in ["chicken thigh", "peha ayam", "chicken leg", "drumstick"]): return "Chicken Thigh"
    if any(x in name for x in ["chicken wing", "kepak ayam"]): return "Chicken Wing"
    if any(x in name for x in ["ground chicken", "minced chicken", "ayam cincang"]): return "Ground Chicken"
    if any(x in name for x in ["chicken", "ayam"]): return "Chicken"
    
    if any(x in name for x in ["ground pork", "minced pork", "pork mince"]): return "Ground Pork"
    if any(x in name for x in ["pork belly"]): return "Pork Belly"
    if any(x in name for x in ["bacon", "pancetta"]): return "Bacon"
    if any(x in name for x in ["ham", "prosciutto"]): return "Ham"
    if any(x in name for x in ["sausage", "sosej", "chorizo", "hotdog"]): return "Sausage"
    if any(x in name for x in ["pork", "babi", "khinzir"]): return "Pork"
    
    if any(x in name for x in ["ground lamb", "minced lamb"]): return "Ground Lamb"
    if any(x in name for x in ["lamb", "mutton", "kambing"]): return "Lamb"
    if any(x in name for x in ["duck", "itik"]): return "Duck"
    if any(x in name for x in ["turkey", "ayam belanda"]): return "Turkey"

    # ==========================================
    # 3. SEAFOOD
    # ==========================================
    if any(x in name for x in ["salmon", "ikan salmon"]): return "Salmon"
    if any(x in name for x in ["tuna", "ikan tuna"]): return "Tuna"
    if any(x in name for x in ["cod", "ikan cod"]): return "Cod"
    if any(x in name for x in ["seabass", "siakap"]): return "Seabass"
    if any(x in name for x in ["mackerel", "tenggiri"]): return "Mackerel"
    if any(x in name for x in ["anchovy", "anchovies", "ikan bilis"]): return "Anchovy"
    if any(x in name for x in ["sardine", "sardin"]): return "Sardine"
    if any(x in name for x in ["fish", "ikan"]): return "Fish"
    
    if any(x in name for x in ["shrimp", "prawn", "udang"]): return "Shrimp"
    if any(x in name for x in ["crab", "ketam"]): return "Crab"
    if any(x in name for x in ["lobster", "udang karang"]): return "Lobster"
    if any(x in name for x in ["squid", "calamari", "sotong"]): return "Squid"
    if any(x in name for x in ["octopus", "kurita"]): return "Octopus"
    if any(x in name for x in ["scallop", "kekapis"]): return "Scallop"
    if any(x in name for x in ["mussel", "clam", "oyster", "kerang", "tiram"]): return "Shellfish"

    # ==========================================
    # 4. ALLIUMS & PEPPERS
    # ==========================================
    if any(x in name for x in ["green onion", "spring onion", "scallion", "daun bawang"]): return "Green Onion"
    if any(x in name for x in ["red onion", "bawang merah"]): return "Red Onion"
    if any(x in name for x in ["yellow onion", "white onion", "brown onion", "bawang besar"]): return "Onion"
    if any(x in name for x in ["shallot"]): return "Shallot"
    if any(x in name for x in ["garlic", "bawang putih"]): return "Garlic"
    if any(x in name for x in ["leek", "leeks"]): return "Leek"
    
    if any(x in name for x in ["bell pepper", "capsicum", "red bell", "green bell", "yellow bell"]): return "Bell Pepper"
    if any(x in name for x in ["bird's eye", "cili padi"]): return "Bird's Eye Chili"
    if any(x in name for x in ["jalapeno", "habanero"]): return "Jalapeno"
    if any(x in name for x in ["chili", "chilli", "cili", "cabai"]): return "Chili Pepper"

    # ==========================================
    # 5. VEGETABLES & HERBS
    # ==========================================
    if any(x in name for x in ["potato", "potatoes", "ubi kentang"]): return "Potato"
    if "carrot" in name or "lobak merah" in name: return "Carrot"
    if "tomato" in name: return "Tomato"
    if "broccoli" in name: return "Broccoli"
    if "cauliflower" in name or "bunga kubis" in name: return "Cauliflower"
    if "cabbage" in name or "kubis" in name: return "Cabbage"
    if any(x in name for x in ["mushroom", "mushrooms", "cendawan"]): return "Mushroom"
    if any(x in name for x in ["lettuce", "salad"]): return "Lettuce"
    if "spinach" in name or "bayam" in name: return "Spinach"
    if "kale" in name: return "Kale"
    if any(x in name for x in ["zucchini", "courgette"]): return "Zucchini"
    if "cucumber" in name or "timun" in name: return "Cucumber"
    if "corn" in name or "jagung" in name: return "Corn"
    if "eggplant" in name or "aubergine" in name or "terung" in name: return "Eggplant"
    if "asparagus" in name: return "Asparagus"
    if "celery" in name or "daun saderi" in name: return "Celery"
    if "green bean" in name or "kacang buncis" in name: return "Green Bean"
    if "okra" in name or "lady finger" in name or "bendi" in name: return "Okra"
    if any(x in name for x in ["water spinach", "morning glory", "kangkung"]): return "Water Spinach"
    if any(x in name for x in ["bok choy", "pak choy", "choy sum", "sawi"]): return "Asian Greens"
    
    if "cilantro" in name or "coriander leaf" in name or "daun ketumbar" in name: return "Cilantro"
    if "parsley" in name: return "Parsley"
    if "basil" in name or "daun selasih" in name: return "Basil"
    if "mint" in name or "daun pudina" in name: return "Mint"
    if "rosemary" in name: return "Rosemary"
    if "thyme" in name: return "Thyme"
    if "oregano" in name: return "Oregano"
    if "lemongrass" in name or "serai" in name: return "Lemongrass"

    # ==========================================
    # 6. FRUITS
    # ==========================================
    if "lemon" in name: return "Lemon"
    if "lime" in name or "limau" in name: return "Lime"
    if "orange" in name or "oren" in name: return "Orange"
    if "apple" in name or "epal" in name: return "Apple"
    if "banana" in name or "pisang" in name: return "Banana"
    if "strawberry" in name: return "Strawberry"
    if "blueberry" in name: return "Blueberry"
    if "grape" in name or "anggur" in name: return "Grape"
    if "watermelon" in name or "tembikai" in name: return "Watermelon"
    if "mango" in name or "mangga" in name: return "Mango"
    if "pineapple" in name or "nanas" in name: return "Pineapple"
    if "papaya" in name or "betik" in name: return "Papaya"
    if "avocado" in name: return "Avocado"

    # ==========================================
    # 7. DAIRY & ALTERNATIVES
    # ==========================================
    if any(x in name for x in ["egg", "telur"]): return "Egg"
    if "milk" in name or "susu" in name: return "Milk"
    if "butter" in name or "mentega" in name: return "Butter"
    if "ghee" in name or "minyak sapi" in name: return "Ghee"
    if any(x in name for x in ["yogurt", "yoghurt", "greek yoghurt", "greek yogurt"]): return "Greek Yogurt"
    if any(x in name for x in ["parmesan", "mozzarella", "cheddar", "feta", "brie"]): return "Cheese"
    if any(x in name for x in ["cheese", "keju"]): return "Cheese"
    if "cream" in name or "krim" in name: return "Cream"

    # ==========================================
    # 8. CARBS, GRAINS, PASTA & BREAD
    # ==========================================
    if any(x in name for x in ["brown rice", "basmati", "jasmine rice", "sushi rice"]): return "Rice"
    if any(x in name for x in ["rice", "nasi", "beras"]): return "Rice"
    if "quinoa" in name: return "Quinoa"
    if "oat" in name or "oatmeal" in name: return "Oats"
    if any(x in name for x in ["spaghetti", "macaroni", "penne", "pasta"]): return "Pasta"
    if any(x in name for x in ["noodle", "mee", "bihun", "kuey teow", "vermicelli", "ramen", "udon"]): return "Noodles"
    if any(x in name for x in ["bread", "roti", "baguette", "sourdough", "bun"]): return "Bread"
    if any(x in name for x in ["tortilla", "wrap", "pita"]): return "Tortilla"

    # ==========================================
    # 9. PANTRY, SPICES, NUTS & MISC
    # ==========================================
    if any(x in name for x in ["corn flour", "tepung jagung", "cornstarch"]): return "Corn Flour"
    if any(x in name for x in ["wheat flour", "all purpose flour", "flour", "tepung gandum", "tepung"]): return "Flour"
    if any(x in name for x in ["olive oil", "minyak zaitun"]): return "Olive Oil"
    if any(x in name for x in ["sesame oil", "minyak bijan"]): return "Sesame Oil"
    if any(x in name for x in ["oil", "minyak"]): return "Oil"
    
    if any(x in name for x in ["brown sugar", "gula merah", "gula perang"]): return "Brown Sugar"
    if any(x in name for x in ["sugar", "gula"]): return "Sugar"
    if any(x in name for x in ["honey", "madu"]): return "Honey"
    if "maple syrup" in name: return "Maple Syrup"
    
    if any(x in name for x in ["tofu", "tauhu"]): return "Tofu"
    if "tempeh" in name: return "Tempeh"
    if "ginger" in name or "halia" in name: return "Ginger"
    if "galangal" in name or "lengkuas" in name: return "Galangal"
    if "turmeric" in name or "kunyit" in name: return "Turmeric"
    if "cinnamon" in name or "kayu manis" in name: return "Cinnamon"
    if "cumin" in name or "jintan putih" in name: return "Cumin"
    if "coriander powder" in name or "ketumbar" in name: return "Coriander"
    if "black pepper" in name or "lada hitam" in name: return "Black Pepper"
    if "white pepper" in name or "lada putih" in name: return "White Pepper"
    if "salt" in name or "garam" in name: return "Salt"
    
    if any(x in name for x in ["peanut", "kacang tanah"]): return "Peanut"
    if any(x in name for x in ["almond", "badam"]): return "Almond"
    if "cashew" in name or "gajus" in name: return "Cashew"
    if "walnut" in name: return "Walnut"
    if "chia seed" in name: return "Chia Seed"
    if "sesame seed" in name or "bijan" in name: return "Sesame Seed"
    if "vinegar" in name or "cuka" in name: return "Vinegar"
    if "mayonnaise" in name or "mayo" in name: return "Mayonnaise"
    if "mustard" in name: return "Mustard"

    # ==========================================
    # 10. GENERAL CLEANUP FOR UNHANDLED ITEMS
    # ==========================================
    descriptors = [
        "fresh", "organic", "frozen", "chilled", "diced", "sliced", "chopped", 
        "minced", "ground", "grated", "shredded", "low fat", "fat free", "extra lean", 
        "boneless", "skinless", "whole", "raw", "cooked", "canned", "dried", 
        "australia", "australian", "brand", "premium", "sweet", "spicy", "salted", 
        "unsalted", "roasted", "fried", "peeled", "halves", "pieces"
    ]
    for d in descriptors:
        import re
        name = re.sub(rf'\b{d}\b', '', name)
    
    name = name.strip()
    
    if name.endswith("s") and not name.endswith(("ss", "us", "as", "is", "os")):
        if name.endswith("ies"):
            name = name[:-3] + "y"  # strawberries -> strawberry
        elif name.endswith("es") and not name.endswith(("ches", "shes", "xes")):
            name = name[:-2]       
        else:
            name = name[:-1]
            
    name = " ".join(name.split())
            
    return name.title()

# ====================== SMART WEIGHT CONVERSION ======================
UNIT_CONVERSIONS = {"Small": 75, "Medium": 120, "Large": 180, "Piece": 100, "Pieces": 100, "Cup": 240, "Pounds": 453.6, "Ounces": 28.35}
UNIT_LIST = ["Grams", "Piece", "Pieces", "Small", "Medium", "Large", "Cup", "Pounds", "Ounces"]

def convert_to_grams(unit_type, quantity):
    if unit_type == "Grams": return quantity
    avg_weight = UNIT_CONVERSIONS.get(unit_type, 100)
    return avg_weight * quantity

def parse_recipe_grams(estimated_amount, unit):
    unit = unit.lower()
    if unit in ["g", "gram", "grams"]: return estimated_amount
    elif unit in ["kg", "kilogram", "kilograms"]: return estimated_amount * 1000
    elif unit in ["lb", "lbs", "pound", "pounds"]: return estimated_amount * 453.592
    elif unit in ["oz", "ounce", "ounces"]: return estimated_amount * 28.3495
    elif unit in ["cup", "cups"]: return estimated_amount * 240
    elif unit in ["tbsp", "tablespoon", "tablespoons"]: return estimated_amount * 15
    elif unit in ["tsp", "teaspoon", "teaspoons"]: return estimated_amount * 5
    elif unit in ["ml", "milliliter", "milliliters"]: return estimated_amount
    elif unit in ["l", "liter", "liters"]: return estimated_amount * 1000
    else: return estimated_amount * 50

def convert_grams_to_target_unit(grams_amount, target_system="Metric"):
    if target_system == "Imperial":
        oz = grams_amount / 28.3495
        if oz >= 16:
            lbs = oz / 16.0
            return f"{lbs:.2f}".rstrip('0').rstrip('.') + " lbs"
        return f"{oz:.2f}".rstrip('0').rstrip('.') + " oz"
    else:
        if grams_amount >= 1000:
            kg = grams_amount / 1000.0
            return f"{kg:.2f}".rstrip('0').rstrip('.') + " kg"
        return f"{grams_amount:.0f} g"

# ====================== ROBUST DATABASE MIGRATION ======================
def init_database():
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, email TEXT NOT NULL, 
        age INTEGER, weight REAL, height REAL, gender TEXT, activity_level REAL, 
        diet_preference TEXT, allergies TEXT, calculated_tdee REAL, 
        measurement_sys TEXT DEFAULT 'Metric',
        protein_goal REAL DEFAULT 200, carb_goal REAL DEFAULT 100, fat_goal REAL DEFAULT 80,
        total_xp INTEGER DEFAULT 0,
        created_at TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS pantry (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, ingredient_name TEXT NOT NULL, quantity_grams REAL NOT NULL, raw_unit TEXT DEFAULT 'Grams', raw_quantity REAL DEFAULT 0, expiration_date TEXT, added_date TEXT, nutrition_data TEXT, FOREIGN KEY (username) REFERENCES users(username))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS meal_plan (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, date TEXT NOT NULL, meal_type TEXT NOT NULL, recipe_name TEXT NOT NULL, recipe_id TEXT, FOREIGN KEY (username) REFERENCES users(username))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS nutrition_log (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, date TEXT NOT NULL, meal_name TEXT NOT NULL, calories REAL, protein REAL, carbs REAL, fat REAL, FOREIGN KEY (username) REFERENCES users(username))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS recipe_history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, recipe_name TEXT NOT NULL, completed_date TEXT NOT NULL, FOREIGN KEY (username) REFERENCES users(username))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS recipe_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        recipe_id TEXT NOT NULL,
        recipe_title TEXT NOT NULL,
        added_date TEXT,
        FOREIGN KEY (username) REFERENCES users(username)
    )''')

    def add_column_if_not_exists(table, column, definition):
        cursor.execute(f"PRAGMA table_info({table})")
        existing = [row[1] for row in cursor.fetchall()]
        if column not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    add_column_if_not_exists("pantry", "raw_unit", "TEXT DEFAULT 'Grams'")
    add_column_if_not_exists("pantry", "raw_quantity", "REAL DEFAULT 0")
    add_column_if_not_exists("users", "measurement_sys", "TEXT DEFAULT 'Metric'")
    add_column_if_not_exists("users", "protein_goal", "REAL DEFAULT 200")
    add_column_if_not_exists("users", "carb_goal", "REAL DEFAULT 100")
    add_column_if_not_exists("users", "fat_goal", "REAL DEFAULT 80")
    add_column_if_not_exists("users", "total_xp", "INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

init_database()

# ====================== FAVORITES HELPERS ======================
def toggle_favorite(username, recipe_id, recipe_title):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM recipe_favorites WHERE username=? AND recipe_id=?", (username, str(recipe_id)))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("DELETE FROM recipe_favorites WHERE username=? AND recipe_id=?", (username, str(recipe_id)))
        conn.commit()
        conn.close()
        return False
    else:
        cursor.execute("INSERT INTO recipe_favorites (username, recipe_id, recipe_title, added_date) VALUES (?, ?, ?, ?)",
                       (username, str(recipe_id), recipe_title, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True

def is_favorite(username, recipe_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM recipe_favorites WHERE username=? AND recipe_id=?", (username, str(recipe_id)))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# ====================== XP + GEMINI ROTATION ======================
def add_xp(username, amount):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_xp = total_xp + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()
    if 'user_xp' in st.session_state:
        st.session_state.user_xp += amount
    st.rerun()

def generate_gemini_with_rotation(contents):
    raw_keys = os.getenv('GEMINI_API_KEYS', '') or os.getenv("GOOGLE_API_KEY", '')
    keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
    if not keys:
        return "ERROR: No Gemini API keys found."

    total_keys = len(keys)
    attempts = 0
    while attempts < total_keys:
        current_idx = st.session_state.gemini_key_index
        current_key = keys[current_idx]
        genai.configure(api_key=current_key)
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(contents)
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                st.session_state.gemini_key_index = (current_idx + 1) % total_keys
                attempts += 1
                continue 
            else:
                return f"ERROR: {str(e)}"
    return "RATE_LIMIT_WARNING: All Gemini keys are exhausted for today."

# ====================== DATABASE HELPER FUNCTIONS ======================
def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, email):
    try:
        conn = sqlite3.connect('kitchen.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)', (username, hash_password(password), email, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Username already exists!"
    except Exception as e: return False, f"Error: {str(e)}"

def verify_user(username, password):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return True if result and result[0] == hash_password(password) else False

def get_user_profile(username):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_user_profile(username, age, weight, height, gender, activity_level, diet_pref, allergies, tdee, measure_sys, protein_goal, carb_goal, fat_goal):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET age=?, weight=?, height=?, gender=?, activity_level=?, diet_preference=?, allergies=?, calculated_tdee=?, measurement_sys=?, protein_goal=?, carb_goal=?, fat_goal=? WHERE username=?', 
                   (age, weight, height, gender, activity_level, diet_pref, allergies, tdee, measure_sys, protein_goal, carb_goal, fat_goal, username))
    conn.commit()
    conn.close()

def add_ingredient(username, name, quantity_grams, raw_unit, raw_quantity, exp_date, nutrition):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pantry (username, ingredient_name, quantity_grams, raw_unit, raw_quantity, expiration_date, added_date, nutrition_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (username, name, quantity_grams, raw_unit, raw_quantity, exp_date, datetime.now().isoformat(), json.dumps(nutrition)))
    conn.commit()
    conn.close()

def add_or_update_ingredient(username, name, quantity_grams, raw_unit, raw_quantity, exp_date, nutrition):
    """Smart stacking: if item exists, increase quantity AND recalculate fresh nutrition"""
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    name_lower = name.lower().strip()
    
    cursor.execute("""
        SELECT id, quantity_grams FROM pantry 
        WHERE username = ? 
        AND (LOWER(ingredient_name) = ? 
             OR LOWER(ingredient_name) LIKE ? 
             OR ? LIKE '%' || LOWER(ingredient_name) || '%')
        LIMIT 1
    """, (username, name_lower, f"%{name_lower}%", name_lower))
    
    existing = cursor.fetchone()
    
    if existing:
        item_id, current_g = existing
        new_total_grams = current_g + quantity_grams
        real_nutrition = get_ingredient_nutrition(name, new_total_grams)
        cursor.execute("""
            UPDATE pantry 
            SET quantity_grams = ?, raw_quantity = ?, expiration_date = ?, nutrition_data = ? 
            WHERE id = ?
        """, (new_total_grams, raw_quantity, exp_date, json.dumps(real_nutrition), item_id))
    else:
        cursor.execute('''
            INSERT INTO pantry 
            (username, ingredient_name, quantity_grams, raw_unit, raw_quantity, expiration_date, added_date, nutrition_data) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, name, quantity_grams, raw_unit, raw_quantity, exp_date, datetime.now().isoformat(), json.dumps(nutrition)))
    
    conn.commit()
    conn.close()

def get_ingredients(username):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM pantry WHERE username = ?', (username,))
    results = cursor.fetchall()
    conn.close()
    ingredients = []
    for row in results:
        r_unit = row[4] if len(row) > 4 and row[4] else "Grams"
        r_qty = row[5] if len(row) > 5 and row[5] else row[3]
        ingredients.append({'id': row[0], 'name': row[2], 'quantity_grams': row[3], 'raw_unit': r_unit, 'raw_quantity': r_qty, 'expiration_date': row[6] if len(row)>6 else row[4], 'nutrition': json.loads(row[8]) if len(row)>8 and row[8] else None})
    return ingredients

def get_missing_ingredients(recipe, pantry_items):
    """Returns list of missing ingredients with required amount"""
    if not recipe.get('extendedIngredients'):
        return []
    
    pantry_dict = {item['name'].lower(): item['quantity_grams'] for item in pantry_items}
    missing = []
    
    for ing in recipe['extendedIngredients']:
        req_name = ing.get('name', '').strip().lower()
        req_amount = parse_recipe_grams(ing.get('amount', 0), ing.get('unit', '')) * st.session_state.get('batch_multiplier', 1.0)
        
        if req_amount <= 0:
            continue
            
        normalized = normalize_ingredient_name(req_name)
        found = False
        for p_name in pantry_dict:
            if normalized.lower() in p_name.lower() or p_name.lower() in normalized.lower():
                found = True
                break
        if not found:
            missing.append({
                'name': normalized.title(),
                'amount': req_amount,
                'unit': ing.get('unit', 'g')
            })
    
    return missing

def delete_ingredient(ingredient_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pantry WHERE id = ?', (ingredient_id,))
    conn.commit()
    conn.close()

def subtract_ingredient_stock(username, ingredient_name, amount_used_grams):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    name_lower = ingredient_name.lower().strip()
    
    cursor.execute("""
        SELECT id, quantity_grams, raw_unit, raw_quantity, ingredient_name 
        FROM pantry 
        WHERE username=? 
        AND (ingredient_name = ? OR ingredient_name LIKE ? OR ? LIKE '%' || ingredient_name || '%')
        ORDER BY quantity_grams DESC
    """, (username, ingredient_name, f"%{name_lower}%", name_lower))
    
    result = cursor.fetchone()
    if result:
        ingredient_id, current_stock_g, r_unit, r_qty, pantry_name = result
        new_stock_g = max(current_stock_g - amount_used_grams, 0)
        if current_stock_g > 0:
            ratio = new_stock_g / current_stock_g
            new_r_qty = r_qty * ratio
        else:
            new_r_qty = 0
        if new_stock_g <= 0:
            cursor.execute("DELETE FROM pantry WHERE id=?", (ingredient_id,))
        else:
            cursor.execute("UPDATE pantry SET quantity_grams=?, raw_quantity=? WHERE id=?", (new_stock_g, new_r_qty, ingredient_id))
        conn.commit()
    conn.close()

# ====================== AI-POWERED PANTRY SUBTRACTION ======================
def smart_subtract_recipe_ingredients(username, recipe, scale_factor=1.0):
    """Uses Gemini AI with automatic key rotation to match recipe ingredients to pantry"""
    if not recipe.get('extendedIngredients'):
        return
    
    pantry_items = get_ingredients(username)
    if not pantry_items:
        return
    
    for ing in recipe['extendedIngredients']:
        recipe_name = ing.get('name', '').strip()
        amount_g = parse_recipe_grams(ing.get('amount', 0), ing.get('unit', '')) * scale_factor
        if amount_g <= 0:
            continue
        
        pantry_list = "\n".join([f"- {item['name']} ({item['quantity_grams']:.0f}g)" for item in pantry_items])
        
        prompt = f"""
        Match this recipe ingredient to ONE pantry item.
        Recipe ingredient: "{recipe_name}"
        Pantry items:
        {pantry_list}
        
        Return ONLY the exact pantry item name that best matches.
        Rules:
        - Ignore adjectives like "red", "minced", "ground", "frozen", "low fat", "sliced"
        - "ground beef", "minced beef", "beef" → "Minced Beef"
        - "onion", "red onion" → "Red Onion"
        - "potato", "potatoes" → "Potato"
        If no good match, return exactly "NO_MATCH".
        """
        
        response_text = generate_gemini_with_rotation(prompt)
        
        if response_text.startswith("ERROR") or response_text.startswith("RATE_LIMIT"):
            subtract_ingredient_stock(username, recipe_name, amount_g)
            continue
        
        best_match = response_text.strip()
        
        if best_match != "NO_MATCH":
            for item in pantry_items:
                if item['name'].lower() == best_match.lower() or best_match.lower() in item['name'].lower():
                    subtract_ingredient_stock(username, item['name'], amount_g)
                    st.info(f"✅ Subtracted {amount_g:.0f}g from {item['name']}")
                    break
            else:
                subtract_ingredient_stock(username, recipe_name, amount_g)
        else:
            subtract_ingredient_stock(username, recipe_name, amount_g)

def subtract_ingredient_stock_by_id(username, ingredient_id, amount_used_grams):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("SELECT quantity_grams, raw_unit, raw_quantity FROM pantry WHERE id=? AND username=?", (ingredient_id, username))
    result = cursor.fetchone()
    if result:
        current_stock_g, r_unit, r_qty = result
        new_stock_g = max(current_stock_g - amount_used_grams, 0)
        if current_stock_g > 0:
            ratio = new_stock_g / current_stock_g
            new_r_qty = r_qty * ratio
        else:
            new_r_qty = 0
        if new_stock_g <= 0:
            cursor.execute("DELETE FROM pantry WHERE id=?", (ingredient_id,))
        else:
            cursor.execute("UPDATE pantry SET quantity_grams=?, raw_quantity=? WHERE id=?", (new_stock_g, new_r_qty, ingredient_id))
    conn.commit()
    conn.close()

def add_meal_to_plan(username, date, meal_type, recipe_name, recipe_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO meal_plan (username, date, meal_type, recipe_name, recipe_id) VALUES (?, ?, ?, ?, ?)', (username, date, meal_type, recipe_name, recipe_id))
    conn.commit()
    conn.close()

def get_meal_plan(username, start_date=None, end_date=None):
    """Get meal plans — now uses exact date match for 'Today'"""
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    if start_date and end_date:
        cursor.execute('''
            SELECT * FROM meal_plan 
            WHERE username = ? AND date = ? 
            ORDER BY meal_type
        ''', (username, start_date))
    else:
        cursor.execute('SELECT * FROM meal_plan WHERE username = ? ORDER BY date DESC', (username,))
    results = cursor.fetchall()
    conn.close()
    
    meals = []
    for row in results:
        meals.append({
            'id': row[0], 
            'date': row[2], 
            'meal_type': row[3], 
            'recipe_name': row[4], 
            'recipe_id': row[5]
        })
    return meals

def delete_meal_from_plan(meal_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM meal_plan WHERE id = ?', (meal_id,))
    conn.commit()
    conn.close()

def remove_planned_meal_by_recipe(username, date, recipe_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM meal_plan WHERE username=? AND date=? AND recipe_id=? LIMIT 1", (username, date, str(recipe_id)))
    pm_match = cursor.fetchone()
    if pm_match:
        cursor.execute("DELETE FROM meal_plan WHERE id=?", (pm_match[0],))
    conn.commit()
    conn.close()

def add_nutrition_log(username, datetime_iso, meal_name, calories, protein, carbs, fat):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO nutrition_log (username, date, meal_name, calories, protein, carbs, fat) VALUES (?, ?, ?, ?, ?, ?, ?)', (username, datetime_iso, meal_name, calories, protein, carbs, fat))
    conn.commit()
    conn.close()

def get_nutrition_logs(username, date_prefix):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM nutrition_log WHERE username = ? AND date LIKE ?', (username, f"{date_prefix}%"))
    results = cursor.fetchall()
    conn.close()
    logs = []
    for row in results:
        logs.append({'id': row[0], 'date': row[2], 'meal': row[3], 'calories': row[4], 'protein': row[5], 'carbs': row[6], 'fat': row[7]})
    return logs

def delete_nutrition_log(log_id):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM nutrition_log WHERE id = ?', (log_id,))
    conn.commit()
    conn.close()

def add_recipe_completion(username, recipe_name):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO recipe_history (username, recipe_name, completed_date) VALUES (?, ?, ?)', (username, recipe_name, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def get_recipe_count(username):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM recipe_history WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_xp(username, amount, should_rerun=False):
    conn = sqlite3.connect('kitchen.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET total_xp = total_xp + ? WHERE username = ?", (amount, username))
    conn.commit()
    conn.close()
    
    if 'user_xp' in st.session_state:
        st.session_state.user_xp += amount
        
    if should_rerun:
        st.success(f"+{amount} XP!")
        st.rerun()

# ====================== AI, TIMER, API ======================
def query_ai_sous_chef(recipe_title, current_step_text, query):
    if not GEMINI_API_KEYS: return "RATE_LIMIT_WARNING: API key configuration missing."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        context_prompt = f"""
        You are an elite, Michelin-starred culinary assistant.
        The user is interacting with the recipe: "{recipe_title}".
        {"Current context or instructions they are working on: '" + current_step_text + "'" if current_step_text else ""}
        The user is asking the following question or needs a dietary alternative/ingredient modification: "{query}".
        Provide a concise, practical response focused strictly on kitchen substitution science or professional technique advice in a few clean bullet points.
        """
        response = model.generate_content(context_prompt)
        return response.text
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower(): return "RATE_LIMIT_WARNING"
        return f"❌ System Fault: {str(e)}"

def render_step_timer(total_seconds, step_id):
    html_code = f"""
    <div id="timer_container_{step_id}" style="background:#1a1c23; padding:15px; border-radius:10px; border:1px solid #2d3139; text-align:center; color:#ecf0f1; font-family:sans-serif; margin-bottom:15px;">
        <h4 style="margin:0 0 10px 0; color:#a1a8b5;">⏱️ Active Step Timer</h4>
        <div id="time_display_{step_id}" style="font-size:36px; font-weight:bold; color:#4caf50; margin-bottom:15px;"></div>
        <button id="start_btn_{step_id}" onclick="start_{step_id}()" style="background:#2196f3; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; margin-right:10px; font-weight:bold;">Start</button>
        <button id="pause_btn_{step_id}" onclick="pause_{step_id}()" style="background:#f44336; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; margin-right:10px; font-weight:bold;">Pause</button>
        <button onclick="reset_{step_id}()" style="background:#374151; color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:bold;">Reset</button>
    </div>
    <script>
        let timeLeft_{step_id} = {total_seconds};
        let timerInterval_{step_id} = null;
        function updateDisplay_{step_id}() {{
            let m = Math.floor(timeLeft_{step_id} / 60);
            let s = timeLeft_{step_id} % 60;
            document.getElementById("time_display_{step_id}").innerText = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
            if(timeLeft_{step_id} <= 0) {{
                document.getElementById("time_display_{step_id}").style.color = "#f44336";
                document.getElementById("time_display_{step_id}").innerText = "00:00 - DONE!";
            }}
        }}
        function start_{step_id}() {{
            if(!timerInterval_{step_id} && timeLeft_{step_id} > 0) {{
                timerInterval_{step_id} = setInterval(() => {{
                    timeLeft_{step_id}--;
                    updateDisplay_{step_id}();
                    if(timeLeft_{step_id} <= 0) {{
                        clearInterval(timerInterval_{step_id});
                        timerInterval_{step_id} = null;
                    }}
                }}, 1000);
            }}
        }}
        function pause_{step_id}() {{
            clearInterval(timerInterval_{step_id});
            timerInterval_{step_id} = null;
        }}
        function reset_{step_id}() {{
            pause_{step_id}();
            timeLeft_{step_id} = {total_seconds};
            document.getElementById("time_display_{step_id}").style.color = "#4caf50";
            updateDisplay_{step_id}();
        }}
        updateDisplay_{step_id}();
    </script>
    """
    components.html(html_code, height=180)

def make_spoonacular_request(url, params=None):
    if params is None: params = {}
    raw_keys = os.getenv('SPOONACULAR_KEYS', '')
    keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
    if not keys:
        st.error("❌ Key Error: No keys found inside your environment file variables.")
        return None
    total_keys = len(keys)
    attempts = 0
    while attempts < total_keys:
        current_idx = st.session_state.spoon_key_index
        params['apiKey'] = keys[current_idx]
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code in [402, 429]:
                st.session_state.spoon_key_index = (current_idx + 1) % total_keys
                attempts += 1
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            break
    st.error("❌ Fatal Outage: All available keys inside your vault array are exhausted for today.")
    return None

def search_ingredients_api(query):
    url = "https://api.spoonacular.com/food/ingredients/autocomplete"
    params = {'query': query, 'number': 10}
    data = make_spoonacular_request(url, params)
    return [item['name'].title() for item in data] if data else []

def calculate_local_pui(recipe, user_pantry_names):
    if 'nutrition' in recipe and 'ingredients' in recipe['nutrition']:
        req_ings = recipe['nutrition']['ingredients']
        if not req_ings: return 0
        match_count = 0
        for req in req_ings:
            req_name = req['name'].lower()
            if any(p_item in req_name or req_name in p_item for p_item in user_pantry_names):
                match_count += 1
        return (match_count / len(req_ings)) * 100
    return 0

def search_recipes_by_ingredients(ingredients_list, user_pantry_names, number=12, diet=None, intolerances=None):
    url = "https://api.spoonacular.com/recipes/findByIngredients"
    params = {
        'ingredients': ','.join(ingredients_list),
        'number': number,
        'ranking': 2,          
        'ignorePantry': False,
        'fillIngredients': True
    }
    data = make_spoonacular_request(url, params)
    recipes = data if data else []  

    enriched = []
    for r in recipes[:number]:
        details = get_recipe_details(r['id'])
        if details:
            details['pui_score'] = calculate_local_pui(details, user_pantry_names)
            details['pui_score'] = max(details.get('pui_score', 0), 
                                       (r.get('usedIngredientCount', 0) / max(r.get('usedIngredientCount', 1) + r.get('missedIngredientCount', 0), 1)) * 100)
            enriched.append(details)
    
    enriched.sort(key=lambda x: x.get('pui_score', 0), reverse=True)
    return enriched

def search_recipes_by_name(query, user_pantry_names, number=12):
    url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {'query': query, 'number': number, 'addRecipeNutrition': True}
    data = make_spoonacular_request(url, params)
    recipes = data.get('results', []) if data else []
    for recipe in recipes:
        recipe['pui_score'] = calculate_local_pui(recipe, user_pantry_names)
    return recipes

def get_recipe_details(recipe_id):
    url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
    params = {'includeNutrition': True}
    return make_spoonacular_request(url, params)

# ====================== HELPERS ======================
def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def calculate_tdee(weight, height, age, gender, activity_level):
    if gender.lower() == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    return bmr * activity_level

def get_ingredient_nutrition(name, amount_grams=100):
    """Real Spoonacular nutrition - based on your old working version"""
    if not name or amount_grams <= 0:
        return {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}

    cache_key = f"nutr_{name.lower().strip()}_{int(amount_grams)}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    url = "https://api.spoonacular.com/food/ingredients/search"
    params = {'query': name.strip(), 'number': 1}
    results_data = make_spoonacular_request(url, params)

    results = results_data.get('results', []) if results_data and isinstance(results_data, dict) else []

    if not results:
        st.warning(f"⚠️ No results found for '{name}'")
        result = {"calories": 120, "protein": 5, "carbs": 10, "fat": 5}
        st.session_state[cache_key] = result
        return result

    ingredient_id = results[0].get('id')
    if not ingredient_id:
        st.warning(f"⚠️ No ID found for '{name}'")
        result = {"calories": 120, "protein": 5, "carbs": 10, "fat": 5}
        st.session_state[cache_key] = result
        return result

    nutrition_url = f"https://api.spoonacular.com/food/ingredients/{ingredient_id}/information"
    nutrition_params = {'amount': amount_grams, 'unit': 'grams'}
    nutrition_data = make_spoonacular_request(nutrition_url, nutrition_params)

    if nutrition_data and 'nutrition' in nutrition_data:
        nutrients = nutrition_data.get('nutrition', {}).get('nutrients', [])
        result = {
            'calories': next((n['amount'] for n in nutrients if n['name'] == 'Calories'), 0),
            'protein': next((n['amount'] for n in nutrients if n['name'] == 'Protein'), 0),
            'carbs': next((n['amount'] for n in nutrients if n['name'] == 'Carbohydrates'), 0),
            'fat': next((n['amount'] for n in nutrients if n['name'] == 'Fat'), 0)
        }
    else:
        st.warning(f"⚠️ Could not fetch nutrition for '{name}'")
        result = {"calories": 120, "protein": 5, "carbs": 10, "fat": 5}

    st.session_state[cache_key] = result
    return result

# ====================== SESSION STATE ======================
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_user' not in st.session_state: st.session_state.current_user = None
if 'active_page' not in st.session_state: st.session_state.active_page = "🏠 Home"
if 'current_recipe' not in st.session_state: st.session_state.current_recipe = None
if 'cooking_step' not in st.session_state: st.session_state.cooking_step = 0
if 'viewing_recipe' not in st.session_state: st.session_state.viewing_recipe = None
if 'viewing_profile' not in st.session_state: st.session_state.viewing_profile = False
if 'search_results' not in st.session_state: st.session_state.search_results = None
if 'spoon_key_index' not in st.session_state: st.session_state.spoon_key_index = 0
if 'mfp_last_item' not in st.session_state: st.session_state.mfp_last_item = None
if 'mfp_base_nutr' not in st.session_state: st.session_state.mfp_base_nutr = None
if 'scanned_items' not in st.session_state: st.session_state.scanned_items = None
if 'scanned_receipt_items' not in st.session_state: st.session_state.scanned_receipt_items = None
if 'dish_suggestions' not in st.session_state: st.session_state.dish_suggestions = None
if 'user_xp' not in st.session_state: st.session_state.user_xp = 584

if not st.session_state.authenticated:
    st.title("🍳 Smart Recipe Tracker")
    st.markdown("### Welcome! Please login or sign up")
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Sign Up"])
    with tab1:
        st.subheader("Login")
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", type="primary"):
            if login_user and login_pass and verify_user(login_user, login_pass):
                st.session_state.authenticated = True
                st.session_state.current_user = login_user
                st.rerun()
            else: st.error("Invalid credentials!")
    with tab2:
        st.subheader("Create Account")
        signup_user = st.text_input("Username", key="signup_user")
        signup_email = st.text_input("Email", key="signup_email")
        signup_pass = st.text_input("Password", type="password", key="signup_pass")
        signup_confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
        if st.button("Sign Up", type="primary"):
            if signup_pass != signup_confirm: st.error("Passwords don't match!")
            else:
                success, msg = create_user(signup_user, signup_pass, signup_email)
                if success: st.success(msg)
                else: st.error(msg)
else:
    username = st.session_state.current_user
    ingredients = get_ingredients(username)
    user_pantry_names = [i['name'].lower() for i in ingredients]
    profile = get_user_profile(username)
    user_system = profile[11] if profile and len(profile) > 11 and profile[11] else "Metric"
    st.session_state.user_xp = profile[15] if profile and len(profile) > 15 and profile[15] is not None else 0

    # ====================== TOP BAR ======================
    current_xp = st.session_state.user_xp
    current_level = (current_xp // 1000) + 1
    c1, c2, c3, c4, c5 = st.columns([2.8, 1.3, 4.2, 1, 0.8])
    with c1: st.markdown(f"<span style='font-size:28px; font-weight:600;'>Hello, {username}</span>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div style='text-align:center; margin-top:8px;'><small style='color:#a1a8b5; font-weight:bold;'>LEVEL</small><br><span style='font-size:48px; font-weight:bold; color:#4caf50; line-height:1;'>{current_level}</span></div>", unsafe_allow_html=True)
    with c3:
        progress = (current_xp % 1000) / 1000
        st.markdown(f"<div style='margin-top:28px;'><div style='height:12px; background:#2d3139; border-radius:9999px; overflow:hidden;'><div style='width:{progress*100}%; height:100%; background:linear-gradient(90deg, #4caf50, #ff7f0e);'></div></div><small style='color:#a1a8b5; display:block; text-align:center; margin-top:4px;'>{current_xp} XP</small></div>", unsafe_allow_html=True)
    with c4: st.markdown("<div style='width:52px; height:52px; background:#4caf50; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:28px; border:3px solid #2d3139; margin-top:14px;'>👨‍🍳</div>", unsafe_allow_html=True)
    with c5:
        if st.button("⚙️", use_container_width=True):
            st.session_state.viewing_profile = True
            st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

# ====================== PROFILE EDITING (Username + Password + Logout + Close) ======================
    if st.session_state.get('viewing_profile', False):
        st.markdown("<h2 class='section-header'>👤 Edit Profile</h2>", unsafe_allow_html=True)
        
        with st.form("profile_form"):
            new_username = st.text_input("Username", value=username)
            st.text_input("Email", value=profile[2] if profile and len(profile) > 2 else "", disabled=True)
            
            st.markdown("---")
            st.subheader("🔐 Change Password")
            current_password = st.text_input("Current Password", type="password", key="curr_pass")
            new_password = st.text_input("New Password", type="password", key="new_pass")
            confirm_password = st.text_input("Confirm New Password", type="password", key="conf_pass")
            
            st.markdown("---")
            
            age = st.number_input("Age", min_value=10, max_value=100, value=int(profile[3]) if profile and profile[3] else 25)
            weight = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, value=float(profile[4]) if profile and profile[4] else 70.0)
            height = st.number_input("Height (cm)", min_value=100, max_value=250, value=int(profile[5]) if profile and profile[5] else 170)
            gender = st.selectbox("Gender", ["Male", "Female"], index=0 if not profile or not profile[6] or profile[6]=="Male" else 1)
            activity = st.selectbox("Activity Level", ["Sedentary (1.2)", "Lightly Active (1.375)", "Moderately Active (1.55)", "Very Active (1.725)", "Extra Active (1.9)"])
            activity_level = float(activity.split("(")[1].split(")")[0])
            measure_sys = st.selectbox("Preferred Measurement System", ["Metric", "Imperial"], index=0 if user_system == "Metric" else 1)
            diet_pref = st.selectbox("Diet Profile", ["None", "Vegetarian", "Vegan", "Ketogenic", "Paleo"], index=["None", "Vegetarian", "Vegan", "Ketogenic", "Paleo"].index(profile[8]) if profile and profile[8] else 0)
            allergies = st.text_input("Allergies", value=profile[9] if profile and profile[9] else "")
            
            if st.form_submit_button("💾 Save All Changes", type="primary"):
                success = True
                message = ""
                
                if new_username != username:
                    conn = sqlite3.connect('kitchen.db')
                    cursor = conn.cursor()
                    cursor.execute("SELECT username FROM users WHERE username = ? AND username != ?", (new_username, username))
                    if cursor.fetchone():
                        success = False
                        message = "❌ Username already taken!"
                    conn.close()
                
                if new_password or confirm_password:
                    if not current_password:
                        success = False
                        message = "❌ Please enter your current password"
                    elif not verify_user(username, current_password):
                        success = False
                        message = "❌ Current password is incorrect"
                    elif new_password != confirm_password:
                        success = False
                        message = "❌ New passwords do not match"
                    elif len(new_password) < 4:
                        success = False
                        message = "❌ New password too short"
                
                if success:
                    if new_username != username:
                        conn = sqlite3.connect('kitchen.db')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
                        tables = ["pantry", "meal_plan", "nutrition_log", "recipe_history", "recipe_favorites"]
                        for table in tables:
                            cursor.execute(f"UPDATE {table} SET username = ? WHERE username = ?", (new_username, username))
                        conn.commit()
                        conn.close()
                        st.session_state.current_user = new_username
                        username = new_username
                    
                    if new_password:
                        conn = sqlite3.connect('kitchen.db')
                        cursor = conn.cursor()
                        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                                     (hash_password(new_password), username))
                        conn.commit()
                        conn.close()
                    
                    tdee = calculate_tdee(weight, height, age, gender, activity_level)
                    update_user_profile(username, age, weight, height, gender, activity_level, 
                                      diet_pref, allergies, tdee, measure_sys, 
                                      profile[12] if len(profile)>12 else 200,
                                      profile[13] if len(profile)>13 else 100,
                                      profile[14] if len(profile)>14 else 80)
                    
                    st.success("✅ Profile updated successfully!")
                    st.session_state.viewing_profile = False
                    st.rerun()
                else:
                    st.error(message)
        
        st.markdown("---")
        
        col_close, col_logout = st.columns(2)
        with col_close:
            if st.button("❌ Close", use_container_width=True):
                st.session_state.viewing_profile = False
                st.rerun()
        with col_logout:
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                logout()

    # ====================== NAVIGATION ======================
    m_nav1, m_nav2, m_nav3, m_nav4, m_nav5 = st.columns(5)
    if m_nav1.button("🏠 Home Dashboard", use_container_width=True, type="primary" if st.session_state.active_page == "🏠 Home" else "secondary"): st.session_state.active_page = "🏠 Home"; st.rerun()
    if m_nav2.button("🥕 Digital Pantry Stock", use_container_width=True, type="primary" if st.session_state.active_page == "🥕 My Pantry" else "secondary"): st.session_state.active_page = "🥕 My Pantry"; st.rerun()
    if m_nav3.button("🔍 Smart Recipe Finder", use_container_width=True, type="primary" if st.session_state.active_page == "🔍 Find Recipes" else "secondary"): st.session_state.active_page = "🔍 Find Recipes"; st.rerun()
    if m_nav4.button("📊 Nutrition Log & Plan", use_container_width=True, type="primary" if st.session_state.active_page == "📊 Nutrition & Meals" else "secondary"): st.session_state.active_page = "📊 Nutrition & Meals"; st.rerun()
    if m_nav5.button("🌍 Sustainability Impact", use_container_width=True, type="primary" if st.session_state.active_page == "🌍 Sustainability" else "secondary"): st.session_state.active_page = "🌍 Sustainability"; st.rerun()
    st.markdown("---")

# ====================== COOK MODE + PRE-COOK MISSING INGREDIENTS CHECK ======================
    if st.session_state.current_recipe:
        recipe = st.session_state.current_recipe

        if ('last_cooked_recipe_id' not in st.session_state or 
            st.session_state.last_cooked_recipe_id != recipe.get('id')):
            st.session_state.confirm_cook = True
            ingredients = get_ingredients(username)
            st.session_state.missing_ings = get_missing_ingredients(recipe, ingredients)
            st.session_state.last_cooked_recipe_id = recipe.get('id')

        if st.session_state.get('confirm_cook', False) and st.session_state.missing_ings:
            st.warning("⚠️ You are missing some ingredients for this recipe!")

            st.subheader("Missing Ingredients:")
            for item in st.session_state.missing_ings:
                st.write(f"• **{item['name']}** — {item['amount']:.0f} {item['unit']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Yes — Add missing to pantry", type="primary", use_container_width=True):
                    for item in st.session_state.missing_ings:
                        normalized = normalize_ingredient_name(item['name'])
                        add_or_update_ingredient(username, normalized, item['amount'], "Grams", item['amount'],
                                               (datetime.now() + timedelta(days=7)).isoformat(),
                                               {"calories": 100, "protein": 5, "carbs": 10, "fat": 5})
                    st.success("✅ Missing ingredients added!")
                    st.session_state.confirm_cook = False
                    st.rerun()

            with col2:
                if st.button("➡️ No — Proceed anyway", use_container_width=True):
                    st.session_state.confirm_cook = False
                    st.rerun()

            with col3:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.current_recipe = None
                    st.session_state.confirm_cook = False
                    st.rerun()
            st.stop()

        # ====================== NORMAL COOK MODE ======================
        st.header("👨‍🍳 Cook Mode Active")
        
        if "batch_multiplier" not in st.session_state:
            st.session_state.batch_multiplier = 1.0
            if recipe.get('extendedIngredients'):
                min_scale = 10.0
                for ing in recipe['extendedIngredients']:
                    req_g = parse_recipe_grams(ing.get('amount', 1), ing.get('unit', ''))
                    req_name = ing.get('name', '').lower()
                    stock_g = sum(p['quantity_grams'] for p in ingredients if req_name in p['name'].lower() or p['name'].lower() in req_name)
                    if stock_g > 0 and req_g > 0:
                        possible_scale = stock_g / req_g
                        if possible_scale < min_scale: min_scale = possible_scale
                if min_scale < 1.0: st.session_state.batch_multiplier = max(0.1, round(min_scale, 1))
        
        scale_factor = st.session_state.batch_multiplier
        if scale_factor < 1.0:
            st.warning(f"⚠️ Low Stock Detected! We auto-scaled this recipe down to {scale_factor}x so your ingredients match.")
        st.session_state.batch_multiplier = st.slider("Batch Multiplier", min_value=0.1, max_value=10.0, value=scale_factor, step=0.1)
       
        instructions = recipe.get('analyzedInstructions', [])[0]['steps'] if recipe.get('analyzedInstructions') else []
        if not instructions:
            st.error("No instructions.")
            if st.button("Exit"): 
                st.session_state.current_recipe = None
                st.session_state.cooking_step = 0
                st.rerun()
        else:
            total = len(instructions)
            current = st.session_state.cooking_step
            
            if current >= total:
                st.success("🎉 Recipe Finished!")
                meal_type_log = st.selectbox("Log meal as:", ["Breakfast", "Lunch", "Dinner", "Snack"])
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Consume Stock & Log Nutrition", type="primary", use_container_width=True):
                        with st.spinner("🧾 Updating pantry, logging nutrition, and counting recipe..."):
                            try:
                                remove_planned_meal_by_recipe(username, datetime.now().date().isoformat(), recipe['id'])
                                
                                if 'nutrition' in recipe:
                                    nutr = recipe['nutrition']['nutrients']
                                    scale_factor = st.session_state.get('batch_multiplier', 1.0)
                                    add_nutrition_log(username, datetime.now().isoformat(), recipe['title'],
                                                    next((n['amount'] for n in nutr if n['name'] == 'Calories'), 0)*scale_factor,
                                                    next((n['amount'] for n in nutr if n['name'] == 'Protein'), 0)*scale_factor,
                                                    next((n['amount'] for n in nutr if n['name'] == 'Carbohydrates'), 0)*scale_factor,
                                                    next((n['amount'] for n in nutr if n['name'] == 'Fat'), 0)*scale_factor)
                                
                                smart_subtract_recipe_ingredients(username, recipe, scale_factor)
                                add_recipe_completion(username, recipe['title'])
                                add_xp(username, 150, should_rerun=False)
                                st.success("✅ Everything updated!")
                            except Exception as e:
                                st.error(f"Partial error: {e}")
                            finally:
                                st.session_state.cooking_step = 0
                                st.session_state.current_recipe = None
                                if 'batch_multiplier' in st.session_state:
                                    st.session_state.batch_multiplier = 1.0
                                st.rerun()
                with c2:
                    if st.button("🏠 Exit without logging", use_container_width=True):
                        st.session_state.cooking_step = 0
                        st.session_state.current_recipe = None
                        st.rerun()
            else:
                st.progress((current + 1) / total)
                step = instructions[current]
                st.markdown(f"## Step {step['number']}: {step['step']}")
                
                time_match = re.search(r'(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)', step['step'], re.IGNORECASE)
                if time_match:
                    val = int(time_match.group(1))
                    render_step_timer(val*3600 if 'hour' in time_match.group(2).lower() or 'hr' in time_match.group(2).lower() else val*60, step['number'])
                
                if step.get('ingredients'):
                    st.markdown("### 🥕 Required here:")
                    for ing in step['ingredients']:
                        match = next((x for x in recipe.get('extendedIngredients', []) if x['id'] == ing['id']), None)
                        if match:
                            st.write(f"• {get_food_emoji(match['name'])} **{convert_grams_to_target_unit(parse_recipe_grams(match.get('amount', 1), match.get('unit', ''))*scale_factor, user_system)} {match['name'].title()}**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if current > 0 and st.button("⬅ Previous", use_container_width=True):
                        st.session_state.cooking_step -= 1
                        st.rerun()
                with col2:
                    if st.button("🏠 Exit Cooking", use_container_width=True):
                        st.session_state.cooking_step = 0
                        st.session_state.current_recipe = None
                        st.rerun()
                with col3:
                    if st.button("Next ➡️" if current < total-1 else "✅ Finish!", type="primary", use_container_width=True):
                        st.session_state.cooking_step += 1
                        st.rerun()

    # ====================== HOME DASHBOARD ======================
    else:
        if st.session_state.active_page == "🏠 Home":
            st.markdown(f"<h1 style='text-align:center; color:#FFEA00; margin-bottom:0;'>🍳 <strong>{username}</strong> Kitchen Hub</h1>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center; color:#a1a8b5; font-size:1.1rem;'>Welcome back, <strong>{username}</strong> • Real-time Smart Dashboard</p>", unsafe_allow_html=True)



            col1, col2, col3, col4 = st.columns(4)
            with col1:
                expiring_soon = len([i for i in ingredients if i.get('expiration_date') and datetime.fromisoformat(i['expiration_date']).date() <= datetime.now().date() + timedelta(days=3)])
                st.metric("📦 Pantry Items", len(ingredients), delta=f"{expiring_soon} expiring soon" if expiring_soon > 0 else None, delta_color="orange")
            with col2:
                today_str = datetime.now().date().isoformat()
                today_plans = get_meal_plan(username, today_str, today_str)
                st.metric("🍽️ Today's Meals", len(today_plans))
            with col3:
                r_count = get_recipe_count(username)
                st.metric("🏆 Recipes Cooked", r_count)
            with col4:
                today_prefix = datetime.now().date().isoformat()
                logs = get_nutrition_logs(username, today_prefix)
                total_cal = sum(l['calories'] for l in logs)
                tdee_val = profile[10] if profile and len(profile) > 10 and profile[10] else 2200
                st.metric("🔥 Calories Today", f"{int(total_cal)}", delta=f"{int(total_cal - tdee_val)}" if total_cal else None)

            st.markdown("---")

            left, right = st.columns([2.2, 1])

            with left:
                st.markdown("### 📅 Today's Meal Plan")
                if today_plans:
                    for pm in today_plans:
                        c1, c2, c3 = st.columns([1, 5, 2])
                        with c1: st.markdown(f"**{pm['meal_type']}**")
                        with c2: st.markdown(f"🍲 **{pm['recipe_name']}**")
                        with c3:
                            if st.button("👨‍🍳 Cook Now", key=f"cook_home_{pm['id']}", type="primary", use_container_width=True):
                                st.session_state.current_recipe = get_recipe_details(pm['recipe_id'])
                                st.session_state.cooking_step = 0
                                st.rerun()
                        st.markdown("---")
                else:
                    st.info("No meals planned for today. Find recipes below 👇")

                # ====================== NEW: ❤️ MY FAVORITES ======================
                st.markdown("### ❤️ My Favorites")
                conn = sqlite3.connect('kitchen.db')
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT recipe_id, recipe_title 
                    FROM recipe_favorites 
                    WHERE username = ? 
                    ORDER BY added_date DESC LIMIT 6
                """, (username,))
                favorites = cursor.fetchall()
                conn.close()

                if favorites:
                    for fav_id, fav_title in favorites:
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.markdown(f"🍳 **{fav_title}**")
                        with col_b:
                            if st.button("👨‍🍳 Cook", key=f"fav_cook_{fav_id}"):
                                st.session_state.current_recipe = get_recipe_details(fav_id)
                                st.session_state.cooking_step = 0
                                st.rerun()
                        st.markdown("---")
                else:
                    st.info("You haven't favorited any recipes yet. ❤️ a recipe in the recipe viewer to see it here!")

                # ====================== RECOMMENDED FOR YOU ======================
                st.markdown("### 🔥 Recommended for You")
                if ingredients:
                    top_ingredients = [i['name'] for i in ingredients[:8]]
                    recommended = search_recipes_by_ingredients(top_ingredients, user_pantry_names, number=6)
                    for rec in recommended[:4]:
                        ca, cb = st.columns([4, 1])
                        with ca:
                            st.markdown(f"""
                            <div class="premium-card">
                                <h5>{get_food_emoji(rec['title'])} {rec['title']}</h5>
                                <small>Pantry Match: <strong>{rec.get('pui_score', 0):.0f}%</strong></small>
                            </div>
                            """, unsafe_allow_html=True)
                        with cb:
                            if st.button("View →", key=f"view_rec_{rec['id']}"):
                                st.session_state.viewing_recipe = get_recipe_details(rec['id'])
                                st.rerun()
                else:
                    st.caption("Add ingredients to your pantry to unlock smart recommendations!")

            with right:
                st.markdown("### 🥕 Pantry Snapshot")
                if ingredients:
                    for ing in sorted(ingredients, key=lambda x: x.get('expiration_date') or '9999-12-31')[:5]:
                        display_qty = convert_grams_to_target_unit(ing['quantity_grams'], user_system)
                        st.markdown(f"""
                        <div class="premium-card" style="padding:12px 15px;">
                            <strong>{get_food_emoji(ing['name'])} {ing['name']}</strong><br>
                            <small>{display_qty}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("Your pantry is empty! Add some ingredients.")

                st.markdown("<br>", unsafe_allow_html=True)

                st.markdown("### 📊 Today's Nutrition")
                if logs:
                    p_cal = min((total_cal / tdee_val) * 100, 100) if tdee_val else 0
                    st.markdown(f"""
                    <div style="background:#1a1c23; padding:15px; border-radius:12px; border:1px solid #2d3139;">
                        <strong>Calories</strong> {int(total_cal)} / {int(tdee_val)} kcal<br>
                        <div style="height:8px; background:#2d3139; border-radius:4px; margin:8px 0;">
                            <div style="width:{p_cal}%; height:100%; background:#ff7f0e; border-radius:4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.caption("No meals logged today yet.")

                st.markdown("### ⚡ Quick Actions")
                qa1, qa2 = st.columns(2)
                with qa1:
                    if st.button("➕ Add to Pantry", use_container_width=True):
                        st.session_state.active_page = "🥕 My Pantry"
                        st.rerun()
                with qa2:
                    if st.button("🔍 Find Recipes", use_container_width=True):
                        st.session_state.active_page = "🔍 Find Recipes"
                        st.rerun()

            st.caption("💡 Tip: Use the top navigation bar to access any section instantly.")

        # ====================== PANTRY PAGE ======================
        elif st.session_state.active_page == "🥕 My Pantry":
            st.markdown("<h1 style='color:#4caf50;'>🥕 Digital Pantry</h1>", unsafe_allow_html=True)
            tab_p1, tab_p2, tab_p3 = st.tabs(["🛒 Database Form Entry", "📸 Canvas Image Scanner", "🧾 Scan Receipt"])

            with tab_p1:
                search_query = st.text_input("🔍 Search ingredient registry node", placeholder="type item label...")
                if search_query and len(search_query) >= 2:
                    suggestions = search_ingredients_api(search_query)
                    if suggestions:
                        selected_food = st.selectbox("Confirm Entry ID", suggestions)
                        if selected_food:
                            if st.session_state.mfp_last_item != selected_food:
                                st.session_state.mfp_base_nutr = get_ingredient_nutrition(selected_food, 100)
                                st.session_state.mfp_last_item = selected_food
                            c_num, c_unit = st.columns(2)
                            qty_input = c_num.number_input("Serving Size Value", min_value=0.1, step=1.0, value=1.0)
                            unit_type = c_unit.selectbox("Measurement Metric Ingestion", UNIT_LIST, index=0)
                            calc_g = convert_to_grams(unit_type, qty_input)
                            mult = calc_g / 100.0
                            if st.session_state.mfp_base_nutr:
                                bn = st.session_state.mfp_base_nutr
                                st.markdown(f"**Live Scale Analytics Matrix ({calc_g:.0f}g):** {bn['calories']*mult:.0f} Cal | P: {bn['protein']*mult:.1f}g | C: {bn['carbs']*mult:.1f}g | F: {bn['fat']*mult:.1f}g")
                            exp_in = st.date_input("Expiration Target Calendar Matrix", min_value=datetime.now().date())
                            if st.button("📥 Commit Entry to Pantry Stock Database", type="primary"):
                                normalized_name = normalize_ingredient_name(selected_food)
                                real_nutrition = get_ingredient_nutrition(normalized_name, calc_g)
                                add_or_update_ingredient(username, normalized_name, calc_g, unit_type, qty_input, exp_in.isoformat(), real_nutrition)
                                add_xp(username, 20)
                                st.session_state.mfp_last_item = None
                                st.success(f"✅ {normalized_name} ({calc_g}g) saved!")
                                st.rerun()

            # ====================== TAB 2 - IMAGE SCANNER (fixed with gemini-1.5-flash) ======================
            with tab_p2:
                uploaded_file = st.file_uploader("Drop the ingredient image...", type=["jpg", "jpeg", "png"])
                if uploaded_file and st.button("✨ Execute AI Parsing Extraction Matrix", type="primary"):
                    try:
                        pil_img = Image.open(uploaded_file)
                        
                        prompt = """
                        You are an expert at reading photos of physical grocery items, shopping hauls, fridge contents, or product packaging.
                        Extract EVERY visible food item as a clean JSON array.

                        Rules:
                        - "name": clean, simple, standard English food name only. Remove all brands, "Organic", "Fresh", "Low Fat", "Frozen", etc.
                        - "quantity": the exact quantity WITH unit ONLY if clearly visible. If no quantity is shown, return "quantity": "" (empty string).

                        Return ONLY valid JSON array. Example:
                        [
                          {"name": "Minced Beef", "quantity": "500g"},
                          {"name": "Potato", "quantity": ""},
                          {"name": "Red Onion", "quantity": "440g"}
                        ]
                        """
                        
                        response_text = generate_gemini_with_rotation([prompt, pil_img])
                        
                        if response_text.startswith("ERROR") or response_text.startswith("RATE_LIMIT"):
                            st.error(f"Scan failed: {response_text}")
                        else:
                            clean_json = response_text.replace("```json", "").replace("```", "").strip()
                            st.session_state.scanned_items = json.loads(clean_json)
                            st.success("✅ Image parsed successfully!")
                    except Exception as e:
                        st.error(f"Scan fault pipeline drop: {e}")

                if st.session_state.scanned_items:
                    with st.form("batch_review_form"):
                        payloads = []
                        for idx, item in enumerate(st.session_state.scanned_items):
                            name = item.get('name', '').strip().title()
                            st.write(f"**Item {idx+1}: {name}**")
                            w1, w2, d1 = st.columns([1, 1, 2])
                            q_val = w1.number_input("Mass", min_value=0.0, value=1.0, key=f"v_q_{idx}")
                            u_val = w2.selectbox("Unit", UNIT_LIST, key=f"v_u_{idx}")
                            d_val = d1.date_input("Expiration", min_value=datetime.now().date(), key=f"v_d_{idx}")
                            payloads.append({"name": name, "qty": q_val, "unit": u_val, "date": d_val})
                        
                        if st.form_submit_button("Commit All Scanned Elements"):
                            for p in payloads:
                                normalized_name = normalize_ingredient_name(p['name'])
                                g = convert_to_grams(p['unit'], p['qty'])
                                nutrition = get_ingredient_nutrition(normalized_name, g)
                                add_or_update_ingredient(username, normalized_name, g, p['unit'], p['qty'], p['date'].isoformat(), nutrition)
                                add_xp(username, 20)
                            st.session_state.scanned_items = None
                            st.rerun()

            with tab_p3:
                st.markdown("### 🧾 Scan Receipt / Order Screenshot")
                st.caption("Upload screenshot from Food Panda, Grab, or any delivery order")
                
                receipt_file = st.file_uploader("Upload receipt image", type=["jpg", "jpeg", "png"], key="receipt_uploader")
                
                if receipt_file and st.button("✨ Extract Items with AI", type="primary", use_container_width=True):
                    try:
                        pil_img = Image.open(receipt_file)
                        prompt = """
                        You are an expert at reading food delivery receipts (Food Panda, Grab, etc.).
                        Extract EVERY food item as a clean JSON array.
                        Rules:
                        - "name": clean, simple, standard English food name only.
                        - "quantity": the exact quantity WITH unit as shown (example: "450g", "250g", "1kg", "2 pieces")

                        Return ONLY valid JSON array.
                        """
                        response_text = generate_gemini_with_rotation([prompt, pil_img])
                        
                        # Strong JSON cleaning
                        clean_json = response_text.strip()
                        if "```json" in clean_json:
                            clean_json = clean_json.split("```json")[1].split("```")[0]
                        elif "```" in clean_json:
                            clean_json = clean_json.split("```")[1].strip()
                        
                        import re
                        json_match = re.search(r'\[.*\]', clean_json, re.DOTALL)
                        if json_match:
                            clean_json = json_match.group(0)
                        
                        st.session_state.scanned_receipt_items = json.loads(clean_json)
                        st.success(f"✅ Receipt parsed successfully! Found **{len(st.session_state.scanned_receipt_items)} items**")
                    except Exception as e:
                        st.error(f"Failed to parse receipt: {e}")

                if st.session_state.get('scanned_receipt_items'):
                    st.markdown("### Review & Adjust Items (Duplicates Merged)")
                    
                    from collections import defaultdict
                    merged = defaultdict(float)
                    
                    # ==================== FIXED QUANTITY PARSER ====================
                    def parse_qty_to_grams(qty_str):
                        if not qty_str or qty_str == "1":
                            return 100.0
                        s = str(qty_str).lower().strip()
                        # Extract number
                        num_match = re.search(r'(\d+\.?\d*)', s)
                        num = float(num_match.group(1)) if num_match else 1.0
                        
                        if 'kg' in s:
                            return num * 1000
                        elif 'g' in s:
                            return num
                        elif any(x in s for x in ['lb', 'pound', 'lbs']):
                            return num * 453.6
                        elif any(x in s for x in ['piece', 'pcs', 'pc']):
                            return num * 100
                        else:
                            return num * 100  # safe fallback
                    
                    for item in st.session_state.scanned_receipt_items:
                        name = item.get('name', '').strip().title()
                        qty_str = item.get('quantity', '')
                        grams = parse_qty_to_grams(qty_str)
                        merged[name] += grams
                    
                    st.info(f"**{len(merged)} unique items** will be added to your pantry")

                    with st.form("receipt_review_form"):
                        payloads = []
                        for idx, (name, total_grams) in enumerate(merged.items()):
                            st.write(f"**Item {idx+1}: {name}** (Total: {total_grams:.0f}g)")
                            col1, col2, col3 = st.columns([2, 1, 2])
                            with col1:
                                qty_input = st.number_input("Total Quantity", min_value=0.1, value=total_grams, key=f"r_qty_{idx}")
                            with col2:
                                unit_type = st.selectbox("Unit", UNIT_LIST, index=0, key=f"r_unit_{idx}")
                            with col3:
                                exp_date = st.date_input("Expiration", min_value=datetime.now().date(), key=f"r_exp_{idx}")
                            
                            grams = convert_to_grams(unit_type, qty_input)
                            payloads.append({
                                "name": name,
                                "qty": qty_input,
                                "unit": unit_type,
                                "date": exp_date,
                                "grams": grams
                            })
                        
                        if st.form_submit_button("✅ Commit All Items to Pantry", type="primary"):
                            added_count = 0
                            for p in payloads:
                                try:
                                    normalized_name = normalize_ingredient_name(p['name'])
                                    try:
                                        nutrition = get_ingredient_nutrition(normalized_name, p['grams'])
                                    except:
                                        nutrition = {"calories": 100, "protein": 5, "carbs": 10, "fat": 5}
                                    
                                    add_or_update_ingredient(username, normalized_name, p['grams'], p['unit'], p['qty'], p['date'].isoformat(), nutrition)
                                    add_xp(username, 20)
                                    added_count += 1
                                except Exception as e:
                                    st.error(f"❌ Failed to add {p['name']}: {str(e)}")
                            
                            st.session_state.scanned_receipt_items = None
                            st.success(f"🎉 Successfully added **{added_count} items** to pantry!")
                            st.rerun()
                            
            st.markdown("<br><h4>Current Local Stock Matrix Logs</h4>", unsafe_allow_html=True)
            if ingredients:
                for ing in ingredients:
                    display_qty = convert_grams_to_target_unit(ing['quantity_grams'], user_system)
                    st.markdown(f"<div class='premium-card'><b>{get_food_emoji(ing['name'])} {ing['name']}</b> &nbsp;|&nbsp; Amount: {display_qty} &nbsp;|&nbsp; Energy: {ing['nutrition']['calories'] if ing['nutrition'] else 0:.0f} kcal</div>", unsafe_allow_html=True)
                    if st.button("🗑️ Purge", key=f"p_btn_{ing['id']}"): delete_ingredient(ing['id']); st.rerun()

# ====================== FIND RECIPES PAGE (NEW FEATURES) ======================
        elif st.session_state.active_page == "🔍 Find Recipes":
            if st.session_state.viewing_recipe:
                recipe = st.session_state.viewing_recipe
                st.subheader(recipe['title'])
                st.image(recipe.get('image', ''), use_column_width=True)

                col_fav, col_plan, col_cook, col_close = st.columns([1, 2, 2, 1])
                
                is_fav = is_favorite(username, recipe['id'])
                if col_fav.button("❤️" if is_fav else "♡", use_container_width=True):
                    toggle_favorite(username, recipe['id'], recipe['title'])
                    st.rerun()

                with col_plan.popover("📅 Add to Today's Plan", use_container_width=True):
                    meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"], key="plan_type_key")
                    
                    if st.button("✅ Confirm & Add", type="primary", use_container_width=True):
                        today_str = datetime.now().date().isoformat()
                        
                        add_meal_to_plan(username, today_str, meal_type, recipe['title'], recipe['id'])
                        st.success(f"✅ Added to today's {meal_type}!")
                        st.session_state.viewing_recipe = None
                        st.session_state.active_page = "🏠 Home"
                        st.rerun()

                if col_cook.button("👨‍🍳 Cook Now", type="primary", use_container_width=True):
                    st.session_state.current_recipe = recipe
                    st.session_state.cooking_step = 0
                    st.session_state.viewing_recipe = None
                    st.rerun()

                if col_close.button("❌ Close Preview"): 
                    st.session_state.viewing_recipe = None
                    st.rerun()

                st.markdown("### 📝 Ingredients")
                for ing in recipe.get('extendedIngredients', []):
                    st.write(f"• {convert_grams_to_target_unit(parse_recipe_grams(ing.get('amount',1), ing.get('unit','')), user_system)} {ing.get('name','')}")

            else:
                st.header("🔍 Smart Recipe Finder")
                t1, t2, t3 = st.tabs(["🥕 Match Pantry Stock", "🔍 Text Search", "📸 Scan Cooked Dish"])

                with t1:
                    if not ingredients: st.warning("Inventory clear.")
                    else:
                        selected_items = []
                        for ing in ingredients:
                            if st.checkbox(ing['name'], key=f"chk_f_{ing['id']}"): selected_items.append(ing['name'])
                        if st.button("🔍 Cross-Match Selection Constraints", type="primary") and selected_items:
                            st.session_state.search_results = search_recipes_by_ingredients(selected_items, user_pantry_names, 6, profile[8], profile[9])

                with t2:
                    text_q = st.text_input("Query label field input...", placeholder="e.g. Rice Bowl")
                    if st.button("Execute Complex Database Text Search", type="primary") and text_q:
                        st.session_state.search_results = search_recipes_by_name(text_q, user_pantry_names, 6)

                # ====================== NEW SCAN COOKED DISH TAB ======================
                with t3:
                    st.markdown("### 📸 Scan Your Finished Dish")
                    st.caption("Upload a photo of the cooked meal → AI will guess what it is with confidence %")
                    uploaded_dish = st.file_uploader("Photo of finished dish", type=["jpg", "jpeg", "png"], key="dish_scanner")

                    if uploaded_dish and st.button("🔍 Identify Dish", type="primary"):
                        with st.spinner("Analyzing with Gemini..."):
                            pil_img = Image.open(uploaded_dish)
                            prompt = """
                            Analyze this photo of a finished cooked dish.
                            Return ONLY a valid JSON array like this:
                            [
                              {"recipe_name": "Chicken Fried Rice", "confidence": 92, "reason": "rice, chicken, egg, vegetables"},
                              {"recipe_name": "Beef Stir Fry", "confidence": 67, "reason": "sliced beef and peppers"}
                            ]
                            """
                            response_text = generate_gemini_with_rotation([prompt, pil_img])
                            try:
                                clean = response_text.replace("```json", "").replace("```", "").strip()
                                st.session_state.dish_suggestions = json.loads(clean)
                            except:
                                st.error("Could not parse AI response. Try another photo.")
                                st.session_state.dish_suggestions = []

                    if st.session_state.get("dish_suggestions"):
                        st.markdown("### Possible Recipes (Possibility Meter)")
                        for s in st.session_state.dish_suggestions:
                            name = s.get("recipe_name", "Unknown")
                            conf = s.get("confidence", 50)
                            reason = s.get("reason", "")
                            st.markdown(f"**{name}**")
                            st.progress(conf / 100)
                            st.caption(f"{conf}% — {reason}")
                            if st.button(f"View → {name}", key=f"view_dish_{name}"):
                                st.session_state.search_results = search_recipes_by_name(name, user_pantry_names, number=3)
                                st.rerun()

                if st.session_state.search_results:
                    for recipe in st.session_state.search_results:
                        match_rate = recipe.get('match_rate', recipe.get('pui_score', 0)/100)
                        st.markdown(f"<div class='premium-card'><h4>{recipe['title']}</h4>Match Rate: <strong>{match_rate*100:.0f}%</strong></div>", unsafe_allow_html=True)
                        if st.button("View Comprehensive Details Context", key=f"det_view_{recipe['id']}"):
                            st.session_state.viewing_recipe = get_recipe_details(recipe['id'])
                            st.rerun()

        elif st.session_state.active_page == "📊 Nutrition & Meals":
            st.header("📊 Nutrition & Meals Dashboard")

            # ====================== TODAY'S SUMMARY (your beautiful chart) ======================
            today_prefix = datetime.now().date().isoformat()
            logs = get_nutrition_logs(username, today_prefix)
            total_cal = sum(l['calories'] for l in logs)
            total_prot = sum(l['protein'] for l in logs)
            total_carbs = sum(l['carbs'] for l in logs)
            total_fat = sum(l['fat'] for l in logs)
            tdee_val = profile[10] if profile and len(profile) > 10 and profile[10] else 2000

            protein_goal = profile[12] if profile and len(profile) > 12 else 200
            carb_goal = profile[13] if profile and len(profile) > 13 else 100
            fat_goal = profile[14] if profile and len(profile) > 14 else 80

            p_cal = min((total_cal / tdee_val)*100, 100) if tdee_val else 0
            p_prot = min((total_prot / protein_goal)*100, 100) if protein_goal else 0
            p_carbs = min((total_carbs / carb_goal)*100, 100) if carb_goal else 0
            p_fat = min((total_fat / fat_goal)*100, 100) if fat_goal else 0

            st.markdown(f"""
            <div style="display:flex; justify-content:space-around; align-items:center; background:#1a1c23; padding:30px; border-radius:15px; margin-bottom:20px; border:1px solid #2d3139;">
                <div style="text-align:center;">
                    <div style="width: 160px; height: 160px; border-radius: 50%; background: conic-gradient(#ff7f0e {p_cal}%, #2d3139 0); display: flex; align-items: center; justify-content: center; margin: 0 auto;">
                        <div style="width: 130px; height: 130px; border-radius: 50%; background: #1a1c23; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                            <h2 style="margin:0; color:#ff7f0e;">{total_cal:.0f}</h2><span style="font-size:11px; color:#a1a8b5;">/ {tdee_val:.0f} KCAL</span>
                        </div>
                    </div>
                </div>
                <div style="width:50%;">
                    <div>Protein: {total_prot:.0f}g / {protein_goal}g</div>
                    <div style="background:#2d3139; height:8px; border-radius:6px; margin-bottom:10px;"><div style="background:#4caf50; width:{p_prot}%; height:100%; border-radius:6px;"></div></div>
                    <div>Carbohydrates: {total_carbs:.0f}g / {carb_goal}g</div>
                    <div style="background:#2d3139; height:8px; border-radius:6px; margin-bottom:10px;"><div style="background:#2196f3; width:{p_carbs}%; height:100%; border-radius:6px;"></div></div>
                    <div>Lipid Fats: {total_fat:.0f}g / {fat_goal}g</div>
                    <div style="background:#2d3139; height:8px; border-radius:6px; margin-bottom:10px;"><div style="background:#f44336; width:{p_fat}%; height:100%; border-radius:6px;"></div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # ====================== TODAY'S DETAILED INTAKE ======================
            st.subheader("📅 Today's Intake")
            if logs:
                for log in logs:
                    st.markdown(f"**{log['meal']}** — {log['calories']:.0f} kcal | P: {log['protein']:.1f}g | C: {log['carbs']:.1f}g | F: {log['fat']:.1f}g")
            else:
                st.info("No meals logged today yet.")

            # ====================== LAST 7 DAYS HISTORY ======================
            st.subheader("📆 Last 7 Days History")
            for i in range(7):
                date_obj = datetime.now().date() - timedelta(days=i)
                date_str = date_obj.isoformat()
                day_logs = get_nutrition_logs(username, date_str)
                if day_logs:
                    day_cal = sum(l['calories'] for l in day_logs)
                    st.markdown(f"**{date_obj.strftime('%d %b %Y')}** — {day_cal:.0f} kcal ({len(day_logs)} meals)")
                    for log in day_logs:
                        st.caption(f"• {log['meal']} → {log['calories']:.0f} kcal")
                else:
                    st.caption(f"• {date_obj.strftime('%d %b %Y')} — No meals logged")

            # ====================== MACRO GOALS ======================
            st.markdown("### Adjust Your Daily Macro Goals")
            with st.form("macro_form"):
                new_protein = st.number_input("Protein Goal (g)", value=protein_goal)
                new_carb = st.number_input("Carb Goal (g)", value=carb_goal)
                new_fat = st.number_input("Fat Goal (g)", value=fat_goal)
                if st.form_submit_button("Save Macro Goals", type="primary"):
                    update_user_profile(username, profile[3], profile[4], profile[5], profile[6], profile[7], profile[8], profile[9], profile[10], profile[11], new_protein, new_carb, new_fat)
                    st.success("Macro goals updated!")
                    st.rerun()

        elif st.session_state.active_page == "🌍 Sustainability":
            st.header("🌍 Sustainability Impact Dashboard")
            st.markdown("### How your cooking habits are helping the planet & your wallet 💰")

            r_count = get_recipe_count(username)

            avg_meal_cost_out = 18.50  
            avg_meal_cost_home = 7.50  
            savings_per_meal = avg_meal_cost_out - avg_meal_cost_home

            total_savings = r_count * savings_per_meal

            co2_saved = r_count * 2.8     
            water_saved = r_count * 1200  
            plastic_reduced = r_count * 3 

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("🍳 Meals Cooked at Home", r_count, delta="Great job!")
            with col2:
                st.metric("💰 Money Saved", f"RM {total_savings:.2f}", 
                         delta=f"RM {savings_per_meal:.2f} per meal", delta_color="normal")
            with col3:
                st.metric("🌱 CO₂ Emissions Avoided", f"{co2_saved:.1f} kg", delta="Equivalent to planting 1 tree")

            st.markdown("---")

            st.subheader("Environmental Impact")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("💧 Water Saved", f"{water_saved:,} liters", delta="Equivalent to 8 bathtubs")
            with c2:
                st.metric("🛍️ Plastic Waste Reduced", f"{plastic_reduced} items", delta="Less single-use plastic")
            with c3:
                st.metric("🌳 Trees Saved (approx)", f"{int(r_count * 0.35)}", delta="By reducing delivery waste")

            st.info("💡 By cooking at home instead of ordering delivery, you’re reducing food packaging waste and carbon emissions from delivery riders — a very Malaysian-friendly habit!")
            
            if r_count >= 10:
                st.success("🎉 You’re a Sustainability Champion! Keep it up!")

# ====================== END OF FILE ======================