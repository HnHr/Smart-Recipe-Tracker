# Smart Recipe Tracker

A full-stack web application built using Python and Streamlit to manage kitchen inventory, track nutritional macro goals, plan meals, and discover recipes using smart inventory matching and AI analysis.

## Core Tech Stack
* Frontend & UI: Streamlit
* Database: SQLite3 (Local file-based system storage)
* Core Languages: Python, SQL
* APIs Integrated: Google Gemini API (gemini-2.5-flash), Spoonacular API

## How to Set Up and Run

1. Clone or download this project folder onto your computer.

2. Open your terminal inside the project directory and create a virtual environment:
   python -m venv venv

3. Activate the virtual environment:
   * Windows: venv\Scripts\activate
   * Mac/Linux: source venv/bin/activate

4. Install the required dependencies:
   pip install streamlit anthropic requests python-dotenv google-generativeai Pillow

5. Create a file named `.env` in the root directory of the app and paste your API keys inside it:
   SPOONACULAR_KEYS=your_spoonacular_key_here
   GEMINI_API_KEYS=your_gemini_api_key_here

6. Run the application locally:
   streamlit run app.py

Note: On launch, sign up with any test username and password. The email field does not require active verification.

## Local Database Architecture
The application automatically creates a local SQLite database file named `kitchen.db` in the root directory upon startup. If you ever need to completely reset the system state, user credentials, or pantry mock inventory, simply close the app and delete the `kitchen.db` file.

The system relies on six connected relational tables:
* users: Stores hashed user credentials, physiological metrics, selected macro targets, and calculated TDEE.
* pantry: Houses current logged ingredients tracking total weight in grams, raw units, and expiration tracking parameters.
* meal_plan: Stores planned recipes assigned to breakfast, lunch, or dinner slots for particular calendar dates.
* nutrition_log: Tracks daily consumed caloric values alongside detailed macronutrient weights (protein, carbs, fats).
* recipe_history: Keeps a running ledger of every meal successfully cooked at home to track user XP metrics.
* recipe_favorites: Saves individual user bookmarks for favored recipes.

## Key Technical Features Implementation

### 1. Ingredient Normalization Engine
To avoid duplicate entries or mismatches between user inventory and Spoonacular API naming systems, I built a regex-based string normalization function. It automatically converts slang, plural variants, structural preparations (e.g., "minced", "diced"), and bilingual Malay text inputs into clean, standard English database tokens.

### 2. High-Availability API Rotation System
To avoid runtime errors due to API rate constraints, both the Spoonacular and Gemini integrations utilize a silent index-rotation mechanism. If a call encounters a 429 rate-limit error, the application automatically catches the exception, switches to an alternate fallback key listed in the environment array, and attempts the query again without disrupting user experience.

### 3. Automated Inventory Subtraction Logic
When a user completes a recipe via Cook Mode, the app isolates the raw ingredients required. It passes the current recipe text and active pantry state to the Gemini API to find the best match. Once confirmed, it automatically subtracts the exact proportional weights from the local SQLite pantry table and recalculates fresh systemic nutrition.