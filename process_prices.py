import os
import csv
import json
import re
from collections import defaultdict

def normalize_name(name):
    """
    Normalizes the product name to allow for fuzzy grouping across stores.
    Removes quotes, extra whitespace, and standardizes to lowercase.
    """
    name = str(name).lower()
    # Remove special characters but keep numbers, text, %, commas, dots, hyphens
    name = re.sub(r'[^\w\s%.,-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def categorize_product(name, raw_category=""):
    """
    Tries to map the product into one of the Spesti UI categories based on keywords.
    UI Cats: Milk, Butter, White Cheese, Yogurt, Eggs, Bread, Meat, Produce, Pantry, Drinks, Household, Snacks, Frozen
    """
    n = name.lower()
    
    if any(k in n for k in ['прясно мляко', 'мляко uht']): return "Milk"
    if any(k in n for k in ['масло', 'краве масло']): return "Butter"
    if any(k in n for k in ['сирене']): return "White Cheese"
    if any(k in n for k in ['кисело мляко']): return "Yogurt"
    if any(k in n for k in ['яйца', 'яйце']): return "Eggs"
    if any(k in n for k in ['хляб', 'питка', 'багета']): return "Bread"
    
    if any(k in n for k in ['свинско', 'пилешко', 'кайма', 'кюфтета', 'кебапчета', 'наденица', 'салам', 'луканка', 'телешко', 'риба', 'филе']): return "Meat"
    if any(k in n for k in ['домати', 'краставици', 'картофи', 'лук', 'ябълки', 'банани', 'лимони', 'портокали', 'чушки', 'моркови', 'магданоз', 'копър', 'чесън', 'салата', 'гъби']): return "Produce"
    
    if any(k in n for k in ['бира', 'вино', 'вода', 'сок', 'нектар', 'кока-кола', 'фанта', 'спрайт', 'пепси', 'чай', 'кафе']): return "Drinks"
    if any(k in n for k in ['тоалетна хартия', 'препарат', 'прах за пране', 'омекотител', 'шампоан', 'паста за зъби', 'сапун', 'гъби', 'торби', 'салфетки']): return "Household"
    if any(k in n for k in ['чипс', 'шоколад', 'бисквити', 'ядки', 'вафла', 'бонбони', 'снакс', 'солети']): return "Snacks"
    if any(k in n for k in ['сладолед', 'замразен', 'замразена', 'пелмени', 'пица']): return "Frozen"
    
    return "Pantry" # Default fallback for oil, sugar, rice, pasta, etc.

def process_directory(input_dir, output_file):
    # Dictionary to hold the grouped products
    products = defaultdict(lambda: {"name": "", "category": "", "prices": []})
    
    # For MVP, focus on major supermarket chains to keep the JSON size reasonable
    target_stores = ["лидл", "фантастико", "билла", "метро", "t market", "kaufland", "cba", "penny"]

    files_processed = 0
    if not os.path.exists(input_dir):
        print(f"Directory not found: {input_dir}")
        return

    for filename in os.listdir(input_dir):
        if not filename.endswith('.csv'):
            continue
            
        # Check if the file is from one of the target major stores
        store_key = filename.lower()
        if not any(ts in store_key for ts in target_stores):
            continue

        filepath = os.path.join(input_dir, filename)
        store_name_short = filename.split('_')[0].strip()
        files_processed += 1
        print(f"Reading: {filename}")
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row.get('Наименование на продукта')
                raw_cat = row.get('Категория', '')
                location = row.get('Търговски обект', '')
                retail_price = row.get('Цена на дребно', '')
                promo_price = row.get('Цена в промоция', '')
                
                if not raw_name or not retail_price:
                    continue
                
                # Prices might be using comma as decimal separator
                retail_price = retail_price.replace(',', '.')
                promo_price = promo_price.replace(',', '.') if promo_price else None
                
                try:
                    retail_price = float(retail_price)
                except ValueError:
                    continue
                
                try:
                    promo_price = float(promo_price) if promo_price else None
                except ValueError:
                    promo_price = None
                
                norm_name = normalize_name(raw_name)
                
                if norm_name:
                    # Keep the original title-cased name if not already set
                    if not products[norm_name]["name"]:
                        products[norm_name]["name"] = raw_name
                        products[norm_name]["category"] = categorize_product(raw_name, raw_cat)
                    
                    price_entry = {
                        "store": store_name_short,
                        "location": location,
                        "retail_price": retail_price
                    }
                    if promo_price:
                        price_entry["promo_price"] = promo_price
                        
                    products[norm_name]["prices"].append(price_entry)

    print(f"Processed {files_processed} files.")
    print(f"Found {len(products)} unique products.")
    
    # Convert to list and sort by alphabetical name
    product_list = [
        {
            "id": k, 
            "name": v["name"], 
            "category": v["category"], 
            "prices": v["prices"]
        } 
        for k, v in products.items()
    ]
    product_list.sort(key=lambda x: str(x["name"]))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(product_list, f, ensure_ascii=False, indent=2)
    print(f"Data successfully exported to {output_file}")

if __name__ == "__main__":
    import sys
    # Default to the known 2026-03-10 snapshot if no argument provided
    input_directory = sys.argv[1] if len(sys.argv) > 1 else "/Users/Presidential/Downloads/2026-03-10"
    output_filepath = sys.argv[2] if len(sys.argv) > 2 else "products.json"
    process_directory(input_directory, output_filepath)
