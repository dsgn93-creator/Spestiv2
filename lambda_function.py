import os
import csv
import json
import re
import urllib.request
import urllib.error
import zipfile
import datetime
import boto3
from collections import defaultdict

def normalize_name(name):
    name = str(name).lower()
    name = re.sub(r'[^\w\s%.,-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def categorize_product(name, raw_category=""):
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
    
    return "Pantry"

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    bucket_name = 'spesti-grocery-data-46367c80'
    output_key = 'products.json'
    
    tmp_dir = '/tmp/grocery_data'
    os.makedirs(tmp_dir, exist_ok=True)
    
    # 1. Download the ZIP file
    today = datetime.datetime.now()
    dates_to_try = [today, today - datetime.timedelta(days=1), today - datetime.timedelta(days=2)]
    
    zip_path = os.path.join(tmp_dir, 'data.zip')
    downloaded = False
    
    for dt in dates_to_try:
        date_str = dt.strftime('%Y-%m-%d')
        url = f"https://kolkostruva.bg/opendata_files/{date_str}.zip"
        print(f"Trying to download: {url}")
        try:
            urllib.request.urlretrieve(url, zip_path)
            print(f"Successfully downloaded data for {date_str}")
            downloaded = True
            break
        except urllib.error.HTTPError as e:
            print(f"HTTPError for {url}: {e.code}")
        except Exception as e:
            print(f"Error downloading from {url}: {e}")
            
    if not downloaded:
        print("Failed to download data for any recent date. Aborting.")
        return {'statusCode': 500, 'body': 'Download failed'}
        
    # 2. Extract ZIP
    extract_dir = os.path.join(tmp_dir, 'extracted')
    os.makedirs(extract_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
        
    # The zip might contain a folder or direct CSVs. Let's find the CSVs.
    csv_dir = extract_dir
    # Check if there's a subdirectory
    extracted_items = os.listdir(extract_dir)
    if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
        csv_dir = os.path.join(extract_dir, extracted_items[0])
        
    # 3. Process Data
    products = defaultdict(lambda: {"name": "", "category": "", "prices": []})
    target_stores = ["лидл", "фантастико", "билла", "метро", "t market", "kaufland", "cba", "penny"]
    
    files_processed = 0
    
    for filename in os.listdir(csv_dir):
        if not filename.endswith('.csv'):
            continue
            
        store_key = filename.lower()
        if not any(ts in store_key for ts in target_stores):
            continue
            
        filepath = os.path.join(csv_dir, filename)
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
    
    output_filepath = os.path.join(tmp_dir, 'products.json')
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(product_list, f, ensure_ascii=False, indent=2)
        
    # 4. Upload to S3
    print(f"Uploading to {bucket_name}/{output_key}")
    s3.upload_file(
        output_filepath, 
        bucket_name, 
        output_key,
        ExtraArgs={'ContentType': 'application/json'}
    )
    print("Upload successful!")
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': f'Successfully updated grocery data based on {date_str}. Processed {len(product_list)} products.'})
    }
