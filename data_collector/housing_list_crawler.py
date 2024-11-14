import os
import time
import random
import datetime
import re
import requests
import json
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

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
    url = 'https://www.28hse.com/en/rent/residential/property-' + str(property_id)
    # Set up Chrome options
    options = Options()
    options.add_argument("--headless")  # Run in headless mode (no GUI)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(executable_path='./chromedriver', options=options)

    try:
        # Go to the target URL
        driver.get(url)

        # Wait for the page to load (you may need to adjust this)
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
        # Close the driver
        driver.quit()
    return accessible_facilities

def transactions_data(soup):
    # Step 2: Parse the transaction data
    transactions = []

    # Find the main container holding the transactions
    transaction_elements = soup.find_all('div', class_='mobile_alt latest_3months_or_landreg_result')

    for element in transaction_elements:
        # Now find individual content inside each transaction block
        content_elements = element.find_all('div', class_='content')

        for content in content_elements:
            transaction = {}

            # Extract the relevant parts of the transaction
            header = content.find('div', class_='header')
            description = content.find('div', class_='description')
            rental_price = content.find('div', class_='transaction_detail_price_rent')
            extra = content.find_all('div', class_="extra")
            print(extra[0])
            extra = extra[0].find_all('div', class_="ui label")
            print(extra)

            transaction['header'] = header.get_text(strip=True) if header else 'N/A'
            transaction['size'] = description.get_text(strip=True) if description else 'N/A'
            transaction['rental'] = rental_price.get_text(strip=True) if rental_price else 'N/A'
            if len(extra) != 0:
                transaction['date'] = extra[0].get_text(strip=True) if extra[0] else 'N/A'
                transaction['source'] = extra[1].get_text(strip=True) if extra[1] else 'N/A'
                transaction['number_of_rooms'] = extra[2].get_text(strip=True) if extra[2] else 'N/A'

            # Convert transaction keys to snake_case
            transaction = {to_snake_case(k): v for k, v in transaction.items()}

            # Append each transaction to the list
            transactions.append(transaction)
    return {"transactions": transactions}

def write_data(data, index, dir_path):

    # Specify the file path where you want to save the JSON file
    file_path = os.path.join(dir_path, str(index) + ".json")

    # Write the data to a JSON file
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f'JSON file {file_path} has been created successfully.')

def read_property(property_id, dir_path):
    data = {}
    local_property_id = property_id
    str_id = str(local_property_id)
    url = "https://www.28hse.com/en/rent/residential/property-" + str_id
    try:
        response = requests.get(url)
    except Exception as e:
        print("Access Denied")
        print("Property URL:", url)
        return False
    soup = BeautifulSoup(response.content, 'html.parser')
    title_and_description = soup.find_all(class_="ui large message")
    if len(title_and_description) == 0:
        print("Not a valid property ID, ID: ", property_id)
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
                lat_o = match[0][0]  # First capture group (latitude)
                lng_o = match[0][1]  # Second capture group (longitude)
                break  # If found, no need to continue
    if not lat_o or not lng_o:
        print("No Geolocation Data")

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
    write_data(data, property_id, dir_path)
    return True

def generate_need_update():
    # Set up ChromeDriver
    options = Options()
    options.add_argument('--headless')  # Optional: run headless, comment out if you want to see the browser window

    # Initialize the driver
    driver = webdriver.Chrome(executable_path='./chromedriver', options=options)

    # URL of the first page to scrape
    base_url = "https://www.28hse.com/en/rent"
    driver.get(base_url)

    # List to store property IDs
    property_ids = []

    # Scraping logic with pagination
    page_count = 0
    while True:
        # Wait for the page to load
        time.sleep(random.randint(2, 2))
        try:
            # Find all property elements on the current page
            properties = driver.find_elements(By.CLASS_NAME, "detail_page")

            # Extract the 'attr1' property IDs
            for prop in properties:
                property_id = prop.get_attribute("attr1")
                if property_id:
                    property_ids.append(property_id)
            page_count += 1
            print(f"Collected {page_count} pages so far...")
            # Edge Case
            # if page_count == 2000:
            if page_count == 2:
                break

        except Exception as e:
            print(f"An error occurred on this page: {e}")
            # If error occurs during scraping, do nothing and move to checking next button

        # Always check and attempt to click the "Next" button
        try:
            # Try to find the 'Next' button for pagination
            next_button = driver.find_element(By.CSS_SELECTOR, 'a.item[attr1="plus"]')

            # If the 'Next' button is found and clickable, click it
            if next_button.is_enabled():
                next_button.click()
                print("Moving to the next page...")
            else:
                print("No more pages. Scraping complete.")
                break

        except Exception as e:
            # If 'Next' button is not found or any error occurs, stop scraping (no more pages)
            print("No more pages or error with Next button. Scraping complete.")
            break

    # Close the browser after scraping
    driver.quit()

    # Removing Duplicates
    property_ids = list(set(property_ids))

    print("Total Number of", len(property_ids), "IDs are Found")

    if os.path.exists("completed.txt"):
        with open("completed.txt") as file:
            past_ids = file.read().splitlines()
    else:
        past_ids = []

    unique_ids = [estate_id for estate_id in property_ids if estate_id not in past_ids]

    print("Total Number of", len(unique_ids), "IDs need to be scraped")

    with open("need_update.txt", "w") as file:
        for estate_id in unique_ids:
            file.write(estate_id)
            file.write("\n")

    print("List is written as need_update.txt")

def merge_ids():
    """
    Merges IDs from need_update.txt into completed.txt, avoiding duplicates.
    """
    need_update_file = 'need_update.txt'
    completed_file = 'completed.txt'

    if not os.path.exists(need_update_file):
        print(f"{need_update_file} does not exist. No IDs to merge.")
        return

    # Read IDs from need_update.txt
    with open(need_update_file, 'r') as f:
        need_update_ids = set(f.read().splitlines())

    # Read IDs from completed.txt
    if os.path.exists(completed_file):
        with open(completed_file, 'r') as f:
            completed_ids = set(f.read().splitlines())
    else:
        completed_ids = set()

    # Merge IDs, avoiding duplicates
    all_ids = completed_ids.union(need_update_ids)

    # Write back to completed.txt
    with open(completed_file, 'w') as f:
        for id_ in sorted(all_ids):
            f.write(f"{id_}\n")
    print(f"Merged {len(need_update_ids)} IDs into {completed_file}.")

def main():
    # Generate the need_update.txt file
    generate_need_update()

    file_name = "need_update.txt"
    dir_path = "./housing_data/" + str(datetime.date.today())
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    existing_files = {f.split(".json")[0] for f in os.listdir(dir_path) if f.endswith(".json")}
    print(len(existing_files))

    if not os.path.exists(file_name):
        print(f"{file_name} not found.")
        return True  # Considered success since there's nothing to process
    else:
        with open(file_name, "r") as file:
            ids = file.read().splitlines()
        print(len(ids))
        unique_ids = set(ids) - set(existing_files)
        print(len(unique_ids))
        for property_id in unique_ids:
            try:
                success = read_property(property_id, dir_path)
                if not success:
                    print(f"Failed to read property {property_id}")
            except Exception as e:
                print(f"An error occurred while processing property {property_id}: {e}")
                raise e  # Re-raise the exception to be caught in the retry logic
    return True  # If everything went well

if __name__ == '__main__':
    max_retries = 3
    retries = 0
    while retries < max_retries:
        try:
            print("Starting the data collection process...")
            main()
            print("Data collection completed successfully.")

            # Merge IDs from need_update.txt into completed.txt
            merge_ids()

            # Delete need_update.txt
            if os.path.exists('need_update.txt'):
                os.remove('need_update.txt')
                print("need_update.txt has been deleted.")
            else:
                print("need_update.txt does not exist.")

            break  # Exit the loop since the process was successful
        except Exception as e:
            retries += 1
            print(f"An error occurred during data collection: {e}")
            print(f"Retrying... ({retries}/{max_retries})")
            if retries == max_retries:
                print("Maximum retries reached. Exiting.")
                exit(1)