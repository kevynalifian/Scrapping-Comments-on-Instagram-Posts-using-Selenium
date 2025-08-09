# IMPORT LIBRARY
import os
import csv
import time
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import StaleElementReferenceException
import schedule

# FUNCTION TO OPEN INSTAGRAM USING SELENIUM
def openselenium():
    driver = Options()
    driver.add_argument("--ignore-certificate-errors")
    driver.add_experimental_option("detach", True)
    driver.add_argument('--ignore-certificate-errors')
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=driver)
    driver.get("https://www.instagram.com/")
    return driver

# FUNCTION FOR AUTOMATIC LOGIN
def login(driver, username_str, password_str):
    username = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username']")))
    password = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password']")))

    username.clear()
    password.clear()
    username.send_keys(username_str)
    password.send_keys(password_str)
    log_in = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))).click()
    time.sleep(1.5)

# FUNCTION TO FIND THE SEARCH BUTTON
def search(driver, keyword):
    search_box = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//span[text()='Search']"))).click()
    searchbox = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Search']")))
    searchbox.clear()
    searchbox.send_keys(keyword)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{keyword}')]"))).click()
    time.sleep(2)

# FUNCTION TO GET LINK
def get_link(driver):
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
    anchors = driver.find_elements(By.TAG_NAME, 'a')    
    print(f"Found {len(anchors)} anchor elements.")  # Debug print
    hrefs = []

    for a in anchors:
        if len(hrefs) >= 5:
            break
        try:
            href = a.get_attribute('href')
            if href and '/p/' in href:  # Check if href is not None or empty
                hrefs.append(href)
                print(f"Found link: {href}")  # Debug print
        except StaleElementReferenceException:
            try:
                a = driver.find_element(By.TAG_NAME, 'a')
                href = a.get_attribute('href')
                if href and '/p/' in href:  # Check if href is a post link
                    hrefs.append(href)
                    print(f"Found link after retry: {href}")  # Debug print
            except StaleElementReferenceException:
                continue 

    return hrefs

# FUNCTION TO VISIT LINK AND WRITE TO CSV
def visit_links(driver, links):
    with open('comments_usernames.csv', 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['URL', 'Username', 'Comment'])

    # Loop melalui setiap URL postingan (hanya 3)
        for link in links:
            driver.get(link)
            print(f"Visiting {link}")
            time.sleep(5)
            try:
                # Temukan elemen yang dapat digulir
                scrollable_div = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.x5yr21d.xw2csxc.x1odjw0f.x1n2onr6"))
                )
                
                last_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                new_comments_loaded = True
                scroll_attempts = 0

                while new_comments_loaded and scroll_attempts < 10:  # Batasi maksimal 10 kali scroll
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                    time.sleep(5)  # Tambahkan waktu tunggu untuk memuat komentar
                    new_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
                    if new_height == last_height:
                        new_comments_loaded = False
                    else:
                        last_height = new_height
                        scroll_attempts += 1

                # Tambahkan waktu tunggu setelah semua scroll selesai untuk memastikan komentar dimuat
                time.sleep(10)

                # Scroll kembali ke atas
                driver.execute_script("arguments[0].scrollTop = 0", scrollable_div)
                time.sleep(2)  # Waktu tunggu setelah scroll ke atas
                
                # Tunggu hingga elemen komentar muncul
                comments = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.x1lliihq.x1plvlek.xryxfnj.x1n2onr6.x193iq5w.xeuugli.x1fj9vlw.x13faqbe.x1vvkbs.x1s928wv.xhkezso.x1gmr53x.x1cpjm7i.x1fgarty.x1943h6x.x1i0vuye.xvs91rp.xo1l8bm.x5n08af.x10wh9bi.x1wdrske.x8viiok.x18hxmgj"))
                )
                usernames = WebDriverWait(driver, 5).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span._ap3a._aaco._aacw._aacx._aad7._aade")))

                for username, comment in zip(usernames, comments):
                    # Periksa apakah elemen span memiliki anak elemen <a>
                    if not comment.find_elements(By.TAG_NAME, 'a'):
                        username_text = username.text
                        comment_text = comment.text
                        print(f"Username: @{username_text}, Comment: {comment_text}")

                        # Tulis URL postingan, username, dan komentar ke dalam file CSV
                        writer.writerow([link, f"@{username_text}", comment_text])
                        print(f"Wrote to CSV: {link}, @{username_text}, {comment_text}")

            except Exception as e:
                # Jika terjadi kesalahan
                print("Error:", e)
                print("Could not retrieve data for:", link)

# FUNCTION FOR SAVE TO MONGO
def save_mongo(filename):
    client = MongoClient('mongodb://localhost:27017/')
    db = client.db_analisis_sentimen
    insta_collection = db.instagram

    data_dir = 'insta-data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    filepath = os.path.join(data_dir, filename)
    
    with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for comment in reader:
            # Pastikan "URL" tidak kosong dan bukan hanya kata "URL"
            if comment.get("URL") and comment["URL"] != "URL":
                existing_comment = insta_collection.find_one({"URL": comment["URL"], "Username": comment["Username"], "Comment": comment["Comment"]})

                if not existing_comment:
                    comment_to_save = {
                        "URL": comment.get("URL"),
                        "Username": comment.get("Username"),
                        "Comment": comment.get("Comment"),
                    }
                    insta_collection.insert_one(comment_to_save)
        
def main():
    driver = openselenium()
    login(driver, "Your_username", "Your_password")
    search(driver, "Your_keyword")
    links = get_link(driver)
    print(links)
    visit_links(driver, links)
    save_mongo('comments_usernames.csv')

def schedule_crawling():
    schedule.every().day.at("13:28").do(main)  # Atur waktu sesuai kebutuhan Anda
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    schedule_crawling()
