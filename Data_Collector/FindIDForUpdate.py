from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import time
import random

# Set up ChromeDriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Optional: run headless, comment out if you want to see the browser window
driver = webdriver.Chrome(executable_path='./chromedriver',options=options)

# URL of the first page to scrape
base_url = "https://www.28hse.com/en/rent"
driver.get(base_url)

# List to store property IDs
property_ids = []

# Scraping logic with pagination
i = 0
while True:
    # Wait for the page to load
    time.sleep(random.randint(2,2))
    try:
        # Find all property elements on the current page
        properties = driver.find_elements(By.CLASS_NAME, "detail_page")

        # Extract the 'attr1' property IDs
        for prop in properties:
            property_id = prop.get_attribute("attr1")
            if property_id:
                property_ids.append(property_id)
        i += 1
        print(f"Collected {i} pages so far...")
        #Edge Case
        if i == 2000:
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

#Removing Duplicate
property_ids = list(set(property_ids))

print("Total Number of ",len(property_ids),"IDs are Found")

with open("Completed.txt") as file:
    past = file.read().splitlines()

unique_ids = [estate_id for estate_id in property_ids if estate_id not in past]

print("Total Number of ",len(unique_ids),"IDs need to be scraped")

with open("Need_Update.txt","w") as file:
    for i in unique_ids:
        file.write(i)
        file.write("\n")

print("List is written as Need_Update.txt")




