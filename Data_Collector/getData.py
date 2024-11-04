import datetime
from bs4 import BeautifulSoup
import json
import requests
import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
#from multiprocessing import Pool
from bs4 import BeautifulSoup


def extract_estate_info(soup):
    """
    Extracts the estate entry date or building age (if available) from a BeautifulSoup object.

    Parameters:
        soup (BeautifulSoup): A BeautifulSoup object containing the parsed HTML of the 28hse property page.

    Returns:
        dict: A dictionary containing the estate entry date and/or building age, if available.
    """

    # Extracting the estate entry date
    entry_date_tag = soup.find("td", text="Estate Entry Date")

    # Extracting the building age from the specified div
    building_age_div = soup.find("div", class_="pairSubValue", text=lambda x: x and "Building age" in x)

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


def get_adj(propertyID):
    url = 'https://www.28hse.com/en/rent/residential/property-'+ str(propertyID)
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(executable_path='./chromedriver')

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
        Accessable_Facilities = {}

        # Execute JavaScript to retrieve the data
        MTR_data = driver.execute_script("return map_data_MTRItems;")
        Bus_data = driver.execute_script("return map_data_BusItems;")
        Mall_data = driver.execute_script("return map_data_MallItems;")
        Restaurant_data = driver.execute_script("return map_data_RestaurantItems;")
        School_data = driver.execute_script("return map_data_SchoolItems;")
        Bank_data = driver.execute_script("return map_data_BankItems;")
        Hospital_data = driver.execute_script("return map_data_HospitalItems;")
        Estate_data = driver.execute_script("return map_data_EstateItems;")
        # Adjust as necessary
        Accessable_Facilities.update({"MTR":MTR_data})
        Accessable_Facilities.update({"Bus": Bus_data})
        Accessable_Facilities.update({"Mall": Mall_data})
        Accessable_Facilities.update({"Restaurant": Restaurant_data})
        Accessable_Facilities.update({"School": School_data})
        Accessable_Facilities.update({"Bank": Bank_data})
        Accessable_Facilities.update({"Hospital": Hospital_data})
        Accessable_Facilities.update({"Estate": Estate_data})

    finally:
        # Close the driver
        driver.quit()
    return Accessable_Facilities
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
            if len(extra)!= 0:
                transaction['date'] = extra[0].get_text(strip=True) if extra[0] else 'N/A'
                transaction['source'] = extra[1].get_text(strip=True) if extra[1] else 'N/A'
                transaction['Number of Rooms'] = extra[2].get_text(strip=True) if extra[2] else 'N/A'



            # Append each transaction to the list
            transactions.append(transaction)
    return {"transactions": transactions}

def write(data, index,dir_path):

    # Specify the file path where you want to save the JSON file
    file_path = os.path.join(dir_path, str(index) + ".json")

    # Write the data to a JSON file
    with open(file_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print(f'JSON file {file_path} has been created successfully.')


def read(propertyID,dir_path):
    data = {}
    localpropertyID = propertyID
    strID = str(localpropertyID)
    url = "https://www.28hse.com/en/rent/residential/property-" + strID
    try:
        r = requests.get(url)
    except:
        print("Access Denied")
        print("Property URL:",url)
        return False
    soup = BeautifulSoup(r.content, 'html.parser')
    titleandDescription = soup.find_all(class_= "ui large message")
    if len(titleandDescription) == 0:
        print("Not a valid property ID, ID: ", propertyID)
        return False
    # Find the header
    header = titleandDescription[0].find('div', class_='header')
    description = titleandDescription[0].find(id='desc_normal')

    # Get the text from the header
    header_text = header.get_text(separator=" ", strip=True)
    description = description.get_text(separator=" ", strip=True)
    data.update({"Title": header_text})
    data.update({"Description":description})

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
    maintable = soup.find_all(class_="tablePair")


    for table in maintable:
        # Extract data from each table pair
        left = table.find_all(class_='table_left')
        right = table.find_all(class_='table_right')

        leftList = [str(i.text.strip()) for i in left]
        rightList = [str(i.text.strip()) for i in right]

        # Add to the main data dictionary
        data.update(dict(zip(leftList, rightList)))

    # Add latitude and longitude to the data
    if lat_o and lng_o:
        data['Latitude'] = lat_o
        data['Longitude'] = lng_o

    #transaction = transactions_data(soup)
    #data.update(transaction)
    #adj = get_adj(propertyID)
    #data.update(adj)
    building_age = extract_estate_info(soup)
    if len(building_age) != 0:
        data.update(building_age)
    write(data, propertyID,dir_path)
    return True

if __name__ == '__main__':
    fileName = "Update.txt"
    dir_path ="./Housing/"+str(datetime.date.today())
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

    existing_files = {f.split(".json")[0] for f in os.listdir(dir_path) if f.endswith(".json")}
    print(len(existing_files))

    with open(fileName, "r") as file:
        ids = file.read().splitlines()
    print(len(ids))

    unique_ids = set(ids)-set(existing_files)
    print(len(unique_ids))

    for i in unique_ids:
        read(i,dir_path)

