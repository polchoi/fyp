import os
import time
import random
import datetime
import re
import requests
import json
import logging
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# For AWS S3 interaction
import boto3
from botocore.exceptions import ClientError

# AWS S3 Bucket Name and Region
S3_BUCKET_NAME = "housing-listing-bucket"
S3_BUCKET_REGION = "ap-east-1" # Hong Kong

# Get current date string
current_date_str = datetime.date.today().strftime("%Y-%m-%d")

# Log filename
log_filename = f"{current_date_str}-log.log"

# Remove existing log file if it exists
if os.path.exists(log_filename):
    os.remove(log_filename)

# Logging configuration to log to a file named "{date}-log.log"
logging.basicConfig(filename=log_filename, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def to_snake_case(s):
    """
    Converts a given string to snake_case.

    Parameters:
        s (str): The string to convert.

    Returns:
        str: The converted snake_case string.
    """
    s = s.strip()
    # Replace special characters with spaces
    s = re.sub(r'[\s\-]+', ' ', s)
    # Remove any character that is not alphanumeric or space
    s = re.sub(r'[^A-Za-z0-9 ]+', '', s)
    # Convert to lowercase
    s = s.lower()
    # Replace spaces with underscores
    s = s.replace(' ', '_')
    return s

def extract_estate_info(soup):
    """
    Extracts the estate entry date or building age (if available) from a BeautifulSoup object.

    Parameters:
        soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of the 28hse property page.

    Returns:
        dict: A dictionary containing the estate entry date and/or building age, if available.
    """
    # Extracting the estate entry date
    entry_date_tag = soup.find("td", string="Estate Entry Date")

    # Extracting the building age from the specified div
    building_age_div = soup.find("div", class_="pairSubValue", string=lambda x: x and "Building age" in x)

    # Initialize data dictionary
    data = {}

    # Check and add entry date if available
    if entry_date_tag:
        entry_date = entry_date_tag.find_next_sibling("td").get_text(strip=True)
        if entry_date:
            data["estate_entry_date"] = entry_date

    # Check and add building age if available
    if building_age_div:
        building_age = building_age_div.get_text(strip=True).replace("Building age: ", "")
        if building_age:
            data["building_age"] = building_age

    return data

def get_adjacent_facilities(property_id):
    """
    Retrieves adjacent facilities data from the property page using Selenium and JavaScript execution.

    Parameters:
        property_id (str): The ID of the property to retrieve data for.

    Returns:
        dict: A dictionary containing information about nearby facilities (e.g., MTR, Bus, Mall, etc.).
    """
    url = 'https://www.28hse.com/en/rent/residential/property-' + str(property_id)
    # Set up Chrome options
    options = Options()
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver', options=options)

    try:
        # Go to the target URL
        driver.get(url)

        # Wait for the page to load
        time.sleep(2)

        # Click the "Google Map" link
        google_map_link = driver.find_element(By.CLASS_NAME, "googleMap")
        google_map_link.click()
        # Wait for the modal to open
        time.sleep(5)
        accessible_facilities = {}

        # Execute JavaScript to retrieve the data
        mtr_data = driver.execute_script("return map_data_MTRItems;")
        bus_data = driver.execute_script("return map_data_BusItems;")
        mall_data = driver.execute_script("return map_data_MallItems;")
        restaurant_data = driver.execute_script("return map_data_RestaurantItems;")
        school_data = driver.execute_script("return map_data_SchoolItems;")
        bank_data = driver.execute_script("return map_data_BankItems;")
        hospital_data = driver.execute_script("return map_data_HospitalItems;")
        estate_data = driver.execute_script("return map_data_EstateItems;")

        accessible_facilities.update({"mtr": mtr_data})
        accessible_facilities.update({"bus": bus_data})
        accessible_facilities.update({"mall": mall_data})
        accessible_facilities.update({"restaurant": restaurant_data})
        accessible_facilities.update({"school": school_data})
        accessible_facilities.update({"bank": bank_data})
        accessible_facilities.update({"hospital": hospital_data})
        accessible_facilities.update({"estate": estate_data})

    finally:
        driver.quit()
    return accessible_facilities

def transactions_data(soup):
    """
    Extracts transaction data from the property page.

    Parameters:
        soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of the 28hse property page.

    Returns:
        dict: A dictionary containing a list of transactions with details such as header, size, rental, date, etc.
    """
    transactions = []

    # Find the main container holding the transactions
    transaction_elements = soup.find_all('div', class_='mobile_alt latest_3months_or_landreg_result')

    for element in transaction_elements:
        # Find individual content inside each transaction block
        content_elements = element.find_all('div', class_='content')

        for content in content_elements:
            transaction = {}

            # Extract the relevant parts of the transaction
            header = content.find('div', class_='header')
            description = content.find('div', class_='description')
            rental_price = content.find('div', class_='transaction_detail_price_rent')
            extra = content.find_all('div', class_="extra")
            logging.debug(extra[0])
            extra = extra[0].find_all('div', class_="ui label")
            logging.debug(extra)

            transaction['header'] = header.get_text(strip=True) if header else 'N/A'
            transaction['size'] = description.get_text(strip=True) if description else 'N/A'
            transaction['rental'] = rental_price.get_text(strip=True) if rental_price else 'N/A'
            if len(extra) != 0:
                transaction['date'] = extra[0].get_text(strip=True) if extra[0] else 'N/A'
                transaction['source'] = extra[1].get_text(strip=True) if extra[1] else 'N/A'
                transaction['number_of_rooms'] = extra[2].get_text(strip=True) if extra[2] else 'N/A'

            # Convert transaction keys to snake_case
            transaction = {to_snake_case(k): v for k, v in transaction.items()}

            transactions.append(transaction)
    return {"transactions": transactions}

def write_data(data, index):
    """
    Uploads the collected data to AWS S3 as a JSON file.

    Parameters:
        data (dict): The data dictionary to upload.
        index (str): The property ID used as the filename.

    Returns:
        None
    """
    # Convert data dictionary to JSON string
    json_data = json.dumps(data, indent=4)

    # Filename for the object in S3
    s3_filename = f"json-files/{current_date_str}/{index}.json"

    # Initialize S3 client
    s3 = boto3.client('s3', region_name=S3_BUCKET_REGION)

    try:
        # Upload the JSON string to S3
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_filename, Body=json_data)
        logging.info(f"Uploaded {s3_filename} to S3 bucket {S3_BUCKET_NAME}.")
    except ClientError as e:
        logging.error(f"Failed to upload {s3_filename} to S3: {e}")

def read_property(property_id):
    """
    Reads the property data from the website and uploads it to AWS S3.

    Parameters:
        property_id (str): The ID of the property to read.

    Returns:
        bool: True if the property was read successfully, False otherwise.
    """
    data = {}
    local_property_id = property_id
    str_id = str(local_property_id)
    url = "https://www.28hse.com/en/rent/residential/property-" + str_id
    try:
        response = requests.get(url)
    except Exception as e:
        logging.error("Access Denied")
        logging.error(f"Property URL: {url}")
        return False
    soup = BeautifulSoup(response.content, 'html.parser')
    title_and_description = soup.find_all(class_="ui large message")
    if len(title_and_description) == 0:
        logging.warning(f"Not a valid property ID, ID: {property_id}")
        return False

    # Find the header
    header = title_and_description[0].find('div', class_='header')
    description = title_and_description[0].find(id='desc_normal')

    # Get the text from the header
    header_text = header.get_text(separator=" ", strip=True)
    description_text = description.get_text(separator=" ", strip=True)
    data.update({"title": header_text})
    data.update({"description": description_text})

    # Extract the <script> content where lat/lng might be
    script_tags = soup.find_all('script')

    # Regex for geolocation
    pattern = r"else\s*\{lat_o='([^']+)';lng_o='([^']+)';\}"
    lat_o, lng_o = None, None

    # Loop through all script tags and search for the pattern
    for script in script_tags:
        script_content = script.string
        if script_content:
            # Remove spaces and line breaks to ensure matching
            script_no_space = re.sub(r'\s+', '', script_content)
            match = re.findall(pattern, script_no_space, re.DOTALL)

            if match:
                lat_o = match[0][0]  # latitude
                lng_o = match[0][1]  # longitude
                break
    if not lat_o or not lng_o:
        logging.warning("No Geolocation Data")

    # Exclude script from soup content
    for script in soup.find_all('script'):
        script.extract()

    # Extract relevant property data
    main_table = soup.find_all(class_="tablePair")

    for table in main_table:
        # Extract data from each table pair
        left = table.find_all(class_='table_left')
        right = table.find_all(class_='table_right')

        left_list = [i.get_text(strip=True) for i in left]
        right_list = [i.get_text(strip=True) for i in right]

        # Convert keys to snake_case
        left_list = [to_snake_case(key) for key in left_list]

        # Add to the main data dictionary
        data.update(dict(zip(left_list, right_list)))

    # Add latitude and longitude to the data
    if lat_o and lng_o:
        data['latitude'] = lat_o
        data['longitude'] = lng_o

    # transaction = transactions_data(soup)
    # data.update(transaction)
    # adj = get_adjacent_facilities(property_id)
    # data.update(adj)
    building_age = extract_estate_info(soup)
    if len(building_age) != 0:
        data.update(building_age)
    write_data(data, property_id)
    return True

def generate_need_update():
    """
    Generates the list of property IDs that need to be updated by scraping the website.

    Returns:
        None
    """
    # Set up ChromeDriver
    options = Options()
    options.add_argument('--headless')

    # Initialize the driver
    driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver', options=options)

    # URL of the first page to scrape
    base_url = "https://www.28hse.com/en/rent"
    driver.get(base_url)

    time.sleep(3)
    
    # Locate all pagination links
    pagination_items = driver.find_elements(By.CSS_SELECTOR, ".ui.menu.pagination a.item:not(.disabled)")

    # Extract the page numbers
    page_numbers = []
    for item in pagination_items:
        attr_value = item.get_attribute("attr1")
        if attr_value and attr_value.isdigit():
            page_numbers.append(int(attr_value))

    # Get the maximum page number
    if page_numbers:
        max_page = max(page_numbers)
    else:
        logging.info("No page numbers found.")
    property_ids = []
    logging.info(f"Extracted maximum page number: {max_page}")

    page_count = 0
    while True:
        # Wait for the page to load
        time.sleep(random.randint(3, 4))
        try:
            # Find all property elements on the current page
            properties = driver.find_elements(By.CLASS_NAME, "detail_page")

            # Extract the 'attr1' property IDs
            for prop in properties:
                property_id = prop.get_attribute("attr1")
                if property_id:
                    property_ids.append(property_id)
            page_count += 1
            logging.info(f"Collected {page_count} pages so far...")

            # Edge Case
            # if page_count == 2000:
            if page_count == max_page:  # TEST
                break

        except Exception as e:
            logging.error(f"An error occurred on this page: {e}")
            # If error occurs during scraping, do nothing and move to checking next button

        # Always check and attempt to click the "Next" button
        try:
            # Try to find the 'Next' button for pagination
            next_button = driver.find_element(By.CSS_SELECTOR, 'a.item[attr1="plus"]')
            driver.execute_script("arguments[0].scrollIntoView();", next_button)

            # If the 'Next' button is found and clickable, click it
            if next_button.is_enabled():
                next_button.click()
                logging.info("Moving to the next page...")
            else:
                logging.info("No more pages. Scraping complete.")
                break

        except Exception as e:
            # If 'Next' button is not found or any error occurs, stop scraping (no more pages)
            print(e)
            logging.info("No more pages or error with Next button. Scraping complete.")
            break

    # Close the browser after scraping
    driver.quit()

    # Removing Duplicates
    property_ids = list(set(property_ids))

    logging.info(f"Total Number of {len(property_ids)} IDs are Found")

    # Initialize S3 client
    s3 = boto3.client('s3', region_name=S3_BUCKET_REGION)
    completed_ids = set()

    try:
        completed_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key='completed.txt')
        completed_ids = set(completed_obj['Body'].read().decode('utf-8').splitlines())
    except s3.exceptions.NoSuchKey:
        logging.info("completed.txt not found in S3. Starting fresh.")
    except Exception as e:
        logging.error(f"Error reading completed.txt from S3: {e}")

    unique_ids = [estate_id for estate_id in property_ids if estate_id not in completed_ids]

    logging.info(f"Total Number of {len(unique_ids)} IDs need to be scraped")

    # Write need_update.txt to S3
    need_update_content = "\n".join(unique_ids)
    try:
        s3.put_object(Bucket=S3_BUCKET_NAME, Key='need_update.txt', Body=need_update_content)
        logging.info("need_update.txt has been uploaded to S3.")
    except Exception as e:
        logging.error(f"Failed to upload need_update.txt to S3: {e}")

def merge_ids():
    """
    Merges IDs from need_update.txt into completed.txt on S3, avoiding duplicates.

    Returns:
        None
    """
    # Initialize S3 client
    s3 = boto3.client('s3', region_name=S3_BUCKET_REGION)

    # Read need_update.txt from S3
    try:
        need_update_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key='need_update.txt')
        need_update_ids = set(need_update_obj['Body'].read().decode('utf-8').splitlines())
    except s3.exceptions.NoSuchKey:
        logging.info("need_update.txt does not exist in S3. No IDs to merge.")
        return
    except Exception as e:
        logging.error(f"Error reading need_update.txt from S3: {e}")
        return

    # Read completed.txt from S3
    try:
        completed_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key='completed.txt')
        completed_ids = set(completed_obj['Body'].read().decode('utf-8').splitlines())
    except s3.exceptions.NoSuchKey:
        completed_ids = set()
    except Exception as e:
        logging.error(f"Error reading completed.txt from S3: {e}")
        return

    # Merge IDs, avoiding duplicates
    all_ids = completed_ids.union(need_update_ids)

    # Write back to completed.txt on S3
    completed_content = "\n".join(sorted(all_ids))
    try:
        s3.put_object(Bucket=S3_BUCKET_NAME, Key='completed.txt', Body=completed_content)
        logging.info(f"Merged {len(need_update_ids)} IDs into completed.txt on S3.")
    except Exception as e:
        logging.error(f"Failed to upload completed.txt to S3: {e}")

    # Delete need_update.txt from S3
    try:
        s3.delete_object(Bucket=S3_BUCKET_NAME, Key='need_update.txt')
        logging.info("need_update.txt has been deleted from S3.")
    except Exception as e:
        logging.error(f"Failed to delete need_update.txt from S3: {e}")

def main():
    """
    Main function that runs the data collection process.

    Returns:
        bool: True if the process completed successfully, False otherwise.
    """
    # Generate the need_update.txt file
    generate_need_update()

    # Initialize S3 client
    s3 = boto3.client('s3', region_name=S3_BUCKET_REGION)

    # Read need_update.txt from S3
    try:
        need_update_obj = s3.get_object(Bucket=S3_BUCKET_NAME, Key='need_update.txt')
        ids = need_update_obj['Body'].read().decode('utf-8').splitlines()
    except s3.exceptions.NoSuchKey:
        logging.info("need_update.txt not found in S3.")
        return True  # Considered success since there's nothing to process
    except Exception as e:
        logging.error(f"Error reading need_update.txt from S3: {e}")
        return False

    logging.info(f"{len(ids)} IDs read from need_update.txt")

    # List existing files in S3 bucket under today's date folder
    existing_files = set()
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=f"json-files/{current_date_str}/")

        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json'):
                    filename = key.split('/')[-1]
                    file_id = filename.split('.json')[0]
                    existing_files.add(file_id)
    except Exception as e:
        logging.error(f"Error listing objects in S3 bucket: {e}")

    unique_ids = set(ids) - existing_files
    logging.info(f"{len(unique_ids)} unique IDs to process")

    for property_id in unique_ids:
        try:
            success = read_property(property_id)
            if not success:
                logging.warning(f"Failed to read property {property_id}")
        except Exception as e:
            logging.error(f"An error occurred while processing property {property_id}: {e}")
            raise e
    return True

if __name__ == '__main__':
    max_retries = 3
    retries = 0
    while retries < max_retries:
        try:
            logging.info("Starting the data collection process...")
            main()
            logging.info("Data collection completed successfully.")

            # Merge IDs from need_update.txt into completed.txt
            merge_ids()

            break
        except Exception as e:
            retries += 1
            logging.error(f"An error occurred during data collection: {e}")
            logging.info(f"Retrying... ({retries}/{max_retries})")
            if retries == max_retries:
                logging.error("Maximum retries reached. Exiting.")
                exit(1)

    # After the script finishes, upload the log file to S3
    s3 = boto3.client('s3', region_name=S3_BUCKET_REGION)
    log_s3_key = f"logs/{current_date_str}-log.log"

    try:
        with open(log_filename, 'rb') as log_file:
            s3.upload_fileobj(log_file, S3_BUCKET_NAME, log_s3_key)
        logging.info(f"Log file {log_filename} uploaded to S3 bucket {S3_BUCKET_NAME} with key {log_s3_key}.")
    except Exception as e:
        logging.error(f"Failed to upload log file to S3: {e}")

    # Shutdown logging to ensure all handlers are closed
    logging.shutdown()

    # Delete the local log file after uploading
    if os.path.exists(log_filename):
        os.remove(log_filename)
