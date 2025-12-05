from flask import Flask, render_template, request, jsonify
import pandas as pd
import requests 
import os # Path Handling के लिए import

app = Flask(__name__)

# ==============================================================================
# ⚠️ Spoonacular API Key 
# ==============================================================================
SPOONACULAR_API_KEY = "e66b732d58b542aba375f7b0a2cf931c"
# ==============================================================================

def search_online_recipes(ingredient):
    """Spoonacular API का उपयोग करके व्यंजनों की खोज करता है।"""
    if not SPOONACULAR_API_KEY or SPOONACULAR_API_KEY == "YOe66b732d58b542aba375f7b0a2cf931c":
        print("ERROR: Spoonacular API Key not set or default value used.")
        return []

    api_url = "https://api.spoonacular.com/recipes/complexSearch"
    params = {
        'apiKey': SPOONACULAR_API_KEY,
        'query': ingredient,
        'number': 15,
        'addRecipeInformation': False,
        'fillIngredients': False
    }
    
    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        recipes = []
        if data.get('results'):
            for result in data['results']:
                recipes.append({
                    'TranslatedRecipeName': result.get('title', 'No Name'),
                    'RecipeID_online': result.get('id'),
                    'is_veg': None, 
                    'Cuisine': 'Global (API)',
                    'image_url': result.get('image')
                })
        return recipes
        
    except requests.exceptions.RequestException as e:
        print(f"Error during API call: {e}")
        return []

def fetch_online_recipe_details(online_id):
    """Spoonacular ID का उपयोग करके पूर्ण व्यंजन विवरण प्राप्त करता है।"""
    if not SPOONACULAR_API_KEY or SPOONACULAR_API_KEY == "YOUR_SPOONACULAR_API_KEY_HERE":
        return None
        
    api_url = f"https://api.spoonacular.com/recipes/{online_id}/information"
    params = {
        'apiKey': SPOONACULAR_API_KEY,
        'includeNutrition': False
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        meal = response.json()
        
        if meal:
            ingredients = []
            if meal.get('extendedIngredients'):
                for ing in meal['extendedIngredients']:
                    ingredients.append(f"{ing.get('amount', '')} {ing.get('unit', '')} {ing.get('name', '')}".strip())

            instructions_raw = meal.get('instructions', meal.get('summary', 'No instructions found.'))
            instructions_cleaned = requests.utils.unquote(instructions_raw.replace('<p>', '').replace('</p>', '').replace('<li>', '').replace('</li>', ''))
            instructions_split = instructions_cleaned.split('.')
                    
            return {
                'TranslatedRecipeName': meal.get('title'),
                'Cuisine': ', '.join(meal.get('cuisines', [])),
                'TranslatedIngredients': ', '.join(ingredients), 
                'TranslatedInstructions': '. '.join(filter(None, instructions_split)),
                'is_veg': meal.get('vegetarian', False),
                'image_url': meal.get('image', None) 
            }
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching online details: {e}")
        return None

try:
    # CSV लोडिंग फिक्स: Python स्क्रिप्ट की निर्देशिका से फ़ाइल पथ बनाएँ
    csv_path = os.path.join(os.path.dirname(__file__), 'IndianFoodDataset.csv')
    
    df = pd.read_csv(csv_path) 
    
    df['is_veg'] = ~df['Diet'].str.contains('Non Vegeterian', case=False, na=True)
    print("Dataset loaded successfully.")
except FileNotFoundError:
    print("ERROR: IndianFoodDataset.csv not found! Only online search will work.")
    df = pd.DataFrame() 

@app.route('/')
def home():
    """होम पेज रेंडर करता है।"""
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    """सामग्री द्वारा व्यंजनों की खोज करता है।"""
    query_str = request.form.get('ingredient', '').strip().lower()
    data_source = request.form.get('data_source', 'offline')
    
    found_recipes = []
    batch_size = 15 # एक बार में दिखाने के लिए रेसिपी की संख्या
    
    if not query_str:
        return render_template('index.html', error="Please enter an ingredient to search.")

    if data_source == 'online':
        # ऑनलाइन API से खोजें
        found_recipes = search_online_recipes(query_str)
        total_count = len(found_recipes)
        recipes_to_show = found_recipes[:batch_size]

        next_start = batch_size if total_count > batch_size else None
        
        return render_template('results.html', 
                               recipes=recipes_to_show, 
                               ingredient=query_str, 
                               data_source='online',
                               next_start=next_start,
                               total_count=total_count)
        
    else: # data_source == 'offline'
        # ऑफलाइन CSV से खोजें 
        if not df.empty:
            # ऑफ़लाइन CSV खोज सुधार के लिए keyword_map
            keyword_map = {
                'potato': ['potato', 'aloo', 'aloo matter'],
                'rice': ['rice', 'chawal', 'basmati', 'pulao'],
            }
            
            search_terms = [query_str]
            if query_str in keyword_map:
                search_terms.extend(keyword_map[query_str])
            
            search_pattern = '|'.join(list(set(search_terms)))
            
            mask = df['TranslatedIngredients'].str.contains(search_pattern, case=False, na=False)
            offline_recipes = df[mask].copy()
            
            total_count = len(offline_recipes)
            
            # पहले 15 परिणाम दिखाएँ
            recipes_to_show_df = offline_recipes[:batch_size].copy()
            recipes_to_show_df['RecipeID_offline'] = recipes_to_show_df.index 
            found_recipes = recipes_to_show_df.to_dict(orient='records')
            
            next_start = batch_size if total_count > batch_size else None
        
        return render_template('results.html', 
                               recipes=found_recipes, 
                               ingredient=query_str, 
                               data_source='offline',
                               next_start=next_start,
                               total_count=total_count)


@app.route('/load_more', methods=['POST'])
def load_more():
    """POST request से ऑफ़लाइन CSV के अगले परिणाम लोड करता है।"""
    ingredient = request.form.get('ingredient', '').strip().lower()
    data_source = request.form.get('data_source', 'offline')
    start_index = int(request.form.get('start_index', 0)) 
    batch_size = 15
    
    if data_source == 'online' or df.empty:
        return jsonify({'recipes': [], 'next_start': None})

    # ऑफ़लाइन खोज लॉजिक दोहराएँ
    keyword_map = {'potato': ['potato', 'aloo', 'aloo matter'], 'rice': ['rice', 'chawal', 'basmati', 'pulao']}
    search_terms = [ingredient]
    if ingredient in keyword_map:
        search_terms.extend(keyword_map[ingredient])
    
    search_pattern = '|'.join(list(set(search_terms)))
    mask = df['TranslatedIngredients'].str.contains(search_pattern, case=False, na=False)
    offline_recipes = df[mask].copy()
    
    # स्लाइसिंग द्वारा अगले 15 परिणाम प्राप्त करें
    end_index = start_index + batch_size
    
    recipes_to_show_df = offline_recipes[start_index:end_index].copy()
    recipes_to_show_df['RecipeID_offline'] = recipes_to_show_df.index
    recipes_to_show = recipes_to_show_df.to_dict(orient='records')
    
    total_count = len(offline_recipes)
    
    if end_index < total_count:
        next_start = end_index
    else:
        next_start = None

    return jsonify({'recipes': recipes_to_show, 'next_start': next_start})


@app.route('/cuisine/<cuisine_name>')
def search_by_cuisine(cuisine_name):
    """व्यंजन के नाम से खोज करता है।"""
    found_recipes = []
    batch_size = 15
    
    if not df.empty:
        mask = df['Cuisine'].str.contains(cuisine_name, case=False, na=False)
        offline_recipes = df[mask].copy()
        
        total_count = len(offline_recipes)
        
        # पहले 15 परिणाम दिखाएँ
        recipes_to_show_df = offline_recipes[:batch_size].copy()
        recipes_to_show_df['RecipeID_offline'] = recipes_to_show_df.index 
        found_recipes = recipes_to_show_df.to_dict(orient='records')

        next_start = batch_size if total_count > batch_size else None
        
    return render_template('results.html', 
                           recipes=found_recipes, 
                           ingredient=cuisine_name, 
                           data_source='offline',
                           next_start=next_start,
                           total_count=total_count)


@app.route('/recipe/offline/<int:recipe_id>')
def recipe_details_offline(recipe_id):
    """स्थानीय DataFrame से ऑफ़लाइन व्यंजन विवरण प्राप्त करता है।"""
    recipe = None
    if not df.empty and 0 <= recipe_id < len(df):
     
        recipe = df.iloc[recipe_id].to_dict()
        if recipe:
            recipe['image_url'] = None 
    
    return render_template('details.html', recipe=recipe)


@app.route('/recipe/online/<online_id>')
def recipe_details_online(online_id):
    """बाहरी API से ऑनलाइन व्यंजन विवरण प्राप्त करता है।"""
    recipe = fetch_online_recipe_details(online_id)
    return render_template('details.html', recipe=recipe)


if __name__ == '__main__':
    app.run(debug=True)